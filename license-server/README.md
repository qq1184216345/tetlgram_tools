# 纸翼授权云服务（一期）

独立部署的卡密/账号授权服务，供桌面端登录、激活、单点登录心跳与 Web 管理后台使用。

## 功能

- 邮箱+密码注册/登录
- 卡密激活（按时长累加到期）
- 单点登录（新登录踢旧会话）
- 管理后台：发卡、用户封禁/延期、审计

## 邮件验证码（注册 / 找回密码）

授权服务通过 SMTP SSL 发送 6 位验证码：

| 项 | 值 |
|----|-----|
| SMTP | `mail.spacemail.com:465` SSL |
| 发件地址 | `nb@zhiyinb.cc` |
| IMAP（备用） | `mail.spacemail.com:993` SSL |

配置写在 `license-server/.env`（勿提交仓库）：

```env
SMTP_HOST=mail.spacemail.com
SMTP_PORT=465
SMTP_USER=nb@zhiyinb.cc
SMTP_PASSWORD=***
SMTP_FROM=nb@zhiyinb.cc
```

API：

- `POST /auth/send-code` `{ email, purpose: "register"|"reset" }`
- `POST /auth/register` 需带 `email_code`
- `POST /auth/reset-password` `{ email, email_code, new_password }`

验证码 10 分钟有效，同一邮箱 60 秒冷却。

## 快速启动（开发）

### 1) 启动 PostgreSQL

```bat
cd license-server
docker compose up -d
```

默认连接串：

```
postgresql+psycopg://paperwing:paperwing@127.0.0.1:25432/paperwing_license
```

宿主机端口为 **25432**（映射容器内 5432），避免与本机其它 PostgreSQL 抢默认口。

### 2) 启动授权服务

```bat
cd license-server
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
run.bat
```

或：

```bat
cd license-server
set PYTHONPATH=%CD%
..\ .venv\Scripts\python.exe -m license_server
```

默认监听：`http://127.0.0.1:28180`（端口见仓库根目录 `config/ports.json`）

- 健康检查：`GET /health`
- 管理后台：`http://127.0.0.1:28180/admin/`

### 默认管理员（首次启动自动创建）

| 项 | 默认值 |
|----|--------|
| 邮箱 | `nb@zhiyinb.cc` |
| 密码 | `xmm123456` |

生产环境务必通过环境变量覆盖：

```bat
set ADMIN_EMAIL=you@example.com
set ADMIN_PASSWORD=strong-password
set JWT_SECRET=random-long-secret
set DATABASE_URL=postgresql+psycopg://user:pass@host:25432/paperwing_license
```

紧急本地调试仍可用 SQLite（不推荐上线）：

```bat
set DATABASE_URL=sqlite:///D:/data/license.db
```

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录（踢掉旧会话） |
| POST | `/auth/heartbeat` | 心跳 |
| POST | `/license/redeem` | 激活卡密 |
| POST | `/license/verify` | 校验授权 |
| POST | `/admin/cards/generate` | 批量发卡 |
| GET | `/admin/users` | 用户列表 |
| POST | `/admin/users/{id}/ban` | 封禁/解封 |
| POST | `/admin/users/{id}/extend` | 延期 |
| GET | `/admin/audit` | 审计日志 |

请求头：`Authorization: Bearer <session_token>`

## 桌面端配置

授权服务地址**写死在构建配置**，客户端不提供填写框：

- 开发：`.env.development` → `VITE_LICENSE_API_BASE=http://127.0.0.1:28180`
- 发行：`.env.production` → `VITE_LICENSE_API_BASE=https://你的域名`，改完后重新 `npm run build` / `tauri build`

本地门禁缓存 `data/license_cache.enc` 为机器绑定加密文件；前端会话亦做 AES-GCM 本地加密。

## 生产部署建议

1. 使用 HTTPS 反代（Nginx/Caddy）
2. 更换 `ADMIN_PASSWORD` / `JWT_SECRET`
3. 使用 PostgreSQL：`DATABASE_URL=postgresql+psycopg://...`
4. systemd / Docker 常驻进程
5. 桌面发行包打包前确认 `.env.production` 域名正确
6. 官网静态文件在仓库根目录 [`website/`](../website/)。本地跑授权服务时，打开 `http://127.0.0.1:28180/` 即为官网；上线可用 Nginx 直接托管 `website/`（示例见 `website/deploy.nginx.conf`），客服邮箱、Telegram、安装包地址改 `website/assets/config.js`

```dockerfile
# 示例：在 license-server 目录构建
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 28180
CMD ["python", "-m", "license_server"]
```

## 一期边界

- 不做在线支付、号量限制、硬机器码绑定
- 客户端加固可提高破解成本，无法做到绝对不可逆向

## 在线支付（待上线）

DujiaoPay 稳定币收款对接方案已预留文档，**等域名与服务器就绪后再开发**：

→ [`docs/dujiaopay-integration.md`](../docs/dujiaopay-integration.md)

## 生产上线（待域名/服务器）

官网 + `/admin` + API 同域部署、Windows/Mac 打包顺序：

→ [`docs/go-live-runbook.md`](../docs/go-live-runbook.md)

## 桌面版本管理

- 公开：`GET /app/version`
- 管理：后台「版本」Tab（需管理员登录）
- 客户端启动提醒 + 设置页「检查更新」
- 支付流程：人工售卡 → 后台发卡 → 用户激活
