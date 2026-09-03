# 지도

카카오맵·네이버지도 SDK 없이 **MapLibre GL JS** 로 지도를 그린다. 배경 지도 위에 우리 그래프(보도·경사·계단·턱·시설·정류장)를
벡터 타일로 얹고, 확대했을 때만 보여 준다. 축소하면 배경 지도만 남는다.

- 프론트: `frontend/src/components/MapView.tsx`(렌더러), `frontend/src/lib/maplayers.ts`(배경 선택·레이어 정의·경로 GeoJSON, 순수 함수)
- 엔진: `engine/app/tiles.py`(타일 인코딩·그늘), `GET /api/tiles/{z}/{x}/{y}.mvt`, `GET /api/shade`
- 백엔드: `/api/tiles/*`, `/api/shade` 를 엔진으로 프록시 (접근 로그에서는 제외)

## 배경 지도

| 설정 | 동작 |
|---|---|
| `VITE_VWORLD_KEY` 있음 | 국토교통부 VWorld 일반 지도(WMTS 래스터). 건물 윤곽·동 이름·도로명주소가 국내 지도 수준으로 상세하다. [vworld.kr](https://www.vworld.kr) 에서 무료 발급 후 서비스 도메인을 등록해야 한다 |
| 없음 | OpenFreeMap `liberty` 스타일(OSM 벡터, 키 불필요). 도심 밖 건물 커버리지는 낮다 |
| `VITE_BASEMAP_STYLE_URL` | MapLibre 스타일 URL 을 직접 지정 (자체 호스팅 OSM 타일 등) |

배경 스타일을 받아오지 못하면(오프라인·키 오류) 8초 안에 빈 회색 배경으로 바꾸고 우리 레이어와 경로는 그대로 띄운다.
WebGL 이 없는 환경에서는 SVG 약식 지도(`SchematicMap`)로 대체한다.

## 그래프 레이어 (벡터 타일)

엔진이 `edges`·`facilities`·`stops` 세 레이어를 MVT 로 만든다. 줌 14 미만은 빈 타일(204)이다.

| 레이어 | 도형 | 속성 |
|---|---|---|
| `edges` | LineString (walk·link·vertical) | `kind, mode, grade, max_grade, stairs, ramp, elevator, escalator, width, surface, crossing, kerb, tactile, handrail, indoor, route_name, name, steps, length` (3진 속성은 1/0/-1) |
| `facilities` | Point (엣지 중점, 수직 이동은 시작점) | `type` = stairs·elevator·escalator·vertical·kerb·crossing, `verified`, `handrail`, `ramp`, `tactile`, `name`, `steps` |
| `stops` | Point (stop·platform·entrance 노드) | `kind`, `name` |

- 메모리 스토어(파일·postgis_memory): 엣지별 bbox 색인을 한 번 만든 뒤 `mapbox-vector-tile` 로 인코딩
- PostGIS 스토어: `ST_TileEnvelope` + `ST_AsMVTGeom` + `ST_AsMVT` 한 번의 SQL. GIST 인덱스가 있으므로 부산 전체 규모도 타일 단위로 빠르다

프론트 레이어와 줌 게이트 (`maplayers.ts`):

| 오버레이 | 켜지는 레이어 | 최소 줌 |
|---|---|---|
| 기본 | 옅은 보행망, 시설 점, 정류장 | 15 (라벨 16~17) |
| 경사 | 보행 엣지를 `max_grade` 로 색칠 (3% 검정 → 6% 회색 → 10% 주황 → 그 이상 빨강) | 15 |
| 그늘 | 보행 엣지를 실시간 그늘 비율로 색칠 (볕 연회색 → 그늘 검정) | 16 |
| 시설 | 보행망 + 계단 엣지 빨간 점선 강조 + 시설 점·라벨 | 15 |

줌이 최소 줌보다 낮으면 "지도를 확대하면 … 표시돼요" 안내만 띄우고 배경 지도만 보인다.

## 실시간 그늘

그늘은 태양 위치에 따라 바뀌므로 타일에 굽지 않는다. 그늘 오버레이가 켜지고 줌 16 이상이면 지도를 움직일 때마다
화면 범위와 출발 시각(검색 결과의 `departure_at`, 없으면 지금)으로 `GET /api/shade?min_lat&min_lng&max_lat&max_lng&at` 를 호출한다.
엔진은 범위 안의 보행 엣지와 주변 300m 건물로 `edge_shade_ratios` 를 계산해 `{edge_id: 0~1}` 을 돌려주고,
프론트는 `setFeatureState` 로 엣지 색을 바꾼다. 한 변 3.5km 를 넘는 범위는 422 로 거부한다.
그늘 오버레이에는 시각 슬라이더(06:00~20:00, 30분 단위)가 있어 "오후 3시엔 어디가 그늘인지" 미리 볼 수 있다. 기본은 출발 시각(검색 전에는 지금)이다.

## 현재 위치(GPS)

MapLibre `GeolocateControl` 이 브라우저 Geolocation API 로 위치를 받아 파란 점과 정확도 원을 그린다.
위치를 받으면 "내 위치에서 출발" 버튼이 나타나고, 누르면 출발지가 `현재 위치` 로 채워진다.
출발지 입력창의 위치 아이콘도 같은 일을 한다. 운영에서는 HTTPS 가 필요하다(localhost 는 예외).

## 경로 표시

- 선택 경로: 구간(leg)별 색(도보 검정 점선, 지하철 노선색, 버스 진회색). 경사·그늘 오버레이에서는 도보 세그먼트를 값으로 칠한다
- 나머지 후보: 회색 선. 클릭하면 선택이 바뀐다
- 출발·도착 핀은 HTML 마커. 검색 패널·바텀시트가 덮는 영역만큼 여백을 두고 `fitBounds` 한다

## 환경변수

```
# frontend/.env
VITE_VWORLD_KEY=            # 비우면 OpenFreeMap
VITE_BASEMAP_STYLE_URL=     # 선택
```

엔진·백엔드는 추가 설정이 없다. 카카오 REST API 키(`KAKAO_REST_API_KEY`)는 장소 이름 검색에만 쓰인다.
