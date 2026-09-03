# 준비 체크리스트: 발급받을 키와 확보할 데이터

상세한 발급 절차와 기입 위치는 [SETUP_GUIDE.md](SETUP_GUIDE.md)에 있다.

코드가 실제로 읽는 환경변수와 파일만 적었다. 괄호 안은 어디에 넣는지(`.env` 키 이름)와 없을 때의 동작이다.

## A. 반드시 필요 (서비스가 돌아가려면)

| # | 항목 | 어디서 | 넣는 곳 | 없으면 |
|---|---|---|---|---|
| A1 | **PostgreSQL 16 + PostGIS 3** | 직접 설치 또는 Docker | `DATABASE_URL`, `POSTGRES_*` | 백엔드·엔진 postgis 모드 실행 불가 (엔진은 file 모드로 샘플만) |
| A2 | **JWT 비밀키** 32자 이상 무작위 문자열 | `openssl rand -base64 48` | `JWT_SECRET` | 기본값 그대로면 세션 위조 가능 (운영 금지) |
| A3 | **관리자 비밀번호** | 직접 생성 | `ADMIN_PASSWORD` | 관리자 페이지 전체 비활성 |
| A4 | **Geofabrik 대한민국 OSM PBF** `south-korea-latest.osm.pbf` (약 300MB) | https://download.geofabrik.de/asia/south-korea.html | `data/raw/`, `--pbf` | 보행망·건물 빌드 불가 |
| A5 | **부산 실데이터 그래프 빌드 실행** (A4 + 저장소에 있는 파일들로 `run_all`) | `python -m app.pipeline.run_all --pbf ... --postgis ...` | PostGIS 적재 | 샘플 격자 도시만 동작 |

## B. 강력 권장 (핵심 사용자 경험)

| # | 항목 | 어디서 | 넣는 곳 | 없으면 |
|---|---|---|---|---|
| B1 | **VWorld 인증키** (오픈API, 무료) + 서비스 도메인 등록 | https://www.vworld.kr → 오픈API → 인증키 발급 | `VITE_VWORLD_KEY` | 배경 지도가 OpenFreeMap(OSM) 으로 대체. 국내 건물·주소 상세도 낮음 |
| B2 | **Kakao REST API 키** (장소 이름 검색) | https://developers.kakao.com → 내 애플리케이션 → 앱 키 → REST API 키 | `KAKAO_REST_API_KEY` | 역·정류장 이름만 검색되는 로컬 색인으로 대체 (건물·상호 검색 불가) |
| B3 | **카카오 로그인** (같은 앱의 REST API 키 + Client Secret 선택) | Kakao Developers → 카카오 로그인 활성화, Redirect URI 등록 `{PUBLIC_BASE_URL}/api/auth/kakao/callback`, 동의항목 닉네임·프로필 | `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET` | 카카오 로그인 버튼 안 보임 |
| B4 | **네이버 로그인** | https://developers.naver.com → 애플리케이션 등록 → 네이버 로그인 → Callback URL `{PUBLIC_BASE_URL}/api/auth/naver/callback`, 제공 정보 별명·프로필 사진 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 로그인 버튼 안 보임 |
| B5 | **공공데이터포털 부산 BIMS 인증키(Decoding)** | https://www.data.go.kr → "부산광역시_버스정보시스템" 활용신청 | `BUS_SERVICE_KEY`, `bims_fetch --key` | 버스 노선·정류장 순서 수집 불가 → GTFS 폴더(`--gtfs`)가 없으면 버스 미포함 |
| B6 | **HTTPS 도메인** (운영) | 배포 환경 | `PUBLIC_BASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE=true` | GPS 현재 위치는 HTTPS 에서만 동작 (localhost 예외). OAuth Redirect URI 도 이 값 기준 |

## C. 선택 (있으면 좋음)

| # | 항목 | 어디서 | 넣는 곳 | 없으면 |
|---|---|---|---|---|
| C1 | **VWorld 오픈API 키** (건물 실측 높이 WFS `LT_C_BLDGINFO`) — B1 과 같은 키로 가능 | vworld.kr | `VWORLD_API_KEY` | OSM `height`/`building:levels` 기반 높이만 사용 → 그늘 정확도 하락 |
| C2 | **OpenWeather API 키** | https://openweathermap.org/api | `WEATHER_PROVIDER=openweather`, `OPENWEATHER_API_KEY` | 기본 Open-Meteo(키 불필요)로 충분 |
| C3 | **GTFS 폴더** (`routes.txt, trips.txt, stop_times.txt, stops.txt`) | 부산시/ODsay 등 GTFS 제공처 | `run_all --gtfs DIR` | BIMS(B5)로 대체 |
| C4 | **MapLibre 스타일 URL** (자체 타일 서버) | 자체 호스팅 | `VITE_BASEMAP_STYLE_URL` | VWorld/OpenFreeMap 사용 |
| C5 | **동해선·부산김해경전철 역 좌표** | 한국철도공사/부산김해경전철 공공데이터 | `data/subway/busan_subway_lines.json` 형식으로 추가 | 1~4호선만 포함 |

## D. 저장소에 이미 있는 데이터 (추가 확보 불필요)

| 파일 | 내용 | 출처 |
|---|---|---|
| `data/boundary/busan_hangjeongdong.geojson` | 부산 행정동 경계 | 행정안전부 행정동 경계 |
| `data/dem/busan_dem_clipped_90m.tif` | 부산 90m DEM (EPSG:5179) | KT-10 에서 가져옴 |
| `data/osm/busan_osm_steps_ramp_no_20260724.geojson` | 경사로 없는 계단 way | OSM 추출 |
| `data/subway/busan_subway_stations.csv` | 114역 좌표·엘리베이터 유무 | 부산교통공사 |
| `data/subway/busan_subway_accessible_exit_coordinates_20260813.csv` | 접근 가능 출입구 좌표 | OSM + 부산교통공사 |
| `data/subway/busan_subway_elevator_routes_20251231.csv` | 엘리베이터 이동경로 | 부산교통공사 |
| `data/subway/busan_subway_station_convenience_20251231.csv` | 역 편의시설 | 부산교통공사 |
| `data/subway/busan_subway_lines.json` | 1~4호선 순서·배차·속도 | 직접 정리 |
| `data/bus/busan_bus_stops_national_20251031.csv` | 부산 버스정류장 9,975개 | 국토부 전국 버스정류장 표준데이터 |
| `data/samples/grid_city.npz`, `grid_city_buildings.json` | 테스트용 샘플 격자 도시 | 합성 |

## E. 발급 후 할 일 (순서)

1. `.env` 를 만들고 A·B 항목 값을 채운다. `frontend/.env` 에는 `VITE_VWORLD_KEY` 만.
2. PostGIS 를 띄우고 `run_all --pbf data/raw/south-korea-latest.osm.pbf --bims-cache data/build/bims --postgis "$DATABASE_URL"` 로 적재한다 (BIMS 는 먼저 `bims_fetch --key` 실행).
3. 엔진을 `GRAPH_SOURCE=postgis_memory`(빠름) 또는 `postgis` 로 띄운다.
4. Kakao/Naver 콘솔에 Redirect URI, VWorld 에 서비스 도메인을 등록한다.
5. `/admin` 에 로그인해 대시보드에 검색이 쌓이는지 확인한다.

자세한 절차: [DATA_PIPELINE.md](DATA_PIPELINE.md), [MAP.md](MAP.md), [PERSONALIZATION.md](PERSONALIZATION.md), [ADMIN.md](ADMIN.md)
