#!/bin/sh
# 백엔드 컨테이너 시작: (선택) DB 마이그레이션 → 서버
set -e
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "[entrypoint] alembic upgrade head"
  # create_all 로 만들어진 기존 DB(alembic_version 없음)는 먼저 현재 리비전으로 표시한다
  if ! alembic current 2>/dev/null | grep -q '[0-9a-f]'; then
    python - <<'PY' || true
import asyncio, sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
async def main():
    eng = create_async_engine(settings.database_url)
    async with eng.connect() as c:
        names = await c.run_sync(lambda conn: sa.inspect(conn).get_table_names())
    await eng.dispose()
    raise SystemExit(0 if "route_requests" in names and "alembic_version" not in names else 1)
asyncio.run(main())
PY
    if [ $? -eq 0 ]; then echo "[entrypoint] existing schema without alembic_version → stamp head"; alembic stamp head; fi
  fi
  alembic upgrade head
fi
exec "$@"
