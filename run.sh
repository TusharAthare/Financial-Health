#!/usr/bin/env bash
# Starts Postgres, Redis, Django API, and Vite frontend.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PID=""
FRONTEND_PID=""
CELERY_PID=""
BACKEND_PORT=8000
FRONTEND_PORT=4200

kill_port() {
  local port=$1
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
  else
    pids=$(netstat -ano 2>/dev/null | grep ":${port} " | grep LISTENING | awk '{print $NF}' | sort -u)
  fi

  if [[ -z "$pids" ]]; then
    return 0
  fi

  for pid in $pids; do
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      echo "Stopping process $pid on port $port"
      if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        taskkill //F //PID "$pid" 2>/dev/null || true
      else
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done
  sleep 1
}

cleanup() {
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$CELERY_PID" ]] && kill "$CELERY_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

command -v docker >/dev/null || { echo "docker is required"; exit 1; }
command -v poetry >/dev/null || { echo "poetry is required"; exit 1; }
command -v npm >/dev/null || { echo "npm is required"; exit 1; }

[[ -f .env ]] || cp .env.example .env

poetry config virtualenvs.in-project true
[[ -d .venv ]] || poetry install

eval "$(poetry env activate)"

docker compose up -d db redis

for _ in $(seq 1 30); do
  docker compose exec -T db pg_isready -U postgres -d financial_health >/dev/null 2>&1 && break
  sleep 2
done
docker compose exec -T db pg_isready -U postgres -d financial_health >/dev/null 2>&1 \
  || { echo "Postgres did not start in time."; exit 1; }

for _ in $(seq 1 30); do
  docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && break
  sleep 2
done
docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG \
  || { echo "Redis did not start in time."; exit 1; }

python manage.py migrate --noinput

kill_port "$BACKEND_PORT"

celery -A api worker --loglevel=info &
CELERY_PID=$!
sleep 2
kill -0 "$CELERY_PID" 2>/dev/null || { echo "Celery worker failed to start."; exit 1; }

python manage.py runserver 0.0.0.0:"$BACKEND_PORT" &
BACKEND_PID=$!
sleep 2
kill -0 "$BACKEND_PID" 2>/dev/null || { echo "Django failed to start."; exit 1; }

kill_port "$FRONTEND_PORT"

(
  cd frontend
  [[ -d node_modules ]] || npm install
  npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "Running:"
echo "  Frontend  http://localhost:$FRONTEND_PORT"
echo "  API       http://127.0.0.1:$BACKEND_PORT"
echo "  Celery    background worker (CSV parsing)"
echo ""
echo "Ctrl+C to stop API, Celery, and frontend."
echo ""

wait "$FRONTEND_PID"
