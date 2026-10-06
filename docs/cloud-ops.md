# 纸翼云端部署配置与注意事项

> 本文汇总**服务器侧**配置：PostgreSQL、授权云 `.env`、systemd、Nginx/HTTPS、目录结构、运维命令与安全注意。  
> 桌面端打包/发版见 [`system-overview.md`](./system-overview.md)；首次上线步骤见 [`go-live-runbook.md`](./go-live-runbook.md)。

**当前生产（一期）：**

| 项 | 值 |
|----|-----|
| 域名 | `zhiyinb.cc` / `www.zhiyinb.cc` |
| 公网 IP | `209.209.50.228` |
| SSH | 端口 `12207`（勿写密码进仓库；建议改密钥登录） |
| 部署根目录 | `/opt/paperwing` |
| 授权进程 | `paperwing-license.service` → `127.0.0.1:28180` |
| 数据库容器 | `paperwing-license-pg` → 宿主机 `127.0.0.1:25432` |
| 凭证备忘（仅服务器） | `/opt/paperwing/DEPLOY_CREDENTIALS.txt`（权限 `600`） |

---

## 1. 云上跑什么 / 不跑什么

| 跑在云上 | 不跑在云上 |
|----------|------------|
| 官网 `website/` | Telegram 业务后端（Telethon） |
| 授权 API（登录/卡密/心跳/版本） | 用户 session / 群发内容 / 私信列表 |
| 管理后台 `/admin/` | 桌面端本地 `data/` |
| 安装包下载 `/downloads/` | |
| PostgreSQL（授权库） | |

原则：**授权与官网上云；号池与任务留在用户电脑。**

---

## 2. 目录结构（生产）

```
/opt/paperwing/
├── config/
│   └── ports.json                 # 与仓库一致；授权默认 28180
├── website/                       # 官网静态 + downloads/
│   ├── index.html
│   ├── assets/                    # logo、config.js、favicon
│   └── downloads/                 # PaperWing-*-setup.exe
├── license-server/
│   ├── .env                       # 生产密钥（勿进 Git）
│   ├── .venv/                     # Python 虚拟环境
│   ├── docker-compose.yml         # PostgreSQL（生产应绑 127.0.0.1）
│   ├── admin/                     # 管理后台静态页
│   └── license_server/            # FastAPI 代码
└── DEPLOY_CREDENTIALS.txt         # 管理员/库密码备忘（仅 root 可读）
```

一键部署脚本（开发机执行）：`scripts/deploy_license_cloud.py`（通过环境变量传 SSH，不把密码写进仓库）。

---

## 3. PostgreSQL（数据库）

### 3.1 本地开发（仓库默认）

文件：`license-server/docker-compose.yml`

| 项 | 默认值 |
|----|--------|
| 镜像 | `postgres:16-alpine` |
| 容器名 | `paperwing-license-pg` |
| 库名 | `paperwing_license` |
| 用户 | `paperwing` |
| 密码 | `paperwing`（**仅开发**） |
| 宿主机端口 | `25432` → 容器 `5432` |
| 数据卷 | Docker volume `paperwing_pg_data` |

启动：

```bash
cd license-server
docker compose up -d
docker exec paperwing-license-pg pg_isready -U paperwing -d paperwing_license
```

连接串：

```env
DATABASE_URL=postgresql+psycopg://paperwing:paperwing@127.0.0.1:25432/paperwing_license
```

### 3.2 生产注意（必读）

1. **改强密码**：`POSTGRES_PASSWORD` 与 `DATABASE_URL` 中的密码必须一致且足够长。  
2. **只绑本机**：端口映射写成 `"127.0.0.1:25432:5432"`，**禁止** `0.0.0.0:25432` 暴露公网。  
3. **防火墙**：云安全组/本机 ufw 不必对公网开放 `25432`。  
4. **改密码后**：同步改 `/opt/paperwing/license-server/.env` 的 `DATABASE_URL`，再 `systemctl restart paperwing-license`。  
5. **数据持久化**：在 Docker volume 中；删容器不删 volume 一般数据还在；`docker compose down -v` 会**清空库**，慎用。

### 3.3 常用运维

```bash
# 状态
docker ps | grep paperwing
docker logs --tail 100 paperwing-license-pg

# 进入 psql
docker exec -it paperwing-license-pg psql -U paperwing -d paperwing_license

# 逻辑备份（示例）
docker exec paperwing-license-pg pg_dump -U paperwing paperwing_license \
  > /root/backup-paperwing-$(date +%F).sql

# 恢复（示例，先停应用再导）
# systemctl stop paperwing-license
# cat backup.sql | docker exec -i paperwing-license-pg psql -U paperwing -d paperwing_license
# systemctl start paperwing-license
```

建议：定期备份 `.sql` 到异地；保留至少最近 7 天。

---

## 4. 授权云环境变量（`.env`）

路径：

- 开发：`license-server/.env`（从 `.env.example` 复制）
- 生产：`/opt/paperwing/license-server/.env`（权限建议 `600`）

### 4.1 必填项

| 变量 | 说明 | 注意 |
|------|------|------|
| `HOST` | 监听地址 | 生产用 `127.0.0.1`（仅本机，交给 Nginx） |
| `PORT` | 监听端口 | 与 `config/ports.json` 一致，默认 `28180` |
| `DATABASE_URL` | PostgreSQL 连接串 | 驱动前缀 `postgresql+psycopg://` |
| `JWT_SECRET` | 签发会话用长随机串 | 泄露需全量重新登录 |
| `ADMIN_EMAIL` | 管理后台账号 | 首次启动自动建管理员 |
| `ADMIN_PASSWORD` | 管理后台密码 | **上线后立即改掉默认值** |
| `SMTP_HOST` / `SMTP_PORT` | 发验证码 | 当前 SpaceMail：`mail.spacemail.com:465` |
| `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | 邮箱账号 | 密码勿提交 Git、勿贴聊天 |

### 4.2 可选项

| 变量 | 说明 |
|------|------|
| `IMAP_*` | 备用，一般不必 |
| `DUJIAOPAY_*` | 支付对接，见 [`dujiaopay-integration.md`](./dujiaopay-integration.md) |

### 4.3 模板（打码）

```env
HOST=127.0.0.1
PORT=28180
DATABASE_URL=postgresql+psycopg://paperwing:强密码@127.0.0.1:25432/paperwing_license
JWT_SECRET=请换成足够长的随机串
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=强密码

SMTP_HOST=mail.spacemail.com
SMTP_PORT=465
SMTP_USER=nb@zhiyinb.cc
SMTP_PASSWORD=***
SMTP_FROM=nb@zhiyinb.cc

DUJIAOPAY_BASE_URL=https://www.dujiaopay.com
DUJIAOPAY_KEY_ID=
DUJIAOPAY_SECRET=
DUJIAOPAY_WEBHOOK_SECRET=
```

改 `.env` 后必须：

```bash
systemctl restart paperwing-license
```

---

## 5. systemd（授权进程常驻）

单元示例：`/etc/systemd/system/paperwing-license.service`

要点：

- `WorkingDirectory=/opt/paperwing/license-server`
- `Environment=PYTHONPATH=/opt/paperwing/license-server`
- `EnvironmentFile=/opt/paperwing/license-server/.env`
- `ExecStart=.../.venv/bin/python -m license_server`
- `Restart=always`

常用命令：

```bash
systemctl status paperwing-license
systemctl restart paperwing-license
journalctl -u paperwing-license -n 100 --no-pager

# 本机健康检查（不经 Nginx）
curl -fsS http://127.0.0.1:28180/health
# 期望: {"status":"ok","service":"paperwing-license"}
```

仓库根需存在 `website/`：进程通过 `PROJECT_ROOT/website` 提供官网。

---

## 6. Nginx + HTTPS

### 6.1 推荐架构（一期已用）

公网 `80/443` → Nginx → 反代到 `http://127.0.0.1:28180`（官网、API、Admin、downloads 全走 FastAPI）。

站点文件一般在：`/etc/nginx/sites-available/paperwing`（`sites-enabled` 软链）。

关键反代头：

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### 6.2 证书

```bash
certbot --nginx -d zhiyinb.cc -d www.zhiyinb.cc
certbot renew --dry-run
```

证书路径通常：`/etc/letsencrypt/live/zhiyinb.cc/`。  
到期由 certbot 定时任务自动续期；续期失败会导致 HTTPS 中断。

### 6.3 域名解析

| 主机记录 | 类型 | 指向 |
|----------|------|------|
| `@` | A | 服务器公网 IP |
| `www` | A | 同上（或 CNAME 到主域） |

解析未生效时不要跑 certbot（校验会失败）。

### 6.4 备选：静态官网 + 反代 API

见 `website/deploy.nginx.conf`（静态 root + `/auth` `/license` `/admin` `/health` 反代）。一期用「整站反代」更简单。

---

## 7. 端口与防火墙

### 7.1 生产公网

| 端口 | 用途 | 是否对公网开放 |
|------|------|----------------|
| 22 或自定义 SSH（如 12207） | 运维登录 | 建议限制来源 IP |
| 80 | HTTP / ACME / 跳转 HTTPS | ✅ |
| 443 | HTTPS | ✅ |
| 28180 | 授权进程 | ❌ 仅 127.0.0.1 |
| 25432 | PostgreSQL | ❌ 仅 127.0.0.1 |

### 7.2 本地开发端口（`config/ports.json`）

| 服务 | 端口 |
|------|------|
| 桌面业务后端 | 28147 |
| Vite | 28182 |
| Vite HMR | 28183 |
| 授权云 | 28180 |
| PostgreSQL 映射 | 25432 |

---

## 8. 桌面端与云端的配置对应关系

| 桌面侧 | 云侧 |
|--------|------|
| `.env.production` → `VITE_LICENSE_API_BASE=https://www.zhiyinb.cc` | 同域授权 API |
| 安装包内嵌业务后端（本机 28147） | **无**对应云服务 |
| 管理后台改「版本 / 下载地址」 | `GET /app/version`；官网 `website/assets/config.js` |
| 用户邮箱登录 / 卡密 | PostgreSQL 用户表与卡密表 |

发新包时务必确认打包机 `.env.production` 已是生产 HTTPS，否则用户装上后连错授权地址。

---

## 9. 运维速查

### 9.1 服务是否正常

```bash
curl -fsS https://www.zhiyinb.cc/health
curl -fsSI https://www.zhiyinb.cc/
curl -fsSI https://www.zhiyinb.cc/admin/
systemctl is-active paperwing-license nginx docker
```

### 9.2 热更新哪些要重启

| 变更 | 路径 | 重启？ |
|------|------|--------|
| 官网文案 / `config.js` | `/opt/paperwing/website/` | 否 |
| 安装包 exe | `/opt/paperwing/website/downloads/` | 否 |
| Admin 静态资源 | `/opt/paperwing/license-server/admin/` | 否 |
| Python 代码 | `license_server/` | **是** |
| `.env` / 数据库密码 | `.env` | **是** |
| Nginx 配置 | `/etc/nginx/...` | `nginx -t && systemctl reload nginx` |

### 9.3 邮件发不出

1. 检查 `.env` 中 SMTP 账号密码。  
2. `journalctl -u paperwing-license` 看报错。  
3. 确认 465 出站未被云厂商拦截。  
4. 验证码有 60 秒冷却、10 分钟有效。

### 9.4 管理后台进不去

1. 确认 `https://域名/admin/`（注意末尾路径）。  
2. 用 `.env` 里的 `ADMIN_EMAIL` / `ADMIN_PASSWORD`（或 `DEPLOY_CREDENTIALS.txt`）。  
3. 首次启动后改过密码以数据库为准。

---

## 10. 安全注意事项（清单）

- [ ] `.env`、`DEPLOY_CREDENTIALS.txt` **永不提交 Git**
- [ ] 生产 DB / Admin / JWT / SMTP 使用强密码；聊天里出现过则**轮换**
- [ ] PostgreSQL、28180 **不对公网监听**
- [ ] SSH 改密钥登录，关闭或限制密码登录；root 密码轮换
- [ ] 仅开放 80/443（及受控 SSH 端口）
- [ ] HTTPS 强制跳转；证书自动续期可用
- [ ] 定期 `pg_dump` 备份
- [ ] 服务器与本地开发库隔离，勿把生产 `.env` 拷回开发机乱提交
- [ ] 安装包只从官网 `/downloads/` 或官方渠道分发

---

## 11. 相关文件索引

| 文件 | 用途 |
|------|------|
| `license-server/docker-compose.yml` | PG 容器定义 |
| `license-server/.env.example` | 环境变量模板 |
| `config/ports.json` | 本地/默认端口 |
| `website/deploy.nginx.conf` | Nginx 备选示例 |
| `scripts/deploy_license_cloud.py` | 远程一键部署 |
| `docs/go-live-runbook.md` | 首次上线流程 |
| `docs/system-overview.md` | 全系统/发版总览 |
| `docs/dujiaopay-integration.md` | 支付（可选） |
