# 키 발급·데이터 확보·기입 가이드 (상세)

이 문서는 "어디서 받아서, 어느 파일의 어느 줄에 적는지"를 한 항목씩 끝까지 적었다.
요약표는 [CHECKLIST.md](CHECKLIST.md)에 있다.

## 0. 먼저 알아둘 것: 값을 적는 파일은 루트 `.env` 하나

```bash
cp .env.example .env        # 저장소 루트
```

백엔드·엔진·프론트·파이프라인·Docker Compose 가 **모두 이 파일을 읽는다**. 아래 항목의 "어디에 기입" 은 전부 이 파일의 해당 줄이다.
(서비스 폴더에 따로 `backend/.env` 같은 파일을 두면 그 값이 우선하지만, 보통은 필요 없다.)

- `DATABASE_URL` 은 한 줄만 쓴다. 엔진(psycopg)·백엔드(asyncpg)가 드라이버 접두어를 알아서 맞춘다.
- 키가 없는 항목은 비워 둔다. 그 기능만 축소 동작한다(표는 [CHECKLIST.md](CHECKLIST.md) "없으면" 열).
- 다 적었으면 `python scripts/doctor.py` 로 확인하고, 서비스를 다시 올린다 (`scripts/bootstrap.sh` 또는 `docker compose up -d --build`).
  관리자 대시보드의 **설정 상태** 카드가 같은 점검을 보여 준다.

규칙: `KEY=value` 한 줄, 따옴표 없이, `=` 양옆 공백 없이. `.env` 는 `.gitignore` 에 있어 커밋되지 않는다. 절대 커밋하지 않는다.

---

## 1. PostgreSQL + PostGIS (필수)

**받는 방법 (둘 중 하나)**

- Docker (권장, 한 줄):
  ```bash
  docker run -d --name pathfinder-db -p 5432:5432 \
    -e POSTGRES_DB=pathfinder -e POSTGRES_USER=pathfinder -e POSTGRES_PASSWORD=pathfinder_dev \
    postgis/postgis:16-3.4
  ```
- 직접 설치: PostgreSQL 16 설치 후 `CREATE EXTENSION postgis;` 를 DB에서 실행. 사용자·DB 이름은 위와 맞추면 예시 값을 그대로 쓸 수 있다.

**어디에 기입**: 루트 `.env`
```
POSTGRES_PASSWORD=pathfinder_dev
DATABASE_URL=postgresql://pathfinder:pathfinder_dev@db:5432/pathfinder     # Compose 용. 컨테이너 없이 로컬이면 db → localhost
GRAPH_SOURCE=auto
```
- 접두어는 `postgresql://` 하나로 충분하다. 엔진과 백엔드가 각자 드라이버에 맞게 바꿔 읽는다.
- `GRAPH_SOURCE=auto` 는 PostGIS 에 그래프가 있으면 그것을, 없으면 `data/build` 의 빌드 산출물을, 그것도 없으면 샘플 격자 도시를 쓴다. 9번 빌드 뒤에 따로 바꿀 것이 없다.
- 운영(`docker-compose.prod.yml`)에서는 `POSTGRES_PASSWORD` 만 보고 `DATABASE_URL` 을 조합하므로 비밀번호 한 줄만 바꾸면 된다.

**확인**: `psql "$DATABASE_URL" -c "select postgis_version();"` 가 버전을 출력하면 된다.

---

## 2. JWT 비밀키 (필수)

**받는 방법**: 직접 만든다. 터미널에서
```bash
openssl rand -base64 48
```
출력된 64자 문자열을 복사한다. (Windows PowerShell: `[Convert]::ToBase64String((1..48|%{Get-Random -Max 256}))`)

**어디에 기입**: 루트 `.env`
```
JWT_SECRET=여기에_복사한_문자열
```
기본값 그대로 두면 누구나 세션 쿠키를 위조할 수 있으니 운영에서는 반드시 바꾼다. (`scripts/bootstrap.sh` 는 비어 있으면 자동으로 만들어 준다.) 값을 바꾸면 기존 로그인 세션은 모두 풀린다.

---

## 3. 관리자 비밀번호 (필수)

**받는 방법**: 직접 정한다. 16자 이상, 다른 곳에서 안 쓰는 값. `openssl rand -base64 18` 로 만들어도 좋다.

**어디에 기입**: 루트 `.env` (비워 두면 `scripts/bootstrap.sh` 가 만들어 출력한다)
```
ADMIN_PASSWORD=정한_비밀번호
ADMIN_SESSION_HOURS=12
ADMIN_LOGIN_MAX_FAILURES=5
ADMIN_LOGIN_LOCKOUT_S=300
```
비워 두면 `/admin` 이 "관리자 기능이 꺼져 있어요" 화면만 보인다.

**확인**: 백엔드 재시작 후 브라우저에서 `http://localhost:5173/admin` → 비밀번호 입력 → 대시보드.

---

## 4. Geofabrik 대한민국 OSM PBF (필수, 보행망·건물 원천)

**받는 방법**
1. https://download.geofabrik.de/asia/south-korea.html 접속
2. "south-korea-latest.osm.pbf" 링크 클릭 (약 300MB, 가입 불필요)
3. 파일을 저장소의 `data/raw/` 폴더에 둔다 (폴더가 없으면 만든다. 이 폴더는 gitignore 되어 있다)
   ```bash
   mkdir -p data/raw
   curl -L -o data/raw/south-korea-latest.osm.pbf https://download.geofabrik.de/asia/south-korea-latest.osm.pbf
   ```

**어디에 기입**: 기입할 것 없음. `data/raw/south-korea-latest.osm.pbf` 에 두면 파이프라인이 기본값으로 찾는다 (9번 참고).

---

## 5. VWorld 인증키 (강력 권장, 배경 지도 + 건물 높이)

**받는 방법**
1. https://www.vworld.kr 회원가입 → 로그인
2. 상단 메뉴 **오픈API → 인증키 발급** (또는 마이페이지 → 오픈API 인증키)
3. **인증키 발급 신청** 클릭
   - 서비스명: `Pathfinder` (아무거나)
   - 서비스 URL: 개발 중이면 `http://localhost:5173`, 운영이면 실제 도메인 (예: `https://pathfinder.example.com`).
     **여기 적은 도메인에서만 타일이 나온다.** 개발·운영 도메인이 둘 다 필요하면 키를 두 개 발급하거나 나중에 URL을 수정한다.
   - 활용 용도: "교통약자 보행 경로 안내 서비스의 배경 지도 및 건물 정보"
   - 활용 API: **2D 지도(WMTS/WMS)** 와 **데이터 API(WFS)** 를 함께 체크 (하나의 키로 둘 다 된다)
4. 승인되면 목록에 인증키(영숫자 32자 안팎)가 보인다. 복사.

**어디에 기입**: 루트 `.env`
```
VITE_VWORLD_KEY=복사한_인증키        # 배경 지도 (프론트 빌드 시점에 들어간다 → npm run dev 재시작 / prod 는 --build)
VWORLD_API_KEY=같은_인증키           # (선택) 파이프라인이 OSM 건물 중 높이를 모르는 것을 VWorld 실측 높이로 채운다
```

**확인**: 프론트를 띄우고 지도가 회색이 아니라 국내 지도(건물 윤곽·동 이름)로 보이면 된다. 회색이면 브라우저 콘솔에서 `api.vworld.kr` 요청이 401/403 인지 본다 → 도메인 불일치가 대부분이다.

---

## 6. Kakao Developers 앱 (장소 검색 + 카카오 로그인)

하나의 앱에서 두 가지를 한 번에 설정한다.

**앱 만들기**
1. https://developers.kakao.com 로그인 → **내 애플리케이션 → 애플리케이션 추가하기**
2. 앱 이름 `Pathfinder`, 회사명 아무거나 → 저장
3. 앱 클릭 → **앱 키** 탭에 네 가지 키가 보인다. 우리가 쓰는 건 **REST API 키** 하나다. (JavaScript 키는 더 이상 쓰지 않는다)

**6-a. 장소 검색용 REST API 키**

- 별도 활성화 필요 없음. **앱 설정 → 플랫폼 → Web** 에 사이트 도메인을 등록해 두면 좋다 (`http://localhost:5173`, 운영 도메인).
- 어디에 기입: 루트 `.env`
  ```
  KAKAO_REST_API_KEY=REST_API_키
  ```
- 확인: `curl "localhost:8000/api/place/search?query=부산역"` 의 `source` 가 `kakao` 로 나온다.

**6-b. 카카오 로그인**

1. 앱 → **제품 설정 → 카카오 로그인** → **활성화 설정 ON**
2. 같은 화면 **Redirect URI 등록** → 다음 값을 **정확히** 추가 (끝에 슬래시 없음)
   - 개발: `http://localhost:8000/api/auth/kakao/callback`
   - 운영: `https://pathfinder.example.com/api/auth/kakao/callback` (`SITE_ADDRESS` + `/api/auth/kakao/callback`. 운영 compose 는 프론트와 API 가 같은 도메인이다)
3. **제품 설정 → 카카오 로그인 → 동의항목** → `닉네임(profile_nickname)` 필수 동의, `프로필 사진(profile_image)` 선택 동의로 설정. 이메일은 쓰지 않는다.
4. (권장) **앱 설정 → 보안 → Client Secret** → 코드 생성 → 활성화 상태 "사용함". 생성된 시크릿 복사.
5. 어디에 기입: 루트 `.env`
   ```
   KAKAO_CLIENT_ID=REST_API_키          # 6-a 와 같은 값
   KAKAO_CLIENT_SECRET=생성한_시크릿     # 4번을 안 했다면 비워 둔다
   PUBLIC_BASE_URL=http://localhost:8000   # 개발. 운영 compose 는 SITE_ADDRESS 에서 자동으로 채운다
   FRONTEND_URL=http://localhost:5173      # 개발. 운영은 위와 같음
   ```
   `PUBLIC_BASE_URL + /api/auth/kakao/callback` 이 2번에 등록한 값과 글자 하나까지 같아야 한다.
6. 확인: 프론트 우상단 **로그인 → 카카오로 로그인** → 동의 → 닉네임이 보이면 성공. `KOE006` 오류는 Redirect URI 불일치, `KOE101` 은 앱 키 오류다.

---

## 7. 네이버 로그인

1. https://developers.naver.com 로그인 → **Application → 애플리케이션 등록**
2. 애플리케이션 이름 `Pathfinder`
3. **사용 API**: `네이버 로그인` 선택 → 제공 정보에서 **별명(필수)**, **프로필 사진(선택)** 체크. 이메일·이름은 불필요.
4. **로그인 오픈 API 서비스 환경**: `PC 웹` 추가
   - 서비스 URL: `http://localhost:5173` (운영: 프론트 도메인)
   - 네이버 로그인 Callback URL: `http://localhost:8000/api/auth/naver/callback` (운영: `SITE_ADDRESS/api/auth/naver/callback`)
5. 등록 후 **Client ID**, **Client Secret** 이 보인다. 둘 다 복사.
6. 어디에 기입: 루트 `.env`
   ```
   NAVER_CLIENT_ID=복사한_Client_ID
   NAVER_CLIENT_SECRET=복사한_Client_Secret
   ```
7. 확인: 로그인 메뉴에 **네이버로 로그인** 이 나타나고 동의 후 별명이 보이면 성공. 네이버는 개발 단계에서 **등록한 계정만 로그인 가능** 하니, 테스트 계정은 "멤버 관리 → 테스터 ID" 에 추가한다. 검수 통과 전까지는 그렇다.

---

## 8. 공공데이터포털 부산 BIMS 인증키 (버스 노선·정류장 순서)

**받는 방법**
1. https://www.data.go.kr 회원가입 → 로그인
2. 검색창에 **부산광역시_버스정보시스템** 검색 → 오픈API 항목 클릭 (제공기관 부산광역시, 노선정보·정류소별 경유노선 등)
3. **활용신청** → 활용목적 "교통약자 경로 안내 서비스의 버스 노선 데이터 구축", 상세기능 전부 체크 → 신청. 보통 즉시 또는 1~2일 내 승인.
4. **마이페이지 → 오픈API → 개발계정 상세보기** → **일반 인증키(Decoding)** 를 복사한다. (Encoding 키가 아니라 **Decoding** 키다. `%` 가 들어 있는 쪽이 Encoding 이다)

**어디에 기입**: 파이프라인은 명령 인자로 받는다. 셸 변수에 넣어 두면 편하다.
```bash
export BUS_SERVICE_KEY='복사한_Decoding_키'
cd engine
python -m app.pipeline.bims_fetch --key "$BUS_SERVICE_KEY" --out ../data/build/bims \
    --ars-seed-csv ../data/bus/busan_bus_stops_national_20251031.csv
python -m app.pipeline.bims_fetch --out ../data/build/bims --report     # 수집 결과 확인
```
루트 `.env` 의 `BUS_SERVICE_KEY=` 줄에 적어 두어도 된다 (Compose 에서 쓸 예정).

**확인**: `data/build/bims/` 에 노선별 JSON 이 쌓이고 `--report` 가 노선 수·정류장 수를 출력한다. 하루 호출 한도(보통 10,000건)를 넘으면 다음 날 이어서 실행하면 캐시된 노선은 건너뛴다.

---

## 9. 그래프 빌드 실행 (부산 실데이터 적재)

4번(PBF)과 8번(BIMS 캐시)이 준비되면 한 번 실행한다. 저장소에 이미 있는 경계·DEM·지하철·정류장 파일은 자동으로 쓰인다.

```bash
# Docker (권장): 루트 .env 의 DATABASE_URL·BUS_SERVICE_KEY·VWORLD_API_KEY 를 읽는다
docker compose --profile pipeline run --rm pipeline && docker compose restart engine
# 또는 scripts/bootstrap.sh 가 data/raw 에 PBF 가 있으면 자동으로 돌린다

# 컨테이너 없이: 기본값이 data/raw 의 PBF, data/build/bims, 환경변수 DATABASE_URL 을 잡으므로 인자가 없어도 된다
cd engine && pip install -r requirements-pipeline.txt
set -a; source ../.env; set +a         # DATABASE_URL 의 호스트가 db 면 localhost 로 바꿔 둔다
python -m app.pipeline.run_all
```
- 버스 없이 먼저 보려면 `data/build/bims` 가 없어도 된다 (도보+지하철만).
- GTFS 가 있으면 `--gtfs 폴더경로`.
- 결과: `data/build/graph_bundle.npz`, `report.json`, 그리고 PostGIS 의 `graph_nodes/graph_edges/buildings` 테이블.
- 걸리는 시간: PBF 읽기 포함 10~30분 (메모리 8GB 이상 권장).

**어디에 기입**: 없음. `GRAPH_SOURCE=auto` 인 엔진이 재시작 때 PostGIS 그래프를 찾아 자동으로 쓴다.

**확인**: 엔진 재시작 후 `curl localhost:8001/health` 의 `graph.nodes` 가 수십만 단위이고 `sample` 이 `false` 면 실데이터다. 관리자 **데이터 품질** 화면에서 커버리지를 본다.

---

## 10. HTTPS 도메인과 운영용 주소 (운영 배포 시)

**받는 방법**: 도메인 구매(가비아·Cloudflare 등) 후 A 레코드를 서버 IP 로 향하게 한다. 프론트와 API 는 같은 도메인(`/api`)을 쓴다.
인증서는 운영 compose 의 Caddy 가 자동으로 받는다(80·443 포트가 열려 있어야 한다).

**어디에 기입**: 루트 `.env`
```
SITE_ADDRESS=https://pathfinder.example.com
```
`docker-compose.prod.yml` 이 이 값으로 `PUBLIC_BASE_URL`·`FRONTEND_URL`·`CORS_ORIGINS` 를 채우고 `COOKIE_SECURE=true`, `ALLOW_DEV_LOGIN=false` 를 기본으로 둔다.
그리고 6-b, 7 의 Redirect/Callback URI 와 5 의 VWorld 서비스 URL 을 이 도메인으로 다시 등록한다. 배포 절차는 [DEPLOY.md](DEPLOY.md).

GPS(현재 위치)는 브라우저 정책상 **HTTPS 에서만** 동작한다 (localhost 는 예외).

---

## 11. 선택 항목

**OpenWeather** (필요할 때만)
1. https://openweathermap.org → Sign up → **API keys** 탭에서 키 생성 (무료 플랜, 활성화까지 최대 2시간)
2. 루트 `.env`
   ```
   WEATHER_PROVIDER=openweather
   OPENWEATHER_API_KEY=키
   ```
   기본 `open_meteo` 는 키가 필요 없고 시간별 예보까지 되므로 보통 이 항목은 건너뛴다.

**GTFS 폴더** (BIMS 대신)
- `routes.txt, trips.txt, stop_times.txt, stops.txt` 가 든 폴더를 `data/raw/gtfs/` 에 두고 9번에서 `--gtfs ../data/raw/gtfs`.

**동해선·부산김해경전철**
- 역 좌표를 구하면 `data/subway/busan_subway_lines.json` 에 노선 항목을 추가하고 `busan_subway_stations.csv` 형식으로 역을 추가한다. 형식은 기존 1호선 항목을 그대로 따라 하면 된다.

---

### 11-b. Slack 알림 웹훅 (선택, 운영 권장)

임계를 넘으면(엔진 다운, 오류율, 경로 없음 비율, 엔진 p95, 서버 5xx, 미처리 제보) Slack 채널로 알린다.

1. https://api.slack.com/apps → **Create New App** → From scratch → 워크스페이스 선택
2. 왼쪽 **Incoming Webhooks** → Activate 켜기 → **Add New Webhook to Workspace** → 채널 선택
3. 생성된 `https://hooks.slack.com/services/T…/B…/…` 를 복사
4. 기입: 둘 중 하나
   - 관리자 화면 `/admin/alerts` → 웹훅 URL 붙여넣기 → 저장 → **테스트 전송** (DB 에 저장, 재배포해도 유지)
   - 또는 `.env` 의 `ALERT_WEBHOOK_URL=` 에 넣기 (화면에서 저장한 값이 있으면 그쪽이 우선)
5. 임계값은 같은 화면의 "규칙·임계" 표에서 바꾼다. 형식을 JSON 으로 두면 Discord·Teams·자체 서버로도 받을 수 있다.

## 12. 다 채운 뒤 최종 점검 순서

1. `python scripts/doctor.py` 에 ❌ 가 없는지 본다 (🟡 는 축소 동작이라 뜨는 데는 지장 없다).
2. `scripts/bootstrap.sh` (개발) 또는 `scripts/bootstrap.sh --prod` (운영).
3. `curl localhost:8000/health` : `engine.status` 가 `ok`, `features.missing` 이 비어 있음. 관리자 대시보드 **설정 상태** 카드도 같은 내용.
4. 프론트에서 실제 부산 장소로 검색 → 경로 3개.
5. 카카오·네이버 로그인 → 경로 선택 → 다음 검색에 "내 취향 반영".
6. `/admin` 로그인 → 대시보드에 방금 검색이 보인다.

문제가 생기면 `backend/app` 로그와 `/admin/logs/access` 의 상태 코드부터 본다.
