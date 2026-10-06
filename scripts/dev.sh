#!/usr/bin/env bash
# 纸翼 (PaperWing) 开发环境一键启动 (macOS / Linux)
# 用法: ./scripts/dev.sh
#       ./scripts/dev.sh --backend-only

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_ONLY=false
SKIP_SETUP=false

for arg in "$@"; do
  case "$arg" in
    --backend-only) BACKEND_ONLY=true ;;
    --skip-setup)   SKIP_SETUP=true ;;
  esac
done

step()  { echo -e "\n==> $1"; }
ok()    { echo "[OK] $1"; }
warn()  { echo "[!] $1"; }

echo ""
echo "  纸翼 开发环境启动"
echo "  项目目录: $ROOT"
echo ""

step "检查 Node.js"
command -v node >/dev/null || { echo "未找到 Node.js，请先安装 Node.js 20+"; exit 1; }
ok "Node $(node -v)"

step "检查 Python"
command -v python3 >/dev/null || command -v python >/dev/null || { echo "未找到 Python 3.10+"; exit 1; }
ok "Python $(python3 --version 2>/dev/null || python --version)"

if [ "$SKIP_SETUP" = false ]; then
  step "检查前端依赖"
  if [ ! -d node_modules ]; then
    warn "node_modules 不存在，正在 npm install ..."
    npm install
  fi
  ok "前端依赖就绪"

  step "检查 Python 虚拟环境"
  if [ ! -f .venv/bin/python ]; then
    warn "虚拟环境不存在，正在 setup:python ..."
    bash scripts/setup-python.sh
  fi
  ok "Python 虚拟环境就绪 (.venv)"
fi

BACKEND_PORT=28147
FRONTEND_PORT=28182
LICENSE_PORT=28180
if [ -f config/ports.json ]; then
  BACKEND_PORT=$(python3 -c "import json; print(json.load(open('config/ports.json'))['backend']['port'])" 2>/dev/null || echo 28147)
  FRONTEND_PORT=$(python3 -c "import json; print(json.load(open('config/ports.json'))['frontend']['port'])" 2>/dev/null || echo 28182)
  LICENSE_PORT=$(python3 -c "import json; print(json.load(open('config/ports.json'))['license']['port'])" 2>/dev/null || echo 28180)
fi

LICENSE_PID=""
cleanup() {
  if [ -n "${LICENSE_PID}" ] && kill -0 "$LICENSE_PID" 2>/dev/null; then
    step "停止授权服务 (PID $LICENSE_PID)"
    kill "$LICENSE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

start_license_server() {
  step "启动授权服务 (127.0.0.1:$LICENSE_PORT)"
  if command -v docker >/dev/null 2>&1; then
    (cd "$ROOT/license-server" && docker compose up -d >/dev/null 2>&1) || warn "docker compose 跳过"
  else
    warn "未找到 Docker，请确保 PostgreSQL 已按 license-server/.env 可用"
  fi
  "$ROOT/.venv/bin/python" -m pip install -q -r "$ROOT/license-server/requirements.txt" || true
  export PYTHONPATH="$ROOT/license-server"
  (cd "$ROOT/license-server" && "$ROOT/.venv/bin/python" -m license_server) &
  LICENSE_PID=$!
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$LICENSE_PORT/health" >/dev/null 2>&1; then
      ok "授权服务就绪  http://127.0.0.1:$LICENSE_PORT"
      return 0
    fi
    sleep 0.5
  done
  warn "授权服务健康检查超时，登录可能失败"
}

if [ "$BACKEND_ONLY" = true ]; then
  step "仅启动 Python 后端 (127.0.0.1:$BACKEND_PORT)"
  echo "健康检查: http://127.0.0.1:$BACKEND_PORT/health"
  export PAPERWING_DATA="$ROOT/data"
  export TELEGRAM_TOOLS_DATA="$PAPERWING_DATA"
  npm run backend
  exit 0
fi

start_license_server

step "启动开发环境 (Tauri + Vite + Python 后端)"
echo ""
echo "  授权云     http://127.0.0.1:$LICENSE_PORT"
echo "  后端 API   http://127.0.0.1:$BACKEND_PORT/health"
echo "  前端 Dev   http://localhost:$FRONTEND_PORT"
echo ""
echo "  Tauri 会自动拉起 Python 后端，按 Ctrl+C 退出"
echo ""

npm run tauri dev
