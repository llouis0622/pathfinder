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
