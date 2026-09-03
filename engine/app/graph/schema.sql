-- Pathfinder PostGIS 스키마. 엔진 파이프라인(load_postgis)이 적용한다.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS graph_meta (
    key   text PRIMARY KEY,
    value text NOT NULL
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id           bigint PRIMARY KEY,
    kind         text NOT NULL,
    geom         geometry(Point, 4326) NOT NULL,
    elevation_m  real,
    name         text NOT NULL DEFAULT '',
    station_id   text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS graph_nodes_geom_idx ON graph_nodes USING GIST (geom);
CREATE INDEX IF NOT EXISTS graph_nodes_kind_idx ON graph_nodes (kind);

CREATE TABLE IF NOT EXISTS graph_edges (
    id              bigint PRIMARY KEY,
    source          bigint NOT NULL,
    target          bigint NOT NULL,
    kind            text NOT NULL,
    mode            text NOT NULL DEFAULT '',
    length_m        real NOT NULL,
    time_s          real,
    grade_pct       real,
    max_grade_pct   real,
    stairs          smallint NOT NULL DEFAULT 0,
    step_count      real,
    ramp            smallint NOT NULL DEFAULT -1,
    elevator        smallint NOT NULL DEFAULT -1,
    escalator       smallint NOT NULL DEFAULT -1,
    surface         text NOT NULL DEFAULT '',
    width_m         real,
    tactile         smallint NOT NULL DEFAULT -1,
    handrail        smallint NOT NULL DEFAULT -1,
    crossing        text NOT NULL DEFAULT '',
    kerb            text NOT NULL DEFAULT '',
    lit             smallint NOT NULL DEFAULT -1,
    indoor          smallint NOT NULL DEFAULT 0,
    route_id        text NOT NULL DEFAULT '',
    route_name      text NOT NULL DEFAULT '',
    headway_s       real,
    low_floor_ratio real,
    stop_name       text NOT NULL DEFAULT '',
    geom            geometry(LineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS graph_edges_geom_idx ON graph_edges USING GIST (geom);
CREATE INDEX IF NOT EXISTS graph_edges_source_idx ON graph_edges (source);
CREATE INDEX IF NOT EXISTS graph_edges_target_idx ON graph_edges (target);

CREATE TABLE IF NOT EXISTS buildings (
    id            bigint PRIMARY KEY,
    height_m      real,
    height_source text NOT NULL DEFAULT '',
    geom          geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS buildings_geom_idx ON buildings USING GIST (geom);

CREATE TABLE IF NOT EXISTS transit_routes (
    id              text PRIMARY KEY,
    mode            text NOT NULL,
    name            text NOT NULL,
    headway_s       real,
    low_floor_ratio real,
    color           text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS transit_stops (
    id       text PRIMARY KEY,
    mode     text NOT NULL,
    name     text NOT NULL,
    node_id  bigint,
    geom     geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS transit_stops_geom_idx ON transit_stops USING GIST (geom);
