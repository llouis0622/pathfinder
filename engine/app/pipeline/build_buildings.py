"""건물 footprint·높이 수집.

- OSM: pyrosm get_buildings() → height / building:levels×3.3 (없으면 None: 그림자 계산 제외)
- VWorld(선택): LT_C_BLDGINFO WFS 로 실측 높이. `VWORLD_API_KEY` 필요.

    python -m app.pipeline.build_buildings --pbf ... --out ../data/build/buildings.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..graph.store import Building, save_buildings_json
from .osm_tags import parse_float, parse_height

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DEFAULT_BOUNDARY = DATA_DIR / "boundary" / "busan_hangjeongdong.geojson"
VWORLD_URL = "https://api.vworld.kr/req/data"
VWORLD_LAYER = "LT_C_BLDGINFO"


def _polygons(geom) -> list:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


def buildings_from_frame(gdf, id_start: int = 1) -> list[Building]:
    """GeoDataFrame(geometry + height / building:levels 열) → Building 목록."""
    out: list[Building] = []
    bid = id_start
    cols = set(gdf.columns)
    for row in gdf.itertuples(index=False):
        tags = {c: getattr(row, c, None) for c in ("height", "building:levels") if c in cols}
        if "building:levels" not in cols and "building_levels" in cols:
            tags["building:levels"] = getattr(row, "building_levels", None)
        height, _ = parse_height(tags)
        for poly in _polygons(getattr(row, "geometry", None)):
            if poly.area <= 0:
                continue
            footprint = [(float(y), float(x)) for x, y in poly.exterior.coords]
            holes = [[(float(y), float(x)) for x, y in ring.coords] for ring in poly.interiors]
            out.append(Building(id=bid, height_m=height, footprint=footprint, holes=holes))
            bid += 1
    return out


def build_from_pbf(pbf_path: Path, boundary_path: Path = DEFAULT_BOUNDARY) -> list[Building]:
    import geopandas as gpd
    from pyrosm import OSM

    boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326").geometry.union_all()
    osm = OSM(str(pbf_path), bounding_box=boundary, keep_metadata=False)
    gdf = osm.get_buildings(extra_attributes=["height", "building:levels"])
    if gdf is None or gdf.empty:
        return []
    gdf = gdf.rename(columns={"building:levels": "building_levels"})
    return buildings_from_frame(gdf)


def fetch_vworld(bbox: tuple[float, float, float, float], key: str, page_size: int = 1000, max_pages: int = 50) -> list[dict]:
    """VWorld 건물 WFS (GeoJSON features). bbox = (min_lat, min_lng, max_lat, max_lng)."""
    import httpx

    min_lat, min_lng, max_lat, max_lng = bbox
    features: list[dict] = []
    with httpx.Client(timeout=30.0) as client:
        for page in range(1, max_pages + 1):
            params = {
                "service": "data", "request": "GetFeature", "data": VWORLD_LAYER, "key": key, "format": "json", "crs": "EPSG:4326",
                "geomFilter": f"BOX({min_lng},{min_lat},{max_lng},{max_lat})", "columns": "ufid,height,bldrgst_pk",
                "size": page_size, "page": page,
            }
            resp = client.get(VWORLD_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("response", {}).get("result", {})
            batch = result.get("featureCollection", {}).get("features", [])
            features.extend(batch)
            if len(batch) < page_size:
                break
    return features


def buildings_from_vworld_features(features: list[dict], id_start: int = 1) -> list[Building]:
    from shapely.geometry import shape

    out: list[Building] = []
    bid = id_start
    for f in features:
        props = f.get("properties") or {}
        height = parse_float(props.get("height"))
        if height is not None and height <= 0:
            height = None
        for poly in _polygons(shape(f["geometry"])):
            out.append(Building(id=bid, height_m=height,
                                footprint=[(float(y), float(x)) for x, y in poly.exterior.coords],
                                holes=[[(float(y), float(x)) for x, y in r.coords] for r in poly.interiors]))
            bid += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="건물 footprint·높이 수집")
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--out", type=Path, default=Path("../data/build/buildings.json"))
    args = parser.parse_args()
    buildings = build_from_pbf(args.pbf, args.boundary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    save_buildings_json(args.out, buildings)
    known = sum(1 for b in buildings if b.height_m is not None)
    print(json.dumps({"buildings": len(buildings), "known_height": known}), "->", args.out)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- VWorld 실측 높이 병합
def bbox_cells(bbox: tuple[float, float, float, float], step_deg: float = 0.05) -> list[tuple[float, float, float, float]]:
    """WFS 페이지 한도를 넘지 않도록 bbox 를 격자 셀로 나눈다. (min_lat, min_lng, max_lat, max_lng)"""
    min_lat, min_lng, max_lat, max_lng = bbox
    cells: list[tuple[float, float, float, float]] = []
    lat = min_lat
    while lat < max_lat:
        lng = min_lng
        while lng < max_lng:
            cells.append((lat, lng, min(lat + step_deg, max_lat), min(lng + step_deg, max_lng)))
            lng += step_deg
        lat += step_deg
    return cells


def fetch_vworld_buildings(bbox: tuple[float, float, float, float], key: str, step_deg: float = 0.05,
                           fetch=None, id_start: int = 10_000_000) -> list[Building]:
    """bbox 를 셀로 나눠 VWorld 건물을 모두 받는다. ufid 로 중복을 제거한다. fetch 는 테스트용 주입점."""
    fetch = fetch or fetch_vworld
    seen: set[str] = set()
    features: list[dict] = []
    for cell in bbox_cells(bbox, step_deg):
        for f in fetch(cell, key):
            uid = str((f.get("properties") or {}).get("ufid") or "")
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            features.append(f)
    return buildings_from_vworld_features(features, id_start=id_start)


def merge_vworld_heights(osm: list[Building], vworld: list[Building], max_dist_m: float = 15.0) -> tuple[list[Building], dict]:
    """OSM 건물 중 높이를 모르는 것에 가장 가까운 VWorld 건물(중심점 거리 ≤ max_dist_m) 높이를 채우고,
    OSM 과 겹치지 않는 VWorld 건물은 그대로 추가한다."""
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree

    from ..graph.geo import haversine_m

    if not vworld:
        return list(osm), {"filled": 0, "added": 0, "vworld": 0}
    vw_polys = [Polygon([(lng, lat) for lat, lng in b.footprint]) for b in vworld]
    tree = STRtree(vw_polys)
    merged: list[Building] = []
    filled = 0
    used: set[int] = set()
    for b in osm:
        poly = Polygon([(lng, lat) for lat, lng in b.footprint])
        hits = tree.query(poly, predicate="intersects")
        used.update(int(i) for i in hits)
        if b.height_m is None and len(hits) > 0:
            c = poly.centroid
            best = None
            for i in hits:
                v = vworld[int(i)]
                if v.height_m is None:
                    continue
                vc = vw_polys[int(i)].centroid
                d = float(haversine_m(c.y, c.x, vc.y, vc.x))
                if d <= max_dist_m and (best is None or d < best[0]):
                    best = (d, v.height_m)
            if best is not None:
                b = Building(id=b.id, height_m=best[1], footprint=b.footprint, holes=b.holes)
                filled += 1
        merged.append(b)
    added = 0
    for i, v in enumerate(vworld):
        if i in used:
            continue
        merged.append(v)
        added += 1
    return merged, {"filled": filled, "added": added, "vworld": len(vworld)}
