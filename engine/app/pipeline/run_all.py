"""전체 파이프라인 CLI.

    python -m app.pipeline.run_all --pbf ../data/raw/south-korea-latest.osm.pbf \
        [--gtfs DIR | --bims-cache DIR] [--dem ../data/dem/busan_dem_clipped_90m.tif] \
        [--out ../data/build] [--postgis postgresql://...] [--skip-buildings] [--no-compact]

산출물: <out>/walk.npz, subway.npz, bus.npz, buildings.json, graph_bundle.npz, report.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from ..config import plain_postgres_url
from ..features.elevation import DEFAULT_DEM, Dem
from ..graph.model import Graph
from ..graph.store import load_buildings_json, save_buildings_json
from .assemble import assemble, export_bundle
from .build_bus import build_from_sources as build_bus
from .build_subway import build_subway_graph
from .build_walk_graph import DEFAULT_BOUNDARY, DEFAULT_UNRAMPED
from .build_walk_graph import build_from_pbf as build_walk


def main() -> None:
    parser = argparse.ArgumentParser(description="Pathfinder 그래프 빌드")
    default_pbf = Path("../data/raw/south-korea-latest.osm.pbf")
    parser.add_argument("--pbf", type=Path, default=(default_pbf if default_pbf.is_file() else None),
                        help="Geofabrik south-korea-latest.osm.pbf (기본: ../data/raw 에 있으면 사용, 없으면 <out>/walk.npz 재사용)")
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--unramped", type=Path, default=DEFAULT_UNRAMPED)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--gtfs", type=Path, default=None)
    default_bims = Path("../data/build/bims")
    parser.add_argument("--bims-cache", type=Path, default=(default_bims if default_bims.is_dir() else None),
                        help="bims_fetch 결과 폴더 (기본: ../data/build/bims 가 있으면 사용)")
    parser.add_argument("--out", type=Path, default=Path("../data/build"))
    parser.add_argument("--postgis", default=plain_postgres_url(os.environ.get("DATABASE_URL", "")),
                        help="적재할 PostGIS DSN (기본: 환경변수 DATABASE_URL, 비우면 번들만 생성)")
    parser.add_argument("--skip-subway", action="store_true")
    parser.add_argument("--skip-buildings", action="store_true")
    parser.add_argument("--no-compact", action="store_true")
    parser.add_argument("--no-dem", action="store_true")
    parser.add_argument("--vworld-key", default=os.environ.get("VWORLD_API_KEY", ""),
                        help="VWorld 오픈API 키. 주면 건물 실측 높이(LT_C_BLDGINFO)를 받아 OSM 높이를 보완한다 (환경변수 VWORLD_API_KEY)")
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    t0 = time.perf_counter()

    # 1. 보행망
    walk_path = out / "walk.npz"
    if args.pbf:
        walk, walk_report = build_walk(args.pbf, args.boundary, args.unramped)
        walk.save_npz(walk_path)
        report["walk"] = asdict(walk_report)
    elif walk_path.is_file():
        walk = Graph.load_npz(walk_path)
        report["walk"] = {"reused": str(walk_path), "nodes": walk.num_nodes, "edges": walk.num_edges}
    else:
        parser.error("--pbf 가 없고 재사용할 walk.npz 도 없습니다.")
    print(f"[walk] {report['walk']}")

    # 2. 지하철
    subway = None
    if not args.skip_subway:
        subway, sub_report = build_subway_graph()
        subway.save_npz(out / "subway.npz")
        report["subway"] = asdict(sub_report)
        print(f"[subway] {report['subway']}")

    # 3. 버스
    bus = None
    if args.gtfs or args.bims_cache:
        bus, bus_report = build_bus(args.gtfs, args.bims_cache)
        bus.save_npz(out / "bus.npz")
        report["bus"] = asdict(bus_report)
        print(f"[bus] {report['bus']}")

    # 4. 건물
    buildings_path = out / "buildings.json"
    buildings = []
    if not args.skip_buildings and args.pbf:
        from .build_buildings import build_from_pbf as build_buildings

        buildings = build_buildings(args.pbf, args.boundary)
        report["buildings"] = {"count": len(buildings), "known_height": sum(1 for b in buildings if b.height_m is not None)}
        if args.vworld_key:
            from .build_buildings import fetch_vworld_buildings, merge_vworld_heights

            bbox = (float(walk.nodes["lat"].min()), float(walk.nodes["lng"].min()), float(walk.nodes["lat"].max()), float(walk.nodes["lng"].max()))
            vworld = fetch_vworld_buildings(bbox, args.vworld_key)
            buildings, vw_report = merge_vworld_heights(buildings, vworld)
            report["buildings"]["vworld"] = vw_report
            report["buildings"]["known_height_after_vworld"] = sum(1 for b in buildings if b.height_m is not None)
        save_buildings_json(buildings_path, buildings)
        print(f"[buildings] {report['buildings']}")
    elif buildings_path.is_file():
        buildings = load_buildings_json(buildings_path)

    # 5. 조립 (압축 → 병합 → 링크 → 경사)
    dem = None if args.no_dem else Dem.load(args.dem)
    graph, asm = assemble(walk, subway, bus, dem, compact=not args.no_compact)
    report["assemble"] = asdict(asm)
    print(f"[assemble] nodes={asm.nodes} edges={asm.edges} links={asm.links} compacted={asm.walk_nodes_compacted}")
    bundle = export_bundle(graph, out / "graph_bundle.npz")
    report["bundle"] = str(bundle)

    # 6. PostGIS
    if args.postgis:
        from ..graph.postgis import connect, load_buildings, load_graph

        with connect(args.postgis) as conn:
            report["postgis"] = load_graph(conn, graph, replace=True, meta={"built_with": "run_all", "report": report})
            if buildings:
                report["postgis"]["buildings"] = load_buildings(conn, buildings, replace=True, source="osm")
        print(f"[postgis] {report['postgis']}")

    report["elapsed_s"] = round(time.perf_counter() - t0, 1)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 ({report['elapsed_s']}s) → {out}")


if __name__ == "__main__":
    main()
