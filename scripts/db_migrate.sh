#!/usr/bin/env bash
# Alembic 마이그레이션 적용. 백엔드 폴더에서 DATABASE_URL 을 읽는다.
#   DATABASE_URL=postgresql+asyncpg://... scripts/db_migrate.sh            # upgrade head
#   scripts/db_migrate.sh stamp                                             # create_all 로 만든 기존 DB 를 현재 리비전으로 표시
#   scripts/db_migrate.sh revision "add foo column"                         # 모델 변경 후 새 리비전 자동 생성
set -euo pipefail
cd "$(dirname "$0")/../backend"

case "${1:-upgrade}" in
  upgrade)  alembic upgrade head ;;
  stamp)    alembic stamp head ;;
  revision) alembic revision --autogenerate -m "${2:?메시지}" ;;
  history)  alembic history --verbose ;;
  current)  alembic current ;;
  *) echo "usage: $0 [upgrade|stamp|revision <msg>|history|current]"; exit 1 ;;
esac
