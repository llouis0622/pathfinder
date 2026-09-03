# 데이터 파이프라인

그래프는 **사용자 PC에서 오프라인으로 빌드**해 PostGIS에 적재한다. 엔진은 실행 중에
외부 지도 API를 호출하지 않는다.

구현: `engine/app/pipeline/` (`python -m app.pipeline.<step>`)

## 단계

| 순서 | 스크립트 | 입력 | 출력 |
|---|---|---|---|
| 1 | `build_walk_graph` | Geofabrik `south-korea-latest.osm.pbf`, `data/boundary/busan_hangjeongdong.geojson` | `data/build/walk_nodes.parquet`, `walk_edges.parquet` |
| 2 | `enrich_elevation` | 1의 노드, `data/dem/busan_dem_clipped_90m.tif` | 노드 고도, 엣지 `grade_pct` |
| 3 | `build_subway` | `data/subway/*.csv` (역 좌표·출입구·엘리베이터 경로), OSM 지하철 노선 | 역·출입구·승강장 노드, `vertical`·`board`·`ride`·`alight` 엣지 |
| 4 | `build_bus` | `data/bus/busan_bus_stops_national_20251031.csv`, BIMS API(`BUS_SERVICE_KEY`) 또는 GTFS 폴더 | 정류장 노드, 노선별 `board`·`ride`·`alight` 엣지 |
| 5 | `build_buildings` | OSM PBF 건물(`building=*`, `height`, `building:levels`) 또는 VWorld WFS | `data/build/buildings.parquet` |
| 6 | `load_postgis` | 1~5 산출물 | PostGIS 테이블 |
| 7 | `export_bundle` | 1~5 산출물 | `data/build/graph_bundle.npz` (파일 모드용) |

`python -m app.pipeline.run_all --pbf path/to/south-korea-latest.osm.pbf` 로 전체를 실행한다.

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

`data/dem/busan_dem_clipped_90m.tif` (EPSG:5179, 90 m, KT-10에서 가져옴). 노드마다 이중선형 보간
(바다 nodata 셀은 가중치에서 제외)으로 고도를 구하고 `grade_pct = (z_v - z_u) / length × 100`.
90 m 격자보다 짧은 엣지에서는 인접 노드가 같은 셀에 놓여 0 %가 나올 수 있으므로,
30 m 미만 엣지는 양쪽 이웃 엣지의 평균 경사로 보정한다. `|grade| > 35 %`는 DEM 오차로 보고 클리핑한다.

## 3. 지하철

- 역 좌표·엘리베이터 유무: `data/subway/busan_subway_stations.csv` (부산교통공사 공공데이터, 114역)
- 접근 가능한 출입구 좌표: `data/subway/busan_subway_accessible_exit_coordinates_20260813.csv`
  (ODbL, OSM `railway=subway_entrance` 노드 + 부산교통공사 엘리베이터 이동경로 2025-12-31)
- 엘리베이터 이동경로: `data/subway/busan_subway_elevator_routes_20251231.csv`
- 노선 순서: `data/subway/busan_subway_lines.json` (1~4호선·동해선·부산김해경전철 역 순서, 배차 간격, 역간 평균 시간)

노드: `platform`(역당 노선당 1개), `entrance`(출입구, 좌표 있으면 개별, 없으면 역 좌표 1개).
엣지: `entrance→platform vertical`(엘리베이터 여부 = 해당 출입구가 엘리베이터 경로에 있으면 True,
역에 엘리베이터가 있으나 출입구 매칭이 안 되면 None, 역에 없으면 False),
`entrance ↔ 가장 가까운 walk 노드 link`, 노선 순서대로 `platform→route_stop board/ride/alight`.

## 4. 버스

- 정류장: 국토부 전국 버스정류장 표준데이터 중 부산 9,975개 (`data/bus/…csv`)
- 노선-정류장 순서: 부산 BIMS `busInfoByRouteId` / `busStopList` (`BUS_SERVICE_KEY` 필요)
  또는 `--gtfs <dir>` 로 GTFS(`routes.txt, trips.txt, stop_times.txt, stops.txt`) 입력
- 배차 간격: BIMS 노선 정보의 배차 시간, 없으면 12분
- 저상버스 비율: BIMS 노선 정보의 저상 여부, 없으면 `None`

엣지 시간: 정류장 간 거리 / 5.5 m/s(약 20 km/h) + 정차 20 s.

## 5. 건물

OSM `building=*` 폴리곤. 높이: `height`(m) → `building:levels × 3.3` → 없으면 `None`(그림자 계산 제외).
VWorld `LT_C_BLDGINFO` WFS(`VWORLD_API_KEY`)를 쓰면 실측 높이로 대체한다.

## 6. PostGIS 스키마

`engine/app/graph/schema.sql` 참고. 핵심 테이블:

```sql
graph_nodes(id bigint pk, kind text, geom geometry(Point,4326), elevation_m real, name text, attrs jsonb)
graph_edges(id bigint pk, source bigint, target bigint, kind text, length_m real, time_s real,
            grade_pct real, stairs bool, step_count int, ramp bool, elevator bool, escalator bool,
            surface text, width_m real, tactile bool, handrail bool, crossing text, kerb text,
            lit bool, indoor bool, route_id text, headway_s real, low_floor_ratio real,
            attrs jsonb, geom geometry(LineString,4326))
buildings(id bigint pk, height_m real, height_source text, geom geometry(Polygon,4326))
transit_routes(id text pk, mode text, name text, headway_s real, low_floor_ratio real, color text)
transit_stops(id text pk, mode text, name text, node_id bigint, geom geometry(Point,4326))
```

GIST 인덱스: `graph_nodes.geom`, `graph_edges.geom`, `buildings.geom`.

## 라이선스

- OSM: ODbL 1.0 (출처 표기 필요)
- Copernicus DEM GLO-90: 무료 이용, 출처 표기
- 부산교통공사·국토부 데이터: 공공누리 제1유형(출처 표기)
