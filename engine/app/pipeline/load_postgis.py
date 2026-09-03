"""그래프 번들(npz)과 건물(json)을 PostGIS에 적재한다.

    python -m app.pipeline.load_postgis --bundle ../data/build/graph_bundle.npz \
        --buildings ../data/build/buildings.json --dsn postgresql://pathfinder:pathfinder_dev@localhost:5432/pathfinder
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..graph.model import Graph
from ..graph.postgis import connect, load_buildings, load_graph
from ..graph.store import load_buildings_json


def main() -> None:
    parser = argparse.ArgumentParser(description="PostGIS 적재")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--buildings", type=Path, default=None)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--keep", action="store_true", help="기존 데이터를 지우지 않고 추가")
    args = parser.parse_args()
    graph = Graph.load_npz(args.bundle)
    with connect(args.dsn) as conn:
        result = load_graph(conn, graph, replace=not args.keep, meta={"bundle": str(args.bundle)})
        if args.buildings and args.buildings.is_file():
            result["buildings"] = load_buildings(conn, load_buildings_json(args.buildings), replace=not args.keep)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
