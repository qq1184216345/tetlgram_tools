# 纸翼上线 Runbook（域名/服务器就绪后按此执行）

> 状态：已按本文档完成一期上线（`zhiyinb.cc` / `www.zhiyinb.cc` → `209.209.50.228`）。  
> 部署目录：`/opt/paperwing`；进程：`paperwing-license.service`；凭证备忘：服务器 `/opt/paperwing/DEPLOY_CREDENTIALS.txt`。  
> Windows 安装包与官网下载已就绪；可选：Mac 打包、DujiaoPay。  
> **组件与发版总览：** [`system-overview.md`](./system-overview.md)

相关文档：

- 系统总览（前端/后端/官网/授权/打包/上传/发版）：[`system-overview.md`](./system-overview.md)
- **云端部署配置（数据库 / .env / Nginx / 注意事项）：** [`cloud-ops.md`](./cloud-ops.md)
- 支付对接（可后做）：[`dujiaopay-integration.md`](./dujiaopay-integration.md)
- 授权服务说明：[`../license-server/README.md`](../license-server/README.md)
- 端口（仅本地开发）：[`../config/ports.json`](../config/ports.json)

---

## 0. 你需要先准备并告知的信息

请一次性提供（可打码密码，私发或写入服务器 `.env`）：

| 项 | 示例 | 必填 |
|----|------|------|
| 主域名 | `zhiyinb.cc` 或 `license.xxx.com` | ✅ |
| 服务器公网 IP | `x.x.x.x` | ✅ |
| 系统 | Ubuntu 22.04 / Debian 等 | ✅ |
| SSH 登录 | 用户 / 密钥或面板 | ✅ |
| HTTPS | 已解析 A 记录；可用 certbot | ✅ |
| 管理员邮箱/密码 | 覆盖默认 admin | ✅ |
| SMTP | 已有 `nb@zhiyinb.cc` 可沿用 | ✅ |
| PostgreSQL | 本机 Docker 或云 RDS | ✅（推荐） |
| 桌面授权 API 地址 | 一般等于 `https://域名` | ✅ |
| DujiaoPay Webhook | 可本阶段不做 | 可选 |
| Mac 打包机 | 有无 Mac | 可选（无则只发 Windows） |

---

## 1. 目标架构（一期）

```
用户浏览器
  https://你的域名/          → 官网 website/
  https://你的域名/admin/    → 管理后台
  https://你的域名/auth/*    → 授权 API
  https://你的域名/license/* → 授权 API
  https://你的域名/health    → 健康检查

桌面端（Win/Mac）
  → VITE_LICENSE_API_BASE = https://你的域名
  → 本地自带 Telethon 后端（不部署到云）
```

**原则：** 云上只跑「授权云 + 官网 + 管理后台」；Telegram 业务数据仍在用户电脑。

代码已具备同进程托管：

- `/` → `website/index.html`
- `/admin` → `license-server/admin/`
- API → FastAPI 路由

Nginx 示例：`website/deploy.nginx.conf`（可改为整站反代到 28180，由 FastAPI 统一出官网+API）。

---

## 2. 上线步骤总览（按顺序）

| 步骤 | 内容 | 依赖 |
|------|------|------|
| A | 域名解析 + 服务器环境 | 你已购买 |
| B | 部署 PostgreSQL | A |
| C | 部署 license-server + `.env` | B |
| D | Nginx HTTPS 反代 | C |
| E | 冒烟：官网 /admin / 登录发码 | D |
| F | 改 `.env.production`，打 Windows 包 | E |
| G | 官网挂下载链接 | F |
| H | （可选）Mac 打包 | 需要 Mac |
| I | （可选）DujiaoPay 支付 | 见支付文档 |

---

## 3. 步骤 A — 服务器基础环境

在云主机上（建议 Ubuntu 22.04+）：

1. 域名 A 记录指向服务器 IP（含 `www` 如需要）。
2. 安装：Docker（或原生 PostgreSQL）、Python 3.10+、Nginx、Certbot。
3. 防火墙放行 `80` / `443`；授权云进程只监听 `127.0.0.1:28180`（或 `config/ports.json` 中 license 端口）。
4. 拉代码到例如 `/opt/paperwing`（不要把本机 `.env` 里的密钥提交进 Git；服务器单独建 `.env`）。

---

## 4. 步骤 B — PostgreSQL

推荐 Docker（与仓库一致，宿主机端口可自定，生产建议不暴露公网）：

```bash
cd /opt/paperwing/license-server
# 生产可改强密码，并只绑定 127.0.0.1:25432
docker compose up -d
```

`DATABASE_URL` 示例：

```env
DATABASE_URL=postgresql+psycopg://paperwing:强密码@127.0.0.1:25432/paperwing_license
```

---

## 5. 步骤 C — 授权云进程

### 5.1 环境变量（服务器 `license-server/.env`）

至少包含：

```env
HOST=127.0.0.1
PORT=28180
DATABASE_URL=postgresql+psycopg://...
JWT_SECRET=生产用长随机串
ADMIN_EMAIL=你的管理员邮箱
ADMIN_PASSWORD=强密码

SMTP_HOST=mail.spacemail.com
SMTP_PORT=465
SMTP_USER=nb@zhiyinb.cc
SMTP_PASSWORD=***
SMTP_FROM=nb@zhiyinb.cc

# 支付可后填
DUJIAOPAY_BASE_URL=https://www.dujiaopay.com
DUJIAOPAY_KEY_ID=
DUJIAOPAY_SECRET=
DUJIAOPAY_WEBHOOK_SECRET=
```

> 聊天里暴露过的密钥，上线前建议在对应平台轮换。

### 5.2 安装与启动

```bash
cd /opt/paperwing/license-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PYTHONPATH=/opt/paperwing/license-server
# 建议 systemd 常驻，工作目录为 license-server，保证能读到 ../website
.venv/bin/python -m license_server
```

`systemd` 单元要点：

- `WorkingDirectory=/opt/paperwing/license-server`
- `Environment=PYTHONPATH=/opt/paperwing/license-server`
- `EnvironmentFile=/opt/paperwing/license-server/.env`
- 仓库根目录需存在 `website/`（`app.py` 通过 `PROJECT_ROOT/website` 找官网）

健康检查：`curl -s http://127.0.0.1:28180/health`

---

## 6. 步骤 D — Nginx + HTTPS

两种等价方案，**选一种**：

### 方案 1（更简单）：全部反代到授权云

官网、管理端、API 都由 FastAPI 提供。

```nginx
location / {
    proxy_pass http://127.0.0.1:28180;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 方案 2：静态官网 + 反代 API/Admin

参考 `website/deploy.nginx.conf`（静态 root + `/auth` `/license` `/admin` `/health` 反代）。

证书：

```bash
certbot --nginx -d 你的域名 -d www.你的域名
```

---

## 7. 步骤 E — 上线冒烟清单

- [ ] `https://域名/` 打开官网  
- [ ] `https://域名/admin/` 打开管理后台并能登录  
- [ ] `https://域名/health` 返回 ok  
- [ ] 桌面端或 curl：注册发验证码邮件成功  
- [ ] 登录 → 卡密激活 → `/auth/me` 显示 licensed  
- [ ] 单点登录：第二台登录踢第一台  

---

## 8. 步骤 F — 打 Windows 桌面版

在 **Windows 开发机**（本仓库）：

1. 编辑根目录 `.env.production`：

```env
VITE_LICENSE_API_BASE=https://你的域名
```

2. 打包：

```bat
npm run setup:python
npm run build:backend
npm run build:all
```

3. 安装包目录：`src-tauri/target/release/bundle/`（NSIS/MSI 等）。  
4. 用安装包真机测：登录授权云、连 Telegram（代理按设置页）。

---

## 9. 步骤 G — 官网挂下载

编辑 `website/assets/config.js`：

```js
downloadUrl: "https://你的域名/downloads/纸翼-setup.exe",  // 或对象存储直链
downloadName: "纸翼 Windows 安装包",
version: "0.1.0",
```

把安装包放到可下载位置（Nginx `alias`、COS/OSS、GitHub Release 均可）。  
Mac 包有了再加 Mac 下载项（官网文案目前偏 Windows，可后续改）。

---

## 10. 步骤 H — Mac 桌面版（可选，需 Mac）

**不能在 Windows 上交叉打出可用的正式 Mac 包。**

在 Mac 上：

1. 安装 Node 20+、Rust、Python 3.10+、Xcode CLT。  
2. 克隆同一仓库，配置相同 `.env.production`。  
3. 用 PyInstaller 打出无 `.exe` 后缀的 `telegram-backend`，放入 `src-tauri/bin/telegram-backend/`。  
   （当前仅有 `scripts/build-backend.ps1`，Mac 需补 `build-backend.sh` 或当场写命令。）  
4. `npm install && npm run tauri build` → `.dmg` / `.app`。  
5. 正式分发：Apple Developer 签名 + 公证（否则用户打开会被拦）。

一期可只发 Windows，官网写明「Mac 后续提供」。

---

## 11. 步骤 I — 支付（可后置）

按 [`dujiaopay-integration.md`](./dujiaopay-integration.md)：

- Webhook：`https://你的域名/webhooks/dujiaopay`  
- 未接支付前：管理后台人工发卡即可运营。

---

## 12. 安全检查（上线当天）

- [ ] 默认 `admin123456` 已改  
- [ ] `JWT_SECRET` 已换  
- [ ] `.env` 不在 Git  
- [ ] PostgreSQL 不对公网裸奔  
- [ ] HTTPS 强制跳转  
- [ ] SMTP / DujiaoPay 密钥曾出现在聊天则考虑轮换  
- [ ] 桌面包内授权地址为生产 HTTPS，不是 `127.0.0.1`

---

## 13. 执行时对我说的话（复制即用）

```
域名和服务器好了，按 docs/go-live-runbook.md 上线。

域名：https://_____
服务器：IP _____ ，系统 _____ ，SSH _____
先上 Windows；Mac / 支付先不做。
管理员邮箱：_____
```

有面板（宝塔等）也可以说，按面板方式部署。

---

## 15. 当前仓库就绪对照（写文档时）

| 能力 | 状态 |
|------|------|
| 官网 `website/` | ✅ |
| `/admin` 管理后台 | ✅ |
| 授权 API（登录/验证码/卡密/SSO） | ✅ |
| 同进程挂官网+Admin+API | ✅ |
| 桌面版本检查 + 管理后台版本页 | ✅ |
| Nginx 示例 | ✅ |
| PG + Docker Compose | ✅ |
| Win 打包脚本 `build:all` | ✅ |
| Mac 打包一键脚本 | ❌ 需 Mac 补 |
| 生产域名已写入 | ❌ 等你提供 |
| 支付自动开通 | ❌ 有文档未写码 |

### 发新版本时（运维）

1. 升 `backend/version.py` 的 `APP_VERSION`（及 `package.json` / tauri 版本）后打安装包  
2. 把安装包放到可下载 URL  
3. 打开 `https://域名/admin/` → **版本** 页：填版本号、下载地址、说明；需要时勾选强制更新  
4. 客户端下次启动或点「检查更新」即提示  

公开接口：`GET /app/version`

---

## 15. 明确不做进「首次上线」的范围

- 在线支付自动延期（可人工发卡）  
- Mac 安装包（无 Mac 则跳过）  
- 应用商店上架 / 自动更新完整体系  
- 号量限制、硬机器码绑定  

首次上线成功标准：**域名可访问官网与后台、邮箱验证码可用、Windows 客户端能连生产授权云并激活卡密。**
