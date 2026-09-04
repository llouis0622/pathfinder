# 운영 배포 (docker-compose.prod.yml)

서버 한 대(2 vCPU · 4 GB 이상)에 Docker 만 있으면 된다. 키가 하나도 없어도 뜨고, `.env` 에 키를 넣고 다시 올리면 그 기능이 켜진다.

## 1. 처음 띄우기 (3단계)

```bash
git clone https://github.com/llouis0622/pathfinder && cd pathfinder
cp .env.example .env            # 값을 채운다. 비워 둔 비밀값(JWT_SECRET·ADMIN_PASSWORD·POSTGRES_PASSWORD)은 bootstrap 이 만들어 준다
scripts/bootstrap.sh --prod     # 진단 → 빌드·기동 → (data/raw 에 PBF 가 있으면) 부산 그래프 빌드
```

- `SITE_ADDRESS` 를 비우면 `http://<서버IP>` 로 열린다. 도메인이 있으면 `SITE_ADDRESS=https://pf.example.com` 으로 두고 DNS 를 서버로 향하게 하면 Caddy 가 Let's Encrypt 인증서를 자동 발급·갱신한다 (80·443 포트 열림 필요).
- 관리자: `SITE_ADDRESS/admin`, 비밀번호는 `.env` 의 `ADMIN_PASSWORD` (bootstrap 이 출력해 준다).
- 상태 확인: `curl -s SITE_ADDRESS/health` 는 nginx 가 막으므로 컨테이너 안에서 본다 → `docker compose -f docker-compose.prod.yml exec backend python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"`.
  대시보드 상단 **설정 상태** 카드가 같은 내용을 보여 준다.

## 2. 구성

| 서비스 | 역할 | 비고 |
|---|---|---|
| `caddy` | 공개 진입점(80/443), 자동 HTTPS, gzip | `deploy/Caddyfile`, `SITE_ADDRESS` |
| `frontend` | nginx: 빌드된 정적 파일 + `/api` 리버스 프록시 | `assets/` 는 1년 캐시, `sw.js`·`index.html` 은 매번 확인 |
| `backend` | FastAPI, 시작 시 `alembic upgrade head` (`RUN_MIGRATIONS=true`) | `/metrics` 는 외부에 노출되지 않음 |
| `engine` | 경로 엔진, `GRAPH_SOURCE=auto` | PostGIS 그래프 → `data/build` 번들 → 샘플 순 |
| `db` | PostGIS 16 | 포트를 밖으로 열지 않음 |
| `backup` (`--profile ops`) | 매일 `pg_dump` → `backups/` | 그래프 표 제외, `KEEP_DAYS` 일 보관 |
| `pipeline` (`--profile pipeline`) | 부산 실데이터 빌드 | `data/raw/south-korea-latest.osm.pbf` 필요 |

프론트가 같은 오리진의 `/api` 를 부르므로 `PUBLIC_BASE_URL`·`FRONTEND_URL`·`CORS_ORIGINS` 는 모두 `SITE_ADDRESS` 하나에서 나온다.
카카오·네이버 Redirect URI 는 `SITE_ADDRESS/api/auth/{kakao|naver}/callback`, VWorld 서비스 URL 은 `SITE_ADDRESS` 로 등록한다.

## 3. 키를 나중에 넣을 때

```bash
vi .env                                              # 값 추가
docker compose -f docker-compose.prod.yml up -d --build   # 바뀐 서비스만 다시 뜬다 (VITE_* 는 프론트 이미지 재빌드)
```

프론트 키(`VITE_VWORLD_KEY`)는 빌드 시점에 들어가므로 `--build` 가 꼭 필요하다. 백엔드·엔진 키는 재시작만으로 반영된다.

## 4. 실데이터 빌드와 갱신

```bash
mkdir -p data/raw && curl -L -o data/raw/south-korea-latest.osm.pbf https://download.geofabrik.de/asia/south-korea-latest.osm.pbf
# (선택) 버스: BUS_SERVICE_KEY 를 .env 에 넣고 bims_fetch 로 data/build/bims 를 만든다 (docs/SETUP_GUIDE.md 8번)
docker compose -f docker-compose.prod.yml --profile pipeline run --rm pipeline   # PostGIS 적재 + data/build 번들
docker compose -f docker-compose.prod.yml restart engine                          # auto 가 PostGIS 그래프를 고른다
```

관리자 **데이터 품질** 화면에서 경사·건물 높이·연결성 커버리지를 확인한다. 몇 달에 한 번 PBF 를 새로 받아 같은 명령을 돌리면 갱신된다 (적재는 `replace=True` 라 무중단은 아니고, 엔진 재시작 몇 초 동안 검색이 실패할 수 있다).

## 5. 백업·복원·마이그레이션

```bash
docker compose -f docker-compose.prod.yml --profile ops up -d backup     # 매일 백업 켜기
ls backups/                                                              # pathfinder-YYYYMMDD-HHMMSS.dump
DATABASE_URL=postgresql://pathfinder:PW@localhost:5432/pathfinder scripts/db_restore.sh backups/pathfinder-....dump   # 복원 (db 포트를 잠시 열거나 컨테이너 안에서)
```

- 스키마 변경은 Alembic 리비전으로 들어오고, 백엔드가 시작할 때 자동 적용된다. 수동으로는 `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head`.
- 롤백: `git checkout <이전 태그>` → `up -d --build`. 리비전을 내려야 하면 `alembic downgrade -1`.

## 6. 업데이트

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker image prune -f
```

## 7. 운영 점검표

- `.env` 의 `JWT_SECRET`·`POSTGRES_PASSWORD` 가 기본값이 아닌지 (`python scripts/doctor.py`)
- `ALLOW_DEV_LOGIN=false`, `COOKIE_SECURE=true` (prod compose 기본값)
- Slack 웹훅을 `/admin/alerts` 에 넣고 "테스트 전송"
- `backups/` 가 매일 늘어나는지, 디스크 여유
- 대시보드 **설정 상태** 카드에 "확인 필요" 가 남아 있지 않은지
