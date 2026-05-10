#!/usr/bin/env bash
# 从仓库根目录启动后端：自动设置 PYTHONPATH / CONFIG_DIR / MUSIC_DIR，并释放端口。
# 用法：
#   ./scripts/run-backend.sh              # 默认 5173 + --reload（仅监视 backend/app）
#   PORT=5174 ./scripts/run-backend.sh
#   RELOAD=0 ./scripts/run-backend.sh      # 关闭热重载（更稳，适合排查「卡死」）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-5173}"
RELOAD="${RELOAD:-1}"

for pid in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
  kill -9 "$pid" 2>/dev/null || true
done
sleep 1

export CONFIG_DIR="${CONFIG_DIR:-$ROOT/config}"
export MUSIC_DIR="${MUSIC_DIR:-$ROOT/music}"
export PYTHONPATH="$ROOT/backend"

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "缺少可执行文件: $PY（请在仓库根目录创建 .venv 并安装依赖）" >&2
  exit 1
fi

if [[ "$RELOAD" == "1" ]]; then
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
    --reload --reload-dir "$ROOT/backend/app"
else
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
