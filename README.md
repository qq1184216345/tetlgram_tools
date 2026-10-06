# 纸翼（PaperWing）

基于 **Tauri 2 + React + TypeScript** 前端与 **Python FastAPI + Telethon** 后端的 Telegram 营销自动化工具，功能对标彩虹 TG 助手。

## 架构

```
Tauri GUI (React)  ←→  HTTP 127.0.0.1:28147  ←→  Python Backend (Telethon)
```

## 功能模块

| 模块 | 状态 |
|------|------|
| 账号中心（登录/导入/连接） | ✅ |
| 设置（API/代理，持久化） | ✅ |
| 群发消息 / 自动加群 | ✅ |
| 私信 | ✅ |
| 群成员采集 / 关键词搜群 | ✅ |
| 群拉人 | ✅ |
| 炒群 | ✅ |
| 监控 / 自动回复 | ✅ |
| 过滤筛群 | ✅ |

## 环境要求

- Node.js 20+
- Rust 1.70+
- Python 3.10+

## 端口配置

所有端口统一在 `config/ports.json` 中管理，均为非常见默认端口，避免冲突：

| 服务 | 端口 |
|------|------|
| Python 后端 API | 28147 |
| Vite 开发服务器 | 28182 |
| Vite HMR | 28183 |
| 授权云服务 | 28180 |
| PostgreSQL（宿主机映射） | 25432 |

如需修改，编辑 `config/ports.json`，并同步更新：
- `src-tauri/tauri.conf.json` 的 `devUrl`
- `.env.development` 的 `VITE_LICENSE_API_BASE`
- `license-server/.env` 的 `DATABASE_URL` / docker-compose 映射

## 群发发送类型

支持四种发送模式：文本、图片、文件、转发频道消息（可隐藏来源）。

## tdata 转换

在「账号中心 → 导入 Session」中输入 Telegram Desktop 的 tdata 目录路径即可转换。
需要安装 opentele（已包含在 requirements.txt 中，运行 `npm run setup:python` 即可）

## 快速开始

更完整的中文步骤见根目录 [`启动说明.txt`](./启动说明.txt)。

### 1. 安装依赖

```bash
# 前端
npm install

# 后端（自动创建 .venv 虚拟环境并安装依赖）
npm run setup:python
```

Python 依赖安装在项目根目录的 `.venv/` 中，与系统 Python 完全隔离。

### 2. 配置 API

在应用「设置」页面填入从 [my.telegram.org](https://my.telegram.org) 申请的 `api_id` 和 `api_hash`，并配置代理后点「测试网络连接」。

### 3. 开发模式

```bash
# 推荐：一键启动前后端
.\dev.bat
# 或
npm run dev:all

# 方式二：Tauri 自动拉起后端
npm run tauri dev

# 方式三：分别启动
npm run backend            # 终端 1（使用 .venv）
npm run tauri dev          # 终端 2
```

> Tauri 启动时会自动检测并使用 `.venv` 中的 Python。若虚拟环境不存在，会回退到系统 Python。

### 4. 导入账号

账号中心支持 **同时选择 `.session` + 同名 `.json`** 一键配对导入（也可稍后单独补传 json）。列表「JSON」列可查看是否已关联。

### 5. 构建

双击根目录 **`pack.bat`**，或执行 `npm run pack:win`（一键：前端 + 无窗口后端 + NSIS 安装包）。

```bash
npm run build:all
# 或
npm run tauri build
```

若杀软误报，将安装目录加入白名单即可（本项目为 Tauri + Python，非易语言）。
## 目录结构

```
纸翼/
├── src/                 # React 前端
├── src-tauri/           # Tauri Rust 壳
├── backend/             # Python 后端
│   ├── api/             # REST API 路由
│   ├── telegram/        # Telethon 客户端管理
│   └── models/          # 数据模型
├── data/
│   ├── sessions/        # Telethon session 文件
│   ├── 配置/            # 批量修改资料模板
│   ├── 采集/            # 采集结果
│   └── 日志/
└── requirements.txt
```

## 软件多开

每个实例使用独立数据目录，避免 session、配置、任务互相冲突：

**开发模式**（PowerShell）：

```powershell
$env:PAPERWING_DATA = "E:\PaperWing-data-2"
npm run backend
# 另开终端
npm run dev
```

**生产构建**：复制整个安装目录到不同路径，各实例的 `data/` 目录天然隔离（Release 版通过 `PAPERWING_DATA` 指向各自 `data` 目录；旧变量 `TELEGRAM_TOOLS_DATA` 仍可用）。

## 商业授权（一期）

桌面端需连接**授权云服务**完成邮箱登录与卡密激活后才能使用群发/私信等任务。

| 组件 | 说明 |
|------|------|
| 授权服务 | [`license-server/`](license-server/) ，默认 `http://127.0.0.1:28180` |
| 管理后台 | `http://127.0.0.1:28180/admin/` （默认管理员见该目录 README） |
| 数据库 | PostgreSQL（`docker compose up -d` 于 `license-server/`） |
| 本地门禁 | 加密缓存授权状态；断网超过 24h 锁定任务 |

开发时先起库再起授权服务：

```bat
cd license-server
docker compose up -d
run.bat
```

发行前把根目录 `.env.production` 里的 `VITE_LICENSE_API_BASE` 改成你的 HTTPS 域名后重新打包。详见 [`license-server/README.md`](license-server/README.md)。

在线支付（DujiaoPay）对接说明已预留：[`docs/dujiaopay-integration.md`](docs/dujiaopay-integration.md)（等域名服务器就绪后再实施）。

**上线部署总流程（官网 + 授权云 + Win/Mac 打包）**：[`docs/go-live-runbook.md`](docs/go-live-runbook.md)。

**组件与发版总览（前端 / 后端 / 官网 / 授权后台 / 打包 / 上传 / 发版）**：[`docs/system-overview.md`](docs/system-overview.md)。

**云端部署配置（PostgreSQL / 环境变量 / Nginx / 运维注意）**：[`docs/cloud-ops.md`](docs/cloud-ops.md)。

## 安全说明

- Session 文件等同于账号完整登录态，请妥善保管
- 建议使用自己的 API ID，避免公共 API 导致封号
- 授权云仅处理账号/卡密/会话，不上传 Telegram 业务数据（群发内容、私信目标等仍在本地）
- 生产环境请修改管理员密码，并通过 HTTPS 部署授权服务
- 桌面端对授权会话/本地门禁做了加密与发行构建加固，可提高破解成本，但无法做到绝对不可逆向
