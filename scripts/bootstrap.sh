#!/usr/bin/env bash
# 처음 띄우기: .env 준비(비밀값 자동 생성) → 진단 → Docker Compose 기동 → (PBF 가 있으면) 부산 실데이터 빌드
#   scripts/bootstrap.sh          # 개발용 (docker-compose.yml, vite dev, http://localhost:5173)
#   scripts/bootstrap.sh --prod   # 운영용 (docker-compose.prod.yml, Caddy, http(s)://SITE_ADDRESS)
#   scripts/bootstrap.sh --prod --no-pipeline
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE=dev; PIPELINE=auto
for a in "$@"; do case "$a" in --prod) MODE=prod ;; --no-pipeline) PIPELINE=no ;; --pipeline) PIPELINE=yes ;; *) echo "usage: $0 [--prod] [--pipeline|--no-pipeline]"; exit 2 ;; esac; done
COMPOSE=(docker compose); [ "$MODE" = prod ] && COMPOSE=(docker compose -f docker-compose.prod.yml)

# 1. .env
if [ ! -f .env ]; then cp .env.example .env; echo "[bootstrap] .env 를 만들었어요 (.env.example 복사)"; fi
setvar() {  # 비어 있는 값만 채운다
  local key="$1" val="$2"
  if grep -qE "^${key}=$" .env; then sed -i.bak "s|^${key}=$|${key}=${val}|" .env && rm -f .env.bak; echo "[bootstrap] ${key} 자동 생성"; fi
}
gen() { if command -v openssl >/dev/null; then openssl rand -base64 "$1" | tr -d '\n=/+' | cut -c1-"$2"; else head -c 64 /dev/urandom | base64 | tr -d '\n=/+' | cut -c1-"$2"; fi; }
grep -qE "^JWT_SECRET=(change-me-to-a-long-random-string)?$" .env && sed -i.bak "s|^JWT_SECRET=.*$|JWT_SECRET=$(gen 48 64)|" .env && rm -f .env.bak && echo "[bootstrap] JWT_SECRET 자동 생성"
setvar ADMIN_PASSWORD "$(gen 18 20)"
if [ "$MODE" = prod ]; then
  grep -qE "^POSTGRES_PASSWORD=(pathfinder_dev)?$" .env && sed -i.bak "s|^POSTGRES_PASSWORD=.*$|POSTGRES_PASSWORD=$(gen 24 32)|" .env && rm -f .env.bak && echo "[bootstrap] POSTGRES_PASSWORD 자동 생성 (DATABASE_URL 은 compose 가 조합)"
  grep -q "^SITE_ADDRESS=" .env || printf '\n# 공개 주소. 비우면 http://<서버IP>, https://도메인 을 넣으면 Caddy 가 인증서 자동 발급\nSITE_ADDRESS=\n' >> .env
fi
echo "[bootstrap] 관리자 비밀번호: $(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"

# 2. 진단
python3 scripts/doctor.py || true

# 3. 기동
"${COMPOSE[@]}" up -d --build
echo "[bootstrap] 기동 완료"

# 4. 실데이터 (PBF 가 있고 아직 빌드 산출물이 없을 때)
if [ "$PIPELINE" != no ] && ls data/raw/*.osm.pbf >/dev/null 2>&1 && { [ "$PIPELINE" = yes ] || [ ! -f data/build/graph_bundle.npz ]; }; then
  echo "[bootstrap] OSM PBF 발견 → 부산 그래프 빌드 (수십 분 걸릴 수 있어요)"
  "${COMPOSE[@]}" --profile pipeline run --rm pipeline
  "${COMPOSE[@]}" restart engine
fi

# 5. 안내
if [ "$MODE" = prod ]; then
  ADDR="$(grep '^SITE_ADDRESS=' .env | cut -d= -f2-)"; ADDR="${ADDR:-http://<서버IP>}"
  echo "[bootstrap] 서비스 $ADDR  · 관리자 $ADDR/admin  · 상태: curl -s ${ADDR}/api/../health"
else
  echo "[bootstrap] 서비스 http://localhost:5173  · 관리자 http://localhost:5173/admin  · 상태: curl -s localhost:8000/health"
fi
echo "[bootstrap] 키를 .env 에 추가한 뒤에는  ${COMPOSE[*]} up -d --build  로 다시 띄우면 반영돼요 (관리자 대시보드 '설정 상태' 카드에서 확인)"
