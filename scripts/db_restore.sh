#!/usr/bin/env bash
# 백업 복원. 기존 객체를 지우고(--clean) 넣는다. 서비스 컨테이너는 먼저 멈춘다.
#   DATABASE_URL=postgresql://user:pw@host:5432/pathfinder scripts/db_restore.sh backups/pathfinder-20260903-120000.dump
set -euo pipefail

FILE="${1:?복원할 .dump 파일 경로가 필요합니다}"
URL="${DATABASE_URL:?DATABASE_URL 이 필요합니다}"
URL="${URL/postgresql+asyncpg:/postgresql:}"
URL="${URL/postgresql+psycopg:/postgresql:}"

read -r -p "'$URL' 에 '$FILE' 을 복원합니다. 기존 데이터가 덮어써집니다. 계속할까요? [y/N] " ans
[[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "취소"; exit 1; }

pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$URL" "$FILE"
echo "restored <- $FILE"
echo "그래프 테이블을 뺀 백업이면 파이프라인(run_all --postgis ...)으로 그래프를 다시 적재하세요."
