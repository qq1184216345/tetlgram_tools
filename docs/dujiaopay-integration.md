# 纸翼 × DujiaoPay 对接说明（待上线后实施）

> 状态：**文档预留，代码未对接**。等域名 + 云服务器就绪后再开工。  
> 官方文档：https://www.dujiaopay.com/docs  
> 本地密钥已写入 `license-server/.env`（`DUJIAOPAY_KEY_ID` / `DUJIAOPAY_SECRET`），**勿提交仓库**。

---

## 1. 目标业务流

用户在线买时长 → 稳定币付款 → 到账后自动开通/延期授权（不必再人工发卡）。

推荐两种履约方式（二选一或都做）：

| 方式 | 说明 | 推荐 |
|------|------|------|
| A. 支付成功直接给账号加天数 | `order.paid` 后按套餐 `duration_days` 延长 `users.expires_at` | **首选**（少一步卡密） |
| B. 支付成功生成卡密并发邮件 | 生成 `PW-xxxx` 卡密，用户到桌面端激活 | 备选（兼容现有卡密体系） |

一期建议做 **A**，管理后台仍保留人工发卡作兜底。

```
桌面端 / 购买页（登录态）
    │  POST /pay/create-order { plan_id }
    ▼
license-server（纸翼授权云）
    │  HMAC 签名 → POST https://www.dujiaopay.com/v1/orders
    │  落库 payment_orders
    ▼
返回 checkout_url → 用户浏览器打开收银台付款
    │
    ▼
DujiaoPay 链上确认
    │  POST Webhook → https://你的域名/webhooks/dujiaopay
    ▼
license-server 验签 + 幂等
    │  status=paid → 给 user 延期 / 或发卡密
    ▼
用户桌面端心跳/刷新后 licensed=true
```

**履约以 Webhook `order.paid` + 服务端查单为准**，不能只靠 `success_url` 跳转。

---

## 2. 上线前你需要准备的东西

### 2.1 基础设施

- [ ] 已备案/可用的域名（例：`license.xxx.com`）
- [ ] 云服务器，HTTPS（Nginx/Caddy 反代到授权云进程）
- [ ] PostgreSQL（生产库，勿用开发机 SQLite）
- [ ] 授权云常驻：`python -m license_server` 或 Docker/systemd

### 2.2 DujiaoPay 商户后台

- [ ] 项目已创建，收款地址已配置（至少一条链，如 Tron USDT）
- [ ] API Keys：`key_id` + `secret`（本地 `.env` 已有，上线写入服务器环境变量）
- [ ] **新建 Webhook**
  - 回调地址：`https://你的域名/webhooks/dujiaopay`
  - 保存后复制 **Webhook Secret** → `DUJIAOPAY_WEBHOOK_SECRET`
- [ ] 用「推送历史 / 测试事件」验证能打到服务器

### 2.3 服务器环境变量（示例）

```env
# 已有
DATABASE_URL=postgresql+psycopg://...
JWT_SECRET=生产随机长串
ADMIN_PASSWORD=强密码
SMTP_PASSWORD=...

# DujiaoPay
DUJIAOPAY_BASE_URL=https://www.dujiaopay.com
DUJIAOPAY_KEY_ID=ak_...
DUJIAOPAY_SECRET=sk_...
DUJIAOPAY_WEBHOOK_SECRET=whsec_...   # 建完 Webhook 后填

# 对外域名（拼 success_url / 文档用）
PUBLIC_BASE_URL=https://license.xxx.com
```

密钥只放服务端，**禁止**进桌面端 / 前端包 / Git。

---

## 3. DujiaoPay 技术要点（摘自官方文档）

| 项 | 值 |
|----|-----|
| API 根 | `https://www.dujiaopay.com` |
| 鉴权 | HMAC-SHA256，头：`DJP-Key-ID` / `DJP-Timestamp` / `DJP-Nonce` / `DJP-Signature` |
| 自检 | `GET /v1/whoami`（先打通再业务） |
| 建单 | `POST /v1/orders` |
| 查单 | `GET /v1/orders/{id}` |
| 取消 | `POST /v1/orders/{id}/cancel`（仅 pending） |
| 收银台 | 建单返回 `checkout_url`，可直接跳转 |
| Webhook 验签 | `HMAC-SHA256(secret, "<timestamp>.<raw_body>")`，按 `DJP-Webhook-ID` 幂等 |

### 建单请求字段（常用）

| 字段 | 必填 | 说明 |
|------|------|------|
| `fiat_currency` | 是 | 如 `CNY` / `USD`（字符串） |
| `fiat_amount` | 是 | 金额**十进制字符串**，禁止 JSON number |
| `chain` / `token_id` | 否 | 都省略 = 收银台自选链币（延迟分配） |
| `merchant_order_id` | 建议 | 我方订单号，同项目唯一 |
| `metadata` | 建议 | 放 `user_id`、`plan_id`、`duration_days` |
| `success_url` / `cancel_url` | 否 | 仅前端体验，HTTPS |

推荐建单策略：`chain`/`token_id` 都不传，让用户在收银台选 Tron USDT 等。

示例 body：

```json
{
  "fiat_currency": "CNY",
  "fiat_amount": "99.00",
  "merchant_order_id": "pw_20260913_u12_plan30",
  "metadata": {
    "user_id": 12,
    "plan_id": "month_30",
    "duration_days": 30
  },
  "success_url": "https://license.xxx.com/pay/success",
  "cancel_url": "https://license.xxx.com/pay/cancel"
}
```

### 关键 Webhook 事件

| event_type | 动作 |
|------------|------|
| `order.paid` | **履约**：延期或发卡（幂等，只处理一次） |
| `order.expired` | 标记支付单过期 |
| `order.canceled` | 标记取消 |
| `webhook.test` | 后台测试，可只记日志 |

---

## 4. 纸翼侧建议实现清单（上线后让 AI 按此做）

### 4.1 数据表 `payment_orders`

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `merchant_order_id` | 我方单号（唯一） |
| `dujiao_order_id` | 对方 `order_id` |
| `user_id` | 购买用户 |
| `plan_id` | 套餐代号 |
| `duration_days` | 开通天数 |
| `fiat_currency` / `fiat_amount` | 计价 |
| `status` | `created` / `pending` / `paid` / `expired` / `canceled` |
| `checkout_url` | 收银台链接 |
| `paid_at` / `tx_hash` | 到账信息 |
| `webhook_event_id` | 已处理的事件 ID（幂等） |
| `created_at` | 创建时间 |

### 4.2 套餐配置（可先写死再进后台）

例：

| plan_id | 名称 | 天数 | CNY |
|---------|------|------|-----|
| `day_7` | 体验 7 天 | 7 | 19 |
| `month_30` | 月卡 | 30 | 99 |
| `year_365` | 年卡 | 365 | 699 |

### 4.3 新增 API（license-server）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/pay/plans` 或 GET | 套餐列表（可公开或需登录） |
| POST | `/pay/create-order` | 登录用户创建支付单 → 调 DujiaoPay → 返回 `checkout_url` |
| GET | `/pay/orders/{id}` | 查我方支付单状态 |
| POST | `/webhooks/dujiaopay` | **原始 body** 验签 → 处理 `order.paid` |

`/webhooks/dujiaopay` 注意：

1. 读 **raw body** 再验签，不要先 `json.loads` 再序列化。
2. 先返回 2xx，再异步/同步履约；按 `event_id` 去重。
3. `order.paid`：按 `metadata.user_id` + `duration_days` 延长授权；写审计日志。
4. 密钥校验失败返回 401，勿履约。

### 4.4 客户端 / 管理端

- 桌面端登录后增加「购买授权」：选套餐 → 调 `/pay/create-order` → 系统浏览器打开 `checkout_url`。
- 管理后台可看支付单列表、对账（可选一期）。
- 发行包 `.env.production` 的 `VITE_LICENSE_API_BASE` 改成 `https://你的域名` 后重新打包。

### 4.5 模块文件建议

```
license-server/license_server/
  dujiaopay.py      # HMAC 签名、建单、查单、webhook 验签
  plans.py          # 套餐常量
  app.py            # 挂载 /pay/* 与 /webhooks/dujiaopay
```

---

## 5. 域名与 Webhook 怎么填

在 DujiaoPay 后台 **Webhook → 新建**：

```
回调地址：https://你的域名/webhooks/dujiaopay
```

| 情况 | 做法 |
|------|------|
| 已有 HTTPS 域名 | 直接填上面地址 |
| 仅本机开发 | 填不了；用 Cloudflare Tunnel / ngrok 临时 HTTPS |
| 未上线 | **先不要建生产 Webhook**；上线当天再建并写入 `DUJIAOPAY_WEBHOOK_SECRET` |

本地可先测：`GET /v1/whoami` + 建单拿 `checkout_url` 打开收银台；自动开通必须等 Webhook 通。

---

## 6. 安全与运维注意

1. `DUJIAOPAY_SECRET` / `WEBHOOK_SECRET` 只在服务器环境变量或 `.env`，轮换后旧密钥作废。
2. 聊天里出现过密钥时，上线前在商户后台 **轮换 API Key**。
3. Webhook 与查单双保险：Webhook 漏了可定时扫 `pending` 单调 `GET /v1/orders/{id}`。
4. `merchant_order_id` 全局唯一，重试建单用同一 `Idempotency-Key`。
5. 金额用字符串；履约逻辑加数据库事务 + 唯一约束防重复加天数。

---

## 7. 你回来对接时对我说的话（复制即用）

```
域名已好：https://license.xxx.com
服务器已部署授权云，Webhook 已建，DUJIAOPAY_WEBHOOK_SECRET 已写入 .env。
按 docs/dujiaopay-integration.md 实现支付建单 + webhook 自动延期。
```

补充套餐价格/天数即可。

---

## 8. 当前仓库已就绪部分

| 项 | 状态 |
|----|------|
| 卡密授权 / 邮箱登录 / 单点登录 | ✅ 已有 |
| PostgreSQL | ✅ 已切 |
| `.env` 中 DujiaoPay Key | ✅ 本地已填（勿提交） |
| DujiaoPay 建单 / Webhook 代码 | ❌ 未写（等本文档实施） |
| 桌面端购买入口 | ❌ 未写 |

---

## 9. 参考链接

- 接入文档：https://www.dujiaopay.com/docs  
- 纸翼授权服务说明：`license-server/README.md`  
- 端口配置：`config/ports.json`（开发用；生产走 443 反代）
