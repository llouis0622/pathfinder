"""보행·지하철·버스 그래프를 합치고 링크·경사를 붙여 최종 그래프를 만든다."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..features.elevation import Dem, enrich_elevation
from ..graph.merge import compact_walk_chains, link_transit_nodes, merge_graphs
from ..graph.model import Graph


@dataclass
class AssembleReport:
    walk_nodes_in: int
    walk_nodes_compacted: int
    nodes: int
    edges: int
    links: int
    unlinked_transit_nodes: list[int] = field(default_factory=list)
    elevation: dict | None = None


def assemble(walk: Graph, subway: Graph | None = None, bus: Graph | None = None, dem: Dem | None = None,
             compact: bool = True, link_max_m: float = 200.0) -> tuple[Graph, AssembleReport]:
    walk_in = walk.num_nodes
    compacted = 0
    if compact:
        walk, compacted = compact_walk_chains(walk)
    graph = merge_graphs([walk, subway, bus])
    graph, link_report = link_transit_nodes(graph, max_distance_m=link_max_m)
    elev = None
    if dem is not None:
        graph, elev_report = enrich_elevation(graph, dem)
        elev = asdict(elev_report)
    report = AssembleReport(walk_in, compacted, graph.num_nodes, graph.num_edges, link_report.linked, link_report.unlinked[:50], elev)
    return graph, report


def export_bundle(graph: Graph, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph.save_npz(path)
    return path
