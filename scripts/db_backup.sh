#!/usr/bin/env bash
# PostgreSQL 백업 (pg_dump custom 형식). 오래된 백업은 KEEP_DAYS 일 뒤 지운다.
#   DATABASE_URL=postgresql://user:pw@host:5432/pathfinder scripts/db_backup.sh [백업폴더]
#   docker compose 에서: docker compose exec -T db pg_dump -U pathfinder -Fc pathfinder > backups/pathfinder-$(date +%F).dump
set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-backups}}"
KEEP_DAYS="${KEEP_DAYS:-14}"
URL="${DATABASE_URL:?DATABASE_URL 이 필요합니다 (postgresql://...)}"
# SQLAlchemy 접두어(postgresql+asyncpg://)도 받아 준다
URL="${URL/postgresql+asyncpg:/postgresql:}"
URL="${URL/postgresql+psycopg:/postgresql:}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/pathfinder-$STAMP.dump"
# 그래프 테이블(graph_*, buildings, transit_*)은 파이프라인으로 재생성할 수 있어 기본은 제외한다. 포함하려면 WITH_GRAPH=1
EXCLUDE=(--exclude-table-data='graph_*' --exclude-table-data='buildings' --exclude-table-data='transit_*')
if [[ "${WITH_GRAPH:-0}" == "1" ]]; then EXCLUDE=(); fi

pg_dump --format=custom --no-owner --no-privileges "${EXCLUDE[@]}" --file "$OUT" "$URL"
echo "backup -> $OUT ($(du -h "$OUT" | cut -f1))"
find "$BACKUP_DIR" -name 'pathfinder-*.dump' -mtime +"$KEEP_DAYS" -print -delete | sed 's/^/removed old: /' || true
