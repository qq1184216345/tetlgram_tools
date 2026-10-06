#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "==> 创建虚拟环境 .venv ..."
  python3 -m venv "$VENV"
fi

PYTHON="$VENV/bin/python"

echo "==> 升级 pip ..."
"$PYTHON" -m pip install --upgrade pip

echo "==> 安装 Python 依赖 ..."
"$PYTHON" -m pip install -r "$ROOT/requirements.txt"

echo ""
echo "完成。虚拟环境: $VENV"
echo "启动后端: npm run backend"
