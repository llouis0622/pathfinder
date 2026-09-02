# 데이터 파이프라인

그래프는 **사용자 PC에서 오프라인으로 빌드**해 PostGIS에 적재한다. 엔진은 실행 중에
외부 지도 API를 호출하지 않는다.

구현: `engine/app/pipeline/` (`python -m app.pipeline.<step>`)

## 단계

| 순서 | 모듈 (`engine/app/pipeline/`) | 입력 | 출력 |
|---|---|---|---|
| 1 | `build_walk_graph` | Geofabrik `south-korea-latest.osm.pbf`, `data/boundary/busan_hangjeongdong.geojson`, `data/osm/busan_osm_steps_ramp_no_*.geojson` | `walk.npz` (양방향 보행 엣지 + 태그 파생 속성 + 도형) |
| 2 | `build_subway` | `data/subway/*.csv`, `busan_subway_lines.json` | `subway.npz` (승강장·출입구·수직이동·환승·노선 엣지) |
| 3 | `build_bus` (+ `bims_fetch`) | `data/bus/busan_bus_stops_*.csv`, GTFS 폴더 또는 BIMS 캐시 | `bus.npz` |
| 4 | `build_buildings` | OSM PBF 건물(`height`, `building:levels`) 또는 VWorld WFS | `buildings.json` |
| 5 | `assemble` | 1~3 산출물, `data/dem/busan_dem_clipped_90m.tif` | 보행망 압축 → 병합 → 출입구·정류장 link → DEM 경사 → `graph_bundle.npz` |
| 6 | `load_postgis` | `graph_bundle.npz`, `buildings.json` | PostGIS 테이블 (COPY) |

한 번에 실행:

```bash
cd engine && pip install -r requirements-pipeline.txt
python -m app.pipeline.run_all --pbf ../data/raw/south-korea-latest.osm.pbf \
    --bims-cache ../data/build/bims \
    --postgis postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder
```

버스 노선 수집(공공데이터포털 부산 BIMS 키 필요):

```bash
python -m app.pipeline.bims_fetch --key "$BUS_SERVICE_KEY" --out ../data/build/bims \
    --ars-seed-csv ../data/bus/busan_bus_stops_national_20251031.csv
python -m app.pipeline.bims_fetch --out ../data/build/bims --report   # 응답 필드 커버리지 확인
```

`run_all` 산출물은 `data/build/`(gitignore)에 남고, `report.json`에 단계별 통계가 기록된다.
엔진은 `GRAPH_SOURCE=file`(번들), `postgis`(요청마다 SQL 회랑), `postgis_memory`(시작 시 전체 적재) 중 하나로 읽는다.

## 1. 보행망 (OSM)

`pyrosm` 으로 부산 경계 안 `network_type="walking"`을 읽는다. 유지 태그:
`highway, footway, surface, width, incline, step_count, ramp, ramp:wheelchair, handrail,
tactile_paving, kerb, crossing, lit, wheelchair, sidewalk, tunnel, bridge, level, name`.

엣지 속성 파생 규칙:

- `stairs = highway == "steps"`
- `ramp = ramp:wheelchair == "yes"` (없으면 `None`, OSM에 부산 데이터가 거의 없음)
- `width_m` = `width` 파싱(m). 없으면 `None`
- `crossing` = `footway == "crossing"` 인 경우 `crossing` 태그 값(`traffic_signals|marked|zebra|unmarked`), 아니면 `None`
- `tactile_paving`, `lit`, `handrail` = yes/no → True/False, 없으면 `None`
- `indoor = tunnel == "building_passage" or level 태그가 있고 indoor=yes`
- `highway=steps` + `ramp=no`인 way는 `data/osm/busan_osm_steps_ramp_no_20260724.geojson` 과 합쳐 `ramp=False`로 확정한다.
- 양방향 엣지를 만들고 `grade_pct` 부호를 뒤집는다.

## 2. 경사 (DEM)

`data/dem/busan_dem_clipped_90m.tif` (EPSG:5179, 90 m, KT-10에서 가져옴). 노드와 엣지 도형을 45 m 간격으로
표본화해 이중선형 보간(바다 nodata 셀은 가중치에서 제외)으로 고도를 구한다.

- `grade_pct` = 엣지 양 끝 고도차 / 길이 × 100 (부호 있음, 이동 시간 계산용)
- `max_grade_pct` = 표본 구간별 |경사| 의 최대 (급경사 차단·패널티 판정용)
- `|grade| > 35 %` 는 DEM 오차로 보고 35 %로 클리핑한다.

보행망 압축(`compact_walk_chains`)은 차수 2 노드를 지나는 동일 속성 엣지를 300 m 이하까지 합치므로,
경사는 압축 뒤에 계산해 긴 엣지 안의 급경사 구간이 `max_grade_pct`에 남도록 한다.

## 3. 지하철

- 역 좌표·엘리베이터 유무: `data/subway/busan_subway_stations.csv` (부산교통공사 공공데이터, 114역, 역코드 순서 = 노선 순서)
- 접근 가능한 출입구 좌표: `data/subway/busan_subway_accessible_exit_coordinates_20260813.csv`
  (ODbL, OSM `railway=subway_entrance` 노드 + 부산교통공사 엘리베이터 이동경로 2025-12-31)
- 엘리베이터 이동경로: `data/subway/busan_subway_elevator_routes_20251231.csv` (출입구번호가 `1,2` 처럼 복수일 수 있음)
- 노선 순서: `data/subway/busan_subway_lines.json` (1~4호선, 배차 간격, 평균 속도 9.2 m/s, 정차 30 s)

노드: `platform`(노선·역당 1개, `station_id=subway:<노선>:<역>`), `entrance`(좌표를 아는 출입구 + 역 중심 대표 출입구 1개), `route_stop`.
엣지:
- `entrance→platform vertical`: 해당 출입구가 엘리베이터 경로에 있으면 `elevator=True`, 역에 엘리베이터가 있으나 출입구 매칭이 안 되면 `None`(확인 필요), 역에 없으면 `False`
- 같은 역 이름의 다른 노선 승강장 사이 `vertical`(환승, 역 엘리베이터 유무 계승)
- `entrance ↔ 가장 가까운 walk 노드 link` (assemble 단계, 200 m 이내)
- 노선 순서대로 `platform→route_stop board`, `route_stop→platform alight`, `route_stop→route_stop ride`

동해선·부산김해경전철은 좌표 데이터가 없어 미포함이다. `busan_subway_lines.json` 형식으로 노선을 추가하면 바로 반영된다.

## 4. 버스

- 정류장: 국토부 전국 버스정류장 표준데이터 중 부산 9,975개 (`data/bus/busan_bus_stops_national_20251031.csv`, `stop_id`·`ars_no`)
- 노선-정류장 순서: 두 가지 중 하나
  1. 부산 BIMS API (`bims_fetch.py`, `BUS_SERVICE_KEY` 필요): `busInfo` → `busInfoByRouteId` 원본을 `data/build/bims/`에 저장.
     응답 필드명이 계정·버전에 따라 다를 수 있어 로더가 `bstopidx / nodeid / arsno / bstopnm / lat / lin / direction` 등 후보를 관용적으로 읽는다.
     좌표가 없는 정류장은 정류장 CSV의 `stop_id`(nodeid) 또는 `ars_no` 로 보완한다.
  2. GTFS 폴더 (`--gtfs DIR`): `routes.txt, trips.txt, stop_times.txt, stops.txt`. (route, direction)별 정류장이 가장 많은 trip을 대표로 쓰고,
     첫 정류장 출발 간격의 평균을 배차로, `arrival_time` 차이를 구간 시간으로 쓴다. `routes.txt`에 `low_floor_ratio` 열이 있으면 반영한다.
- 배차 간격 기본값 12분, 구간 시간 기본값 거리 / 5.5 m/s + 정차 20 s, 저상 비율 미상은 `None`(휠체어 프로필은 "미확인" 주의 표시).

## 5. 건물

OSM `building=*` 폴리곤. 높이: `height`(m) → `building:levels × 3.3` → 없으면 `None`(그림자 계산 제외).
VWorld `LT_C_BLDGINFO` WFS(`VWORLD_API_KEY`)를 쓰면 실측 높이로 대체한다.

## 6. PostGIS 스키마

`engine/app/graph/schema.sql` 이 정본이다. 불리언은 3진 smallint(1/0/-1=미상). 핵심 테이블:

```sql
graph_meta(key text pk, value text)
graph_nodes(id bigint pk, kind text, geom geometry(Point,4326), elevation_m real, name text, station_id text)
graph_edges(id bigint pk, source bigint, target bigint, kind text, mode text, length_m real, time_s real,
            grade_pct real, max_grade_pct real, stairs smallint, step_count real, ramp smallint, elevator smallint,
            escalator smallint, surface text, width_m real, tactile smallint, handrail smallint, crossing text,
            kerb text, lit smallint, indoor smallint, route_id text, route_name text, headway_s real,
            low_floor_ratio real, stop_name text, geom geometry(LineString,4326))
buildings(id bigint pk, height_m real, height_source text, geom geometry(Polygon,4326))
transit_routes(id text pk, mode text, name text, headway_s real, low_floor_ratio real, color text)
transit_stops(id text pk, mode text, name text, node_id bigint, geom geometry(Point,4326))
```

GIST 인덱스: `graph_nodes.geom`, `graph_edges.geom`, `buildings.geom`.

## 라이선스

- OSM: ODbL 1.0 (출처 표기 필요)
- Copernicus DEM GLO-90: 무료 이용, 출처 표기
- 부산교통공사·국토부 데이터: 공공누리 제1유형(출처 표기)
