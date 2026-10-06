"""
将官网 + 授权云部署到远程 Ubuntu 服务器。
用法（PowerShell）:
  $env:PAPERWING_SSH_HOST='209.209.50.228'
  $env:PAPERWING_SSH_PORT='12207'
  $env:PAPERWING_SSH_USER='root'
  $env:PAPERWING_SSH_PASSWORD='***'
  python scripts/deploy_license_cloud.py
"""
from __future__ import annotations

import os
import secrets
import stat
import string
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/opt/paperwing"
DOMAIN = os.environ.get("PAPERWING_DOMAIN", "zhiyinb.cc")
WWW = f"www.{DOMAIN}"

HOST = os.environ.get("PAPERWING_SSH_HOST", "")
PORT = int(os.environ.get("PAPERWING_SSH_PORT", "22"))
USER = os.environ.get("PAPERWING_SSH_USER", "root")
PASSWORD = os.environ.get("PAPERWING_SSH_PASSWORD", "")

SKIP_NAMES = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
}


def die(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    raise SystemExit(1)


def load_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def rand_alnum(n: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def connect() -> paramiko.SSHClient:
    if not HOST or not PASSWORD:
        die("请设置 PAPERWING_SSH_HOST / PAPERWING_SSH_PASSWORD")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connect {USER}@{HOST}:{PORT}")
    client.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(client: paramiko.SSHClient, cmd: str, check: bool = True, timeout: int = 600) -> str:
    print(f"[remote] {cmd[:160]}{'...' if len(cmd) > 160 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-4000:])
    if err.strip() and code != 0:
        print(err.rstrip()[-2000:], file=sys.stderr)
    if check and code != 0:
        die(f"远程命令失败 exit={code}: {cmd}")
    return out


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote: str) -> None:
    parts = remote.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def should_skip(path: Path) -> bool:
    return any(part in SKIP_NAMES for part in path.parts)


def upload_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> int:
    count = 0
    sftp_mkdirs(sftp, remote)
    for root, dirs, files in os.walk(local):
        root_path = Path(root)
        rel = root_path.relative_to(local)
        # prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES and not should_skip(Path(d))]
        remote_dir = remote if str(rel) == "." else f"{remote}/{rel.as_posix()}"
        sftp_mkdirs(sftp, remote_dir)
        for name in files:
            if name == ".env":
                continue
            lp = root_path / name
            if should_skip(lp):
                continue
            rp = f"{remote_dir}/{name}"
            sftp.put(str(lp), rp)
            mode = lp.stat().st_mode
            sftp.chmod(rp, mode & 0o777)
            count += 1
    return count


def write_remote_file(sftp: paramiko.SFTPClient, remote: str, content: str, mode: int = 0o600) -> None:
    sftp_mkdirs(sftp, str(Path(remote).parent).replace("\\", "/"))
    with sftp.file(remote, "w") as f:
        f.write(content)
    sftp.chmod(remote, mode)


def main() -> None:
    local_env = load_dotenv(ROOT / "license-server" / ".env")
    if not local_env.get("SMTP_PASSWORD"):
        die("本地 license-server/.env 缺少 SMTP_PASSWORD")

    db_pass = rand_alnum(28)
    jwt = secrets.token_urlsafe(48)
    admin_email = local_env.get("ADMIN_EMAIL") or "nb@zhiyinb.cc"
    admin_password = local_env.get("ADMIN_PASSWORD") or rand_alnum(16)

    client = connect()
    sftp = client.open_sftp()

    print("[upload] website / license-server / config")
    n1 = upload_tree(sftp, ROOT / "website", f"{REMOTE_ROOT}/website")
    n2 = upload_tree(sftp, ROOT / "license-server", f"{REMOTE_ROOT}/license-server")
    sftp_mkdirs(sftp, f"{REMOTE_ROOT}/config")
    sftp.put(str(ROOT / "config" / "ports.json"), f"{REMOTE_ROOT}/config/ports.json")
    print(f"[upload] done website={n1} license-server={n2}")

    compose = f"""services:
  postgres:
    image: postgres:16-alpine
    container_name: paperwing-license-pg
    restart: unless-stopped
    environment:
      POSTGRES_USER: paperwing
      POSTGRES_PASSWORD: {db_pass}
      POSTGRES_DB: paperwing_license
    ports:
      - "127.0.0.1:25432:5432"
    volumes:
      - paperwing_pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U paperwing -d paperwing_license"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  paperwing_pg_data:
"""
    write_remote_file(sftp, f"{REMOTE_ROOT}/license-server/docker-compose.yml", compose, 0o644)

    env_lines = {
        "HOST": "127.0.0.1",
        "PORT": "28180",
        "DATABASE_URL": f"postgresql+psycopg://paperwing:{db_pass}@127.0.0.1:25432/paperwing_license",
        "JWT_SECRET": jwt,
        "ADMIN_EMAIL": admin_email,
        "ADMIN_PASSWORD": admin_password,
        "SMTP_HOST": local_env.get("SMTP_HOST", "mail.spacemail.com"),
        "SMTP_PORT": local_env.get("SMTP_PORT", "465"),
        "SMTP_USER": local_env.get("SMTP_USER", "nb@zhiyinb.cc"),
        "SMTP_PASSWORD": local_env["SMTP_PASSWORD"],
        "SMTP_FROM": local_env.get("SMTP_FROM", "nb@zhiyinb.cc"),
        "IMAP_HOST": local_env.get("IMAP_HOST", "mail.spacemail.com"),
        "IMAP_PORT": local_env.get("IMAP_PORT", "993"),
        "DUJIAOPAY_BASE_URL": local_env.get("DUJIAOPAY_BASE_URL", "https://www.dujiaopay.com"),
        "DUJIAOPAY_KEY_ID": local_env.get("DUJIAOPAY_KEY_ID", ""),
        "DUJIAOPAY_SECRET": local_env.get("DUJIAOPAY_SECRET", ""),
        "DUJIAOPAY_WEBHOOK_SECRET": local_env.get("DUJIAOPAY_WEBHOOK_SECRET", ""),
    }
    env_text = "\n".join(f"{k}={v}" for k, v in env_lines.items()) + "\n"
    write_remote_file(sftp, f"{REMOTE_ROOT}/license-server/.env", env_text, 0o600)

    nginx_conf = f"""server {{
    listen 80;
    server_name {DOMAIN} {WWW};

    location / {{
        proxy_pass http://127.0.0.1:28180;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }}
}}
"""
    write_remote_file(sftp, "/etc/nginx/sites-available/paperwing", nginx_conf, 0o644)

    unit = f"""[Unit]
Description=PaperWing license server
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
WorkingDirectory={REMOTE_ROOT}/license-server
Environment=PYTHONPATH={REMOTE_ROOT}/license-server
EnvironmentFile={REMOTE_ROOT}/license-server/.env
ExecStart={REMOTE_ROOT}/license-server/.venv/bin/python -m license_server
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
"""
    write_remote_file(sftp, "/etc/systemd/system/paperwing-license.service", unit, 0o644)

    # credentials note for operator (server only)
    note = (
        f"domain={DOMAIN}\n"
        f"admin_email={admin_email}\n"
        f"admin_password={admin_password}\n"
        f"db_user=paperwing\n"
        f"db_password={db_pass}\n"
        f"deployed_at={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    write_remote_file(sftp, f"{REMOTE_ROOT}/DEPLOY_CREDENTIALS.txt", note, 0o600)

    sftp.close()

    print("[setup] apt / docker / nginx / certbot")
    run(
        client,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y && "
        "apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx "
        "python3-venv python3-pip curl ca-certificates",
        timeout=900,
    )
    run(client, "systemctl enable --now docker")
    run(client, "systemctl enable --now nginx")

    print("[setup] postgres")
    run(
        client,
        f"cd {REMOTE_ROOT}/license-server && docker compose down || true; "
        f"cd {REMOTE_ROOT}/license-server && docker compose up -d",
        timeout=300,
    )
    run(
        client,
        "for i in $(seq 1 30); do "
        "docker exec paperwing-license-pg pg_isready -U paperwing -d paperwing_license && exit 0; "
        "sleep 2; done; exit 1",
        timeout=120,
    )

    print("[setup] python venv + app")
    run(
        client,
        f"cd {REMOTE_ROOT}/license-server && "
        "python3 -m venv .venv && "
        ".venv/bin/pip install -U pip && "
        ".venv/bin/pip install -r requirements.txt",
        timeout=600,
    )

    run(client, "ln -sfn /etc/nginx/sites-available/paperwing /etc/nginx/sites-enabled/paperwing")
    run(client, "rm -f /etc/nginx/sites-enabled/default || true")
    run(client, "nginx -t && systemctl reload nginx")

    run(client, "systemctl daemon-reload")
    run(client, "systemctl enable --now paperwing-license")
    time.sleep(2)
    run(client, "systemctl is-active paperwing-license")
    run(client, "curl -fsS http://127.0.0.1:28180/health")

    print("[setup] HTTPS certbot")
    run(
        client,
        f"certbot --nginx -d {DOMAIN} -d {WWW} --non-interactive --agree-tos "
        f"-m {admin_email} --redirect",
        check=False,
        timeout=300,
    )
    run(client, "nginx -t && systemctl reload nginx", check=False)

    print("[smoke]")
    run(client, "curl -fsS http://127.0.0.1:28180/health")
    run(client, f"curl -fsSIL https://{WWW}/health || curl -fsSIL http://{WWW}/health || true", check=False)
    run(client, "systemctl --no-pager --full status paperwing-license | head -30", check=False)

    print("\n[DONE]")
    print(f"官网: https://{WWW}/")
    print(f"管理后台: https://{WWW}/admin/")
    print(f"健康检查: https://{WWW}/health")
    print(f"管理员邮箱: {admin_email}")
    print(f"管理员密码: （与本地 license-server/.env 的 ADMIN_PASSWORD 相同；亦见服务器 {REMOTE_ROOT}/DEPLOY_CREDENTIALS.txt）")
    print("安全提醒: 聊天里发过 root 密码，建议尽快改 SSH 密码并改用密钥登录。")
    client.close()


if __name__ == "__main__":
    main()
