# 纸翼（PaperWing）系统总览：前端 · 后端 · 官网 · 授权 · 打包 · 上传 · 发版

> 本文汇总桌面端与授权云各组件职责、目录、端口、日常开发与发版流程。  
> 生产域名（一期已上线）：`https://www.zhiyinb.cc`（同域：官网 / 授权 API / 管理后台 / 安装包下载）。

相关文档：

| 文档 | 用途 |
|------|------|
| [`../README.md`](../README.md) | 仓库入门、本地启动 |
| [`go-live-runbook.md`](./go-live-runbook.md) | 服务器首次上线步骤 |
| [`cloud-ops.md`](./cloud-ops.md) | **云端配置：数据库、.env、Nginx、运维与安全注意** |
| [`../license-server/README.md`](../license-server/README.md) | 授权云 API 与本地开发 |
| [`dujiaopay-integration.md`](./dujiaopay-integration.md) | 支付对接（可选） |
| [`../config/ports.json`](../config/ports.json) | 本地端口唯一配置源 |

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  用户浏览器                                                  │
│  https://www.zhiyinb.cc/          → 官网 website/            │
│  https://www.zhiyinb.cc/admin/    → 授权管理后台              │
│  https://www.zhiyinb.cc/auth|license|app|health → 授权 API   │
│  https://www.zhiyinb.cc/downloads/*.exe → 安装包             │
└───────────────────────────┬─────────────────────────────────┘
                            │ Nginx + HTTPS
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  云服务器 /opt/paperwing                                      │
│  · license-server（FastAPI，systemd: paperwing-license）     │
│  · PostgreSQL（Docker，仅 127.0.0.1:25432）                    │
│  · website/ + admin/ 静态资源由同一进程托管                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  用户电脑 · Windows 桌面端「纸翼」                             │
│  Tauri 壳 + React UI  ←HTTP→  本地 Python 后端 (Telethon)     │
│  授权：HTTPS → www.zhiyinb.cc（登录 / 卡密 / 心跳）           │
│  业务数据：仅本地 data/（session、任务、日志，不上云）         │
└─────────────────────────────────────────────────────────────┘
```

**原则：** 云上只跑「官网 + 授权云 + 管理后台 + 安装包下载」；Telegram 号池与群发/私信内容永远在用户本机。

---

## 2. 前端（桌面 UI）

| 项 | 说明 |
|----|------|
| 技术栈 | React 19 + TypeScript + Vite 7 |
| 目录 | `src/`（页面 `src/pages/`，组件 `src/components/`） |
| 壳 | Tauri 2（`src-tauri/`），窗口标题「纸翼」 |
| 本地开发端口 | Vite `28182`，HMR `28183` |
| 调业务后端 | HTTP `http://127.0.0.1:28147`（见 `config/ports.json`） |
| 调授权云 | `VITE_LICENSE_API_BASE`（开发见 `.env.development`，发行见 `.env.production`） |

### 模块页（导航）

账号中心、群发/加群、采集、私信、群拉人、炒群、监控/自动回复、综合功能、过滤筛群、设置。

### 关键体验要点

- 底部 **全局运行日志** 可拖上边缘调高度，按任务 / 账号 Tab 筛选，可导出。
- 登录门禁：邮箱注册/登录、卡密激活、本地加密授权缓存；断网超 24h 锁定任务。
- 私信 / 群发：**勾选的每个账号对全部目标各发一遍**（全量，非分流）；`PeerFlood` 按「本目标失败、账号继续」处理（常对应双向联系人限制）。

### 常用命令

```bat
npm install
npm run dev          # 仅 Vite
npm run tauri dev    # Tauri + 前端（可自动起后端）
npm run build        # 产出 dist/（发行时打进 Tauri）
```

---

## 3. 业务后端（本地 Telethon）

| 项 | 说明 |
|----|------|
| 技术栈 | Python 3.10+ · FastAPI · Telethon |
| 目录 | `backend/`（`api/` 路由，`telegram/` 业务，`tasks/` 任务管理） |
| 监听 | `127.0.0.1:28147` |
| 虚拟环境 | 仓库根目录 `.venv/`（`npm run setup:python`） |
| 本地数据 | `data/sessions`、`data/日志`、`data/采集` 等（可用 `PAPERWING_DATA` 多开隔离） |

### 职责

- 账号登录 / session 导入 / tdata 转换、连接与资料修改。
- 群发、加群、私信、采集、拉人、炒群、监控、筛群、链接提取等任务编排。
- **不负责**卡密与用户账号体系（那是授权云）。

### 常用命令

```bat
npm run setup:python
npm run backend
npm run dev:all          # scripts/dev.ps1：尽量一并拉起 PG + 授权云 + 桌面
```

发行时后端由 PyInstaller 打成 `src-tauri/bin/telegram-backend/telegram-backend.exe`，随安装包分发。

---

## 4. 官网

| 项 | 说明 |
|----|------|
| 目录 | `website/`（`index.html` + `assets/`） |
| 配置 | `website/assets/config.js`（品牌、版本、客服邮箱、**下载地址**、套餐文案） |
| 生产访问 | `https://www.zhiyinb.cc/` |
| 托管方式 | 由 `license-server` 同进程提供 `/` 与 `/assets`；Nginx 反代整站到 `127.0.0.1:28180` |

改官网文案或下载链接：编辑 `config.js`（及静态页）后上传到服务器 `/opt/paperwing/website/`，一般**无需重启**静态文件即时生效；若改了 FastAPI 挂载逻辑才需 `systemctl restart paperwing-license`。

---

## 5. 授权云 + 管理后台

| 项 | 说明 |
|----|------|
| 目录 | `license-server/`（应用 `license_server/`，后台 UI `admin/`） |
| 本地端口 | `28180` |
| 数据库 | PostgreSQL（`license-server/docker-compose.yml`，宿主机 `25432`） |
| 环境变量 | `license-server/.env`（**勿提交 Git**） |
| 生产进程 | `paperwing-license.service`，工作目录 `/opt/paperwing/license-server` |
| 生产部署根 | `/opt/paperwing`（含 `website/`、`config/ports.json`、`DEPLOY_CREDENTIALS.txt`） |

### 能力

- 邮箱验证码注册 / 找回、登录、卡密激活（按时长累加）。
- 单点登录（新登录踢旧会话）、心跳。
- 管理后台：用户、批量发卡、版本号/下载地址、审计。
- 桌面端版本检查：`GET /app/version`（后台「版本」Tab 可改）。

### 本地启动

```bat
cd license-server
docker compose up -d
run.bat
```

- 健康检查：`http://127.0.0.1:28180/health`
- 管理后台：`http://127.0.0.1:28180/admin/`
- 生产：`https://www.zhiyinb.cc/admin/`

### 后台站点图标

`license-server/admin/index.html` 引用 `/admin/assets/favicon.ico`（与官网同源 logo）。

---

## 6. 端口一览（本地开发）

| 服务 | 端口 | 配置 |
|------|------|------|
| 业务后端 | 28147 | `config/ports.json` → backend |
| Vite | 28182 | frontend.port |
| Vite HMR | 28183 | frontend.hmrPort |
| 授权云 | 28180 | license |
| PostgreSQL 映射 | 25432 | postgres |

生产公网仅暴露 `80/443`；授权进程只听本机 `127.0.0.1:28180`，由 Nginx 反代。

---

## 7. 打包（Windows 桌面安装包）

### 前置

1. Node 20+、Rust、Python 3.10+、本机已 `npm install` 与 `npm run setup:python`。
2. 根目录 `.env.production`：

```env
VITE_LICENSE_API_BASE=https://www.zhiyinb.cc
```

3. `src-tauri/tauri.conf.json` 当前 `bundle.targets` 为 **`nsis`**（WiX/MSI 对中文产品名易失败，已改用 NSIS）。

### 命令

双击根目录 **`pack.bat`**，或：

```bat
npm run pack:win
```

高级参数（PowerShell）：

```powershell
.\scripts\pack-windows.ps1              # 完整：venv + 前端 + 后端 + NSIS
.\scripts\pack-windows.ps1 -SkipSetup   # 跳过 setup:python
.\scripts\pack-windows.ps1 -SkipBackend # 已有 telegram-backend.exe 时仅重打壳
```

等价手工步骤：`npm run setup:python` → `npm run build` → `npm run build:backend` → `npx tauri build`。

### 产物

| 文件 | 路径 |
|------|------|
| NSIS 安装包 | `src-tauri/target/release/bundle/nsis/纸翼_0.1.0_x64-setup.exe` |
| 可执行文件 | `src-tauri/target/release/paperwing.exe` |
| 内嵌后端 | `src-tauri/bin/telegram-backend/` |

建议复制一份 ASCII 文件名便于 CDN/官网：

`website/downloads/PaperWing-0.1.0-x64-setup.exe`

### 注意

- 若 `CARGO_TARGET_DIR` 被指到沙箱临时目录，WiX/NSIS 可能异常；发行时建议目标目录为 `src-tauri/target`。
- 杀软可能误报：安装目录加白名单即可。

---

## 8. 上传与云端更新

### 一键部署脚本（首次或大更新）

```powershell
$env:PAPERWING_SSH_HOST='服务器IP'
$env:PAPERWING_SSH_PORT='SSH端口'
$env:PAPERWING_SSH_USER='root'
$env:PAPERWING_SSH_PASSWORD='***'   # 勿写入仓库；优先改密钥登录
$env:PAPERWING_DOMAIN='zhiyinb.cc'
python scripts/deploy_license_cloud.py
```

脚本会上传 `website/`、`license-server/`、`config/ports.json`，配置 Docker PG、venv、systemd、Nginx，并尽量申请 Let’s Encrypt。

### 常见热更新（不必整站重装）

| 改动 | 上传到服务器 | 是否重启服务 |
|------|----------------|--------------|
| 官网 `config.js` / 静态页 | `/opt/paperwing/website/` | 否 |
| 安装包 exe | `/opt/paperwing/website/downloads/` | 否（需已挂载 `/downloads`） |
| 管理后台 HTML/CSS/JS/图标 | `/opt/paperwing/license-server/admin/` | 否 |
| `license_server/*.py` | `/opt/paperwing/license-server/` | **是** `systemctl restart paperwing-license` |
| `.env`（SMTP/JWT 等） | `/opt/paperwing/license-server/.env` | **是** |

### 安装包下载 URL（当前）

```
https://www.zhiyinb.cc/downloads/PaperWing-0.1.0-x64-setup.exe
```

对应配置：`website/assets/config.js` → `downloadUrl`。  
FastAPI 挂载：`/downloads` → `website/downloads/`（见 `license_server/app.py`）。

---

## 9. 发版清单（建议每次发版按序勾选）

### A. 版本号对齐

- [ ] 根目录 `package.json` → `version`
- [ ] `src-tauri/tauri.conf.json` → `version` / `productName`
- [ ] `website/assets/config.js` → `version`、`downloadUrl`（文件名含版本）
- [ ] 授权后台「版本」Tab：`最新版本号` + `下载地址`（供桌面端 `GET /app/version` 检查更新）

### B. 桌面端

- [ ] 确认 `.env.production` 为生产授权地址
- [ ] `npm run build:all`，得到 NSIS 安装包
- [ ] 本机安装冒烟：登录授权云、激活卡密、连 Telegram、跑一条短任务

### C. 云端

- [ ] 上传 exe 到 `/opt/paperwing/website/downloads/`
- [ ] 更新 `website/assets/config.js` 的 `downloadUrl`
- [ ] 管理后台版本配置与官网一致
- [ ] 若有服务端代码改动：上传并 `systemctl restart paperwing-license`
- [ ] 冒烟：`/health`、官网下载、`/admin` 登录、发验证码邮件

### D. 公告与回滚

- [ ] 通知用户下载新包；旧包可保留带版本号的文件名以便回滚
- [ ] 记录本次发版日期、版本号、主要变更（建议写在 `CHANGELOG` 或本仓库 Issues）

### 当前一期状态（摘要）

| 项 | 状态 |
|----|------|
| 域名 / HTTPS | ✅ `zhiyinb.cc` / `www.zhiyinb.cc` |
| 授权云 + PG + Nginx | ✅ `/opt/paperwing` + `paperwing-license` |
| 官网 + 管理后台 | ✅ |
| Windows NSIS 包 | ✅ 已挂下载 |
| Mac 包 | ⏳ 需 Mac 机 |
| DujiaoPay 自动收款 | ⏳ 见支付文档 |

---

## 10. 目录速查

```
TelegramTools/
├── src/                      # 桌面 React 前端
├── src-tauri/                # Tauri；icons、打包配置、bin/telegram-backend
├── backend/                  # 本地 Telethon 业务后端
├── license-server/           # 授权云 + admin/
├── website/                  # 官网 + downloads/
├── config/ports.json         # 端口
├── scripts/
│   ├── setup-python.ps1
│   ├── build-backend.ps1
│   ├── dev.ps1
│   └── deploy_license_cloud.py
├── docs/
│   ├── system-overview.md    # 本文
│   ├── go-live-runbook.md
│   └── dujiaopay-integration.md
├── .env.production           # 发行授权 API 地址
└── data/                     # 本地运行时数据（勿提交敏感 session）
```

---

## 11. 安全提醒

- `license-server/.env`、服务器 root / 数据库密码、SMTP、JWT **不要提交 Git**，不要长期明文出现在聊天记录。
- 生产 PostgreSQL 只绑 `127.0.0.1`；公网只开 80/443。
- Session 等于账号完整登录态，仅存用户本机。
- 聊天中暴露过的 SSH 密码建议尽快改为密钥登录并轮换。
