# Pathfinder 아키텍처

부산 교통약자(휠체어·고령자·보행보조기·시각장애인)를 위한 **자체 경로 탐색** 시스템이다.
외부 길찾기 API(ODsay·TMAP)를 쓰지 않고, OSM 보행망 + 지하철 + 버스를 하나의
멀티모달 그래프로 만들어 **ACO(개미 군집 최적화) 주력 + GA(유전 알고리즘) 보조**로
서로 다른 상위 3개 경로를 찾는다.

```
┌──────────────┐   /api/route     ┌──────────────┐  /api/search   ┌──────────────┐
│  frontend    │ ───────────────▶ │  backend     │ ─────────────▶ │  engine      │
│  React+Vite  │ ◀─────────────── │  FastAPI     │ ◀───────────── │  FastAPI     │
│  Kakao Map   │   routes[3]      │  날씨·장소·로그 │   routes[3]    │  ACO/GA 탐색  │
└──────────────┘                  └──────┬───────┘                └──────┬───────┘
                                         │                               │ corridor SQL
                                         ▼                               ▼
                                  ┌──────────────────────────────────────────┐
                                  │  PostgreSQL 16 + PostGIS                 │
                                  │  graph_nodes / graph_edges / buildings   │
                                  │  transit_routes / transit_stops          │
                                  │  route_requests / route_results (로그)     │
                                  └──────────────────────────────────────────┘
                                                      ▲
                                                      │ 오프라인 빌드 (사용자 PC)
                                  ┌──────────────────────────────────────────┐
                                  │  engine/app/pipeline/*                    │
                                  │  OSM PBF → 보행망, DEM → 경사, OSM 건물,    │
                                  │  지하철(역·출입구·엘리베이터), 버스(BIMS)     │
                                  └──────────────────────────────────────────┘
```

## 서비스

| 서비스 | 역할 | 포트 |
|---|---|---|
| `frontend/` | Kakao 지도, 프로필·조건 입력, Top 3 경로 카드 | 5173 |
| `backend/` | 장소 검색(Kakao Local), 날씨(Open-Meteo 기본 / OpenWeather 선택), 경로 오케스트레이션, 요청·결과 로그 | 8000 |
| `engine/` | 회랑(corridor) 서브그래프 추출 → 비용 모델 → ACO/GA → 다양성 선택 → 경로 특성·배지 | 8001 |
| `db` | PostGIS. 그래프 저장 + 서비스 로그 | 5432 |

엔진은 `GRAPH_SOURCE=postgis`(운영)와 `GRAPH_SOURCE=file`(개발·테스트, 그래프 번들 파일을
메모리에 적재) 두 모드를 지원한다. 두 모드는 같은 `GraphStore` 인터페이스를 구현한다.

## 요청 흐름

1. 프론트가 출발·도착 좌표, 프로필, 출발 시각, 날씨 모드(자동/수동)를 백엔드에 보낸다.
2. 백엔드가 날씨를 조회해 `WeatherContext`(체감온도·강수·풍속·PM10·폭염/한파/우천/대기 나쁨 플래그)를 만든다.
3. 백엔드가 엔진 `/api/search`를 호출한다.
4. 엔진:
   1. 출발·도착을 가장 가까운 보행 노드에 스냅한다.
   2. 타원형 회랑 안의 노드·엣지를 PostGIS에서 읽는다(대중교통 엣지는 더 넓은 회랑).
   3. 회랑 안 건물로 출발 시각 기준 건물 그림자를 계산해 보행 엣지별 `shade_ratio`를 붙인다.
   4. 프로필 + 날씨로 엣지별 일반화 비용(초 단위)을 계산한다. 하드 제약 위반 엣지는 제거한다.
   5. 도착지 기준 역방향 Dijkstra로 cost-to-go `h(v)`를 구해 ACO 휴리스틱·가지치기에 쓴다.
   6. ACO가 경로 아카이브를 만들고, GA가 아카이브를 교차·변이로 다듬는다.
   7. 아카이브에서 엣지 중복률이 낮은 상위 3개를 고른다.
   8. 각 경로의 구간(leg)·특성(경사·그늘·계단·엘리베이터·환승)·배지·주의사항을 만든다.
5. 백엔드가 요청과 결과를 로그 테이블에 남기고 프론트에 돌려준다.

## 디렉토리

```
pathfinder/
├── engine/
│   ├── app/
│   │   ├── main.py, config.py
│   │   ├── api/            # /api/search, /health
│   │   ├── graph/          # 모델, 메모리 스토어, PostGIS 스토어, 회랑, 스냅
│   │   ├── cost/           # 프로필, 날씨 컨텍스트, 엣지 비용
│   │   ├── search/         # dijkstra, aco, ga, diversity, pipeline
│   │   ├── routes/         # leg 분해, 특성, 배지, 응답 스키마
│   │   ├── features/       # DEM 고도, 태양 위치, 건물 그림자
│   │   └── pipeline/       # 오프라인 데이터 빌드 스크립트
│   └── tests/
├── backend/
│   ├── app/{main,config,database}.py, routers/, services/, models/, schemas/
│   └── tests/
├── frontend/src/{api,components,hooks,pages,types}
├── data/               # DEM, 지하철 CSV, 버스 정류장 CSV, 경계, 샘플 그래프
├── docs/               # 이 문서들
└── docker-compose.yml
```

## 데이터 원칙 (KT-10에서 계승)

- **모름 ≠ 0**: 엘리베이터·계단·경사로 정보가 없으면 `None`으로 두고 "확인 필요"로 표시한다.
  휠체어 프로필에서 확인 안 된 수직 이동은 차단하지 않고 큰 패널티 + 주의사항으로 처리한다.
- **경사는 90m DEM 지형 추정치**다. 보도 턱·역사 내부 경사가 아니다. 응답에 `elevation_resolution_m=90`을 명시한다.
- **그늘은 건물 그림자만** 계산한다(가로수·지형 그림자 제외). 높이를 모르는 건물은 층수×3.3m로 추정하고, 그것도 없으면 제외하며 `building_height_coverage`로 신뢰도를 알린다.
- 대중교통은 **시간표 없이 배차 간격(headway)** 으로 대기 시간을 근사한다. `wait_s = min(headway/2, 900)`.
