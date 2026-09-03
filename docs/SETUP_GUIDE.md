# 키 발급·데이터 확보·기입 가이드 (상세)

이 문서는 "어디서 받아서, 어느 파일의 어느 줄에 적는지"를 한 항목씩 끝까지 적었다.
요약표는 [CHECKLIST.md](CHECKLIST.md)에 있다.

## 0. 먼저 알아둘 것: 값을 적는 파일은 세 개

각 서비스는 **자기 폴더의 `.env`** 를 읽는다. 루트 `.env.example` 은 Docker Compose(Phase 5)용 통합본이라 지금은 참고만 한다.

| 서비스 | 만드는 방법 | 읽는 변수 |
|---|---|---|
| 백엔드 | `cp backend/.env.example backend/.env` | DB, 엔진 주소, Kakao REST 키, 카카오·네이버 로그인, JWT, 관리자, 날씨 |
| 엔진 | `cp engine/.env.example engine/.env` | 그래프 소스, PostGIS 주소, 탐색 예산 |
| 프론트 | `cp frontend/.env.example frontend/.env` | VWorld 키, 배경 스타일 URL |
| 파이프라인(터미널) | `.env` 없이 명령 인자 또는 셸 변수 | `BUS_SERVICE_KEY`, `--pbf`, `--postgis` |

규칙: `KEY=value` 한 줄, 따옴표 없이, `=` 양옆 공백 없이. 값을 바꾼 뒤에는 해당 서비스를 재시작한다.
`.env` 는 `.gitignore` 에 있어 커밋되지 않는다. 절대 커밋하지 않는다.

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

**어디에 기입**

- `backend/.env`
  ```
  DATABASE_URL=postgresql+asyncpg://pathfinder:pathfinder_dev@localhost:5432/pathfinder
  ```
  (백엔드는 asyncpg 드라이버라 `postgresql+asyncpg://` 접두어가 꼭 들어간다)
- `engine/.env`
  ```
  DATABASE_URL=postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder
  GRAPH_SOURCE=postgis_memory
  ```
  (엔진은 psycopg 라 접두어가 `postgresql://` 이다. `postgis_memory` 는 시작 시 전체 그래프를 메모리에 올려 빠르다)
- 비밀번호를 바꿨다면 두 줄 모두 같은 값으로 바꾼다.

**확인**: `psql "$DATABASE_URL" -c "select postgis_version();"` 가 버전을 출력하면 된다.

---

## 2. JWT 비밀키 (필수)

**받는 방법**: 직접 만든다. 터미널에서
```bash
openssl rand -base64 48
```
출력된 64자 문자열을 복사한다. (Windows PowerShell: `[Convert]::ToBase64String((1..48|%{Get-Random -Max 256}))`)

**어디에 기입**: `backend/.env`
```
JWT_SECRET=여기에_복사한_문자열
```
기본값 `change-me-in-production` 그대로 두면 누구나 세션 쿠키를 위조할 수 있으니 운영에서는 반드시 바꾼다. 값을 바꾸면 기존 로그인 세션은 모두 풀린다.

---

## 3. 관리자 비밀번호 (필수)

**받는 방법**: 직접 정한다. 16자 이상, 다른 곳에서 안 쓰는 값. `openssl rand -base64 18` 로 만들어도 좋다.

**어디에 기입**: `backend/.env`
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

**어디에 기입**: 파일 위치만 명령 인자로 준다 (환경변수 아님)
```bash
cd engine && pip install -r requirements-pipeline.txt
python -m app.pipeline.run_all --pbf ../data/raw/south-korea-latest.osm.pbf ...
```
(전체 명령은 8번 "그래프 빌드"에 있다)

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

**어디에 기입**
- 프론트 `frontend/.env`
  ```
  VITE_VWORLD_KEY=복사한_인증키
  ```
  `npm run dev` 를 다시 시작해야 반영된다 (Vite 는 시작 시 env 를 읽는다).
- (선택, 건물 실측 높이) 루트 `.env` 또는 셸 변수
  ```
  VWORLD_API_KEY=같은_인증키
  ```
  9번 빌드 명령에 `--vworld-key 같은_인증키` 를 붙이거나 셸에 `export VWORLD_API_KEY=...` 를 두면 OSM 건물 중 높이를 모르는 것을 VWorld 실측 높이로 채운다 (없어도 빌드는 된다).

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
- 어디에 기입: `backend/.env`
  ```
  KAKAO_REST_API_KEY=REST_API_키
  ```
- 확인: `curl "localhost:8000/api/place/search?query=부산역"` 의 `source` 가 `kakao` 로 나온다.

**6-b. 카카오 로그인**

1. 앱 → **제품 설정 → 카카오 로그인** → **활성화 설정 ON**
2. 같은 화면 **Redirect URI 등록** → 다음 값을 **정확히** 추가 (끝에 슬래시 없음)
   - 개발: `http://localhost:8000/api/auth/kakao/callback`
   - 운영: `https://api.pathfinder.example.com/api/auth/kakao/callback` (백엔드가 공개되는 주소 + `/api/auth/kakao/callback`)
3. **제품 설정 → 카카오 로그인 → 동의항목** → `닉네임(profile_nickname)` 필수 동의, `프로필 사진(profile_image)` 선택 동의로 설정. 이메일은 쓰지 않는다.
4. (권장) **앱 설정 → 보안 → Client Secret** → 코드 생성 → 활성화 상태 "사용함". 생성된 시크릿 복사.
5. 어디에 기입: `backend/.env`
   ```
   KAKAO_CLIENT_ID=REST_API_키          # 6-a 와 같은 값
   KAKAO_CLIENT_SECRET=생성한_시크릿     # 4번을 안 했다면 비워 둔다
   PUBLIC_BASE_URL=http://localhost:8000   # 운영에서는 https://api.pathfinder.example.com
   FRONTEND_URL=http://localhost:5173      # 로그인 후 돌아갈 주소
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
   - 네이버 로그인 Callback URL: `http://localhost:8000/api/auth/naver/callback` (운영: `https://api.pathfinder.example.com/api/auth/naver/callback`)
5. 등록 후 **Client ID**, **Client Secret** 이 보인다. 둘 다 복사.
6. 어디에 기입: `backend/.env`
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
cd engine && pip install -r requirements-pipeline.txt
python -m app.pipeline.run_all \
    --pbf ../data/raw/south-korea-latest.osm.pbf \
    --bims-cache ../data/build/bims \
    --postgis postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder
```
- 버스 없이 먼저 보려면 `--bims-cache` 를 빼도 된다 (도보+지하철만).
- GTFS 가 있으면 `--bims-cache` 대신 `--gtfs 폴더경로`.
- VWorld 키가 있으면 `--vworld-key "$VWORLD_API_KEY"` 를 붙인다 (건물 실측 높이).
- Docker 로 돌리려면: `docker compose --profile pipeline run --rm pipeline` (루트 `.env` 의 `BUS_SERVICE_KEY`, `VWORLD_API_KEY` 를 읽는다).
- 결과: `data/build/graph_bundle.npz`, `report.json`, 그리고 PostGIS 의 `graph_nodes/graph_edges/buildings` 테이블.
- 걸리는 시간: PBF 읽기 포함 10~30분 (메모리 8GB 이상 권장).

**어디에 기입**: 끝나면 `engine/.env` 를 실데이터로 바꾼다.
```
GRAPH_SOURCE=postgis_memory
DATABASE_URL=postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder
```
(`GRAPH_BUNDLE_PATH`, `BUILDINGS_PATH` 는 file 모드에서만 쓰이므로 그대로 둬도 된다)

**확인**: 엔진 재시작 후 `curl localhost:8001/health` 의 `graph.nodes` 가 수십만 단위로 나오면 실데이터다.

---

## 10. HTTPS 도메인과 운영용 주소 (운영 배포 시)

**받는 방법**: 도메인 구매(가비아·Cloudflare 등) 후 프론트·백엔드가 공개될 주소를 정한다. 예:
- 프론트 `https://pathfinder.example.com`
- 백엔드 `https://api.pathfinder.example.com` (또는 같은 도메인의 `/api` 를 리버스 프록시로 백엔드에 연결)
- 인증서는 Cloudflare, Caddy, nginx + certbot 중 편한 것으로.

**어디에 기입**: `backend/.env`
```
PUBLIC_BASE_URL=https://api.pathfinder.example.com
FRONTEND_URL=https://pathfinder.example.com
CORS_ORIGINS=https://pathfinder.example.com
COOKIE_SECURE=true
ALLOW_DEV_LOGIN=false
```
그리고 6-b, 7 의 Redirect/Callback URI 와 5 의 VWorld 서비스 URL 을 이 도메인으로 다시 등록한다.

GPS(현재 위치)는 브라우저 정책상 **HTTPS 에서만** 동작한다 (localhost 는 예외).

---

## 11. 선택 항목

**OpenWeather** (필요할 때만)
1. https://openweathermap.org → Sign up → **API keys** 탭에서 키 생성 (무료 플랜, 활성화까지 최대 2시간)
2. `backend/.env`
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

## 12. 다 채운 뒤 최종 점검 순서

1. `backend/.env`, `engine/.env`, `frontend/.env` 세 파일이 있고 위 값들이 들어갔는지 본다.
2. DB → 엔진(8001) → 백엔드(8000) → 프론트(5173) 순으로 띄운다.
3. `curl localhost:8000/health` : `engine.status` 가 `ok`.
4. 프론트에서 실제 부산 장소로 검색 → 경로 3개.
5. 카카오·네이버 로그인 → 경로 선택 → 다음 검색에 "내 취향 반영".
6. `/admin` 로그인 → 대시보드에 방금 검색이 보인다.

문제가 생기면 `backend/app` 로그와 `/admin/logs/access` 의 상태 코드부터 본다.
