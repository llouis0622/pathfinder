#!/usr/bin/env bash
# E2E 용 엔진(8001)·백엔드(8000) 를 샘플 격자 + SQLite 로 띄운다. CI 와 로컬(npm run e2e) 이 같이 쓴다.
#   scripts/e2e_up.sh start   # 백그라운드로 띄우고 /health 가 될 때까지 기다린다
#   scripts/e2e_up.sh stop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${E2E_RUN_DIR:-$ROOT/.e2e}"
PY="${PYTHON:-python}"
mkdir -p "$RUN"

start() {
  ( cd "$ROOT/engine" && GRAPH_SOURCE=file GRAPH_BUNDLE_PATH=../data/samples/grid_city.npz BUILDINGS_PATH=../data/samples/grid_city_buildings.json \
      nohup "$PY" -m uvicorn app.main:app --port 8001 > "$RUN/engine.log" 2>&1 & echo $! > "$RUN/engine.pid" )
  ( cd "$ROOT/backend" && DATABASE_URL="sqlite+aiosqlite:///$RUN/e2e.db" ENGINE_URL=http://127.0.0.1:8001 ADMIN_PASSWORD="${E2E_ADMIN_PASSWORD:-admin-demo-1234}" \
      ALLOW_DEV_LOGIN=true JWT_SECRET=e2e-secret-not-for-production-0123456789 ALERT_ENABLED=false LOG_RETENTION_DAYS=0 WEATHER_PROVIDER=none KAKAO_REST_API_KEY= \
      nohup "$PY" -m uvicorn app.main:app --port 8000 > "$RUN/backend.log" 2>&1 & echo $! > "$RUN/backend.pid" )
  for i in $(seq 1 60); do
    if curl -fsS -m 3 --noproxy "*" http://127.0.0.1:8001/health >/dev/null 2>&1 && curl -fsS -m 5 --noproxy "*" http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "engine + backend ready"; return 0
    fi
    sleep 1
  done
  echo "servers did not become healthy"; tail -n 40 "$RUN"/*.log; return 1
}

stop() {
  for s in engine backend; do
    [ -f "$RUN/$s.pid" ] && kill "$(cat "$RUN/$s.pid")" 2>/dev/null || true
    rm -f "$RUN/$s.pid"
  done
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  *) echo "usage: $0 start|stop"; exit 2 ;;
esac
