"""탐색 파이프라인: 스냅 → 회랑 → 그늘 → 비용 → h(v) → 시드 → ACO → GA → Top K → 경로 구성."""
from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

import numpy as np

from ..cost.model import compute_costs, route_cost
from ..cost.profiles import get_profile
from ..cost.weather import WeatherContext
from ..features.shade import edge_shade_ratios
from ..features.solar import KST
from ..graph.corridor import CorridorSpec
from ..graph.store import GraphStore, SnapError
from ..routes.builder import assign_badges, build_route
from ..routes.schemas import SearchMetadata, SearchRequest, SearchResponse
from .aco import ACOParams, AntColony
from .common import Adjacency
from .dijkstra import cost_to_go, penalty_k_shortest, shortest_path
from .diversity import select_diverse
from .ga import GAParams, GeneticRefiner


class NoRouteError(ValueError):
    pass


def search_routes(
    store: GraphStore,
    request: SearchRequest,
    aco_params: ACOParams | None = None,
    ga_params: GAParams | None = None,
) -> SearchResponse:
    started = time.perf_counter()
    profile = get_profile(request.profile)
    weather = request.weather or WeatherContext.none()
    opts = request.options
    aco_p = aco_params or ACOParams()
    ga_p = ga_params or GAParams()
    if opts.time_budget_s is not None:
        aco_p = replace(aco_p, time_budget_s=opts.time_budget_s * 0.7)
        ga_p = replace(ga_p, time_budget_s=opts.time_budget_s * 0.3)
    if opts.aco_iterations is not None:
        aco_p = replace(aco_p, iterations=opts.aco_iterations)
    if opts.aco_ants is not None:
        aco_p = replace(aco_p, ants=opts.aco_ants)
    if opts.ga_generations is not None:
        ga_p = replace(ga_p, generations=opts.ga_generations)
    if opts.seed is not None:
        aco_p = replace(aco_p, seed=opts.seed)
        ga_p = replace(ga_p, seed=opts.seed)

    # 1. 스냅
    try:
        o = store.nearest_walk_node(request.origin.lat, request.origin.lng)
        d = store.nearest_walk_node(request.destination.lat, request.destination.lng)
    except SnapError as exc:
        raise NoRouteError(str(exc)) from exc
    if o.node_id == d.node_id:
        raise NoRouteError("출발지와 도착지가 같은 보행 노드로 스냅됩니다.")

    # 2. 회랑
    spec = CorridorSpec(o.lat, o.lng, d.lat, d.lng)
    sub = store.corridor(spec)
    if o.node_id not in sub.id_to_index or d.node_id not in sub.id_to_index:
        raise NoRouteError("회랑 추출 후 출발·도착 노드가 없습니다.")
    o_idx = sub.id_to_index[o.node_id]
    d_idx = sub.id_to_index[d.node_id]

    # 3. 그늘 (출발 시각이 없으면 지금)
    departure_at = request.departure_at or datetime.now(KST)
    buildings = store.buildings_in(spec.bbox(spec.walk_axis_m))
    shade, shade_info = edge_shade_ratios(sub, buildings, departure_at)

    # 4. 비용, 5. cost-to-go
    prefs = request.preferences
    cost = compute_costs(sub, profile, weather, shade, avoid_slope=prefs.avoid_slope, prefer_shade=prefs.prefer_shade,
                         shade_available=(shade_info.status == "computed"))
    h = cost_to_go(sub, cost.cost, d_idx)
    if not np.isfinite(h[o_idx]):
        raise NoRouteError(f"{profile.label} 조건으로 통과 가능한 경로가 없습니다 (차단 엣지 {cost.n_blocked}개).")
    adj = Adjacency.build(sub, cost.cost)

    def rc(edges: list[int]) -> float:
        return route_cost(edges, cost, sub)

    # 6. 시드
    seeds: list[list[int]] = []
    best = shortest_path(adj, o_idx, d_idx)
    if best is None:
        raise NoRouteError("최단 경로를 찾지 못했습니다.")
    seeds.append(best)
    seeds.extend(penalty_k_shortest(adj, o_idx, d_idx, k=3))

    # 7. ACO, 8. GA
    aco = AntColony(adj, h, o_idx, d_idx, rc, aco_p).run(seeds)
    archive = aco.archive
    ga_meta: dict = {"enabled": False}
    if opts.use_ga and ga_p.generations > 0:
        ga = GeneticRefiner(adj, o_idx, d_idx, rc, ga_p).run(archive)
        archive = ga.archive
        ga_meta = {"enabled": True, "generations": ga.generations, "offspring_valid": ga.offspring_valid,
                   "offspring_invalid": ga.offspring_invalid, "elapsed_ms": round(ga.elapsed_s * 1000, 1),
                   "best_cost": (round(ga.best.cost, 1) if ga.best else None)}

    # 9. 다양성 Top K
    lengths = sub.edges["length_m"].astype(float).tolist()
    chosen = select_diverse(archive, lengths, k=opts.k)

    # 10. 경로 구성
    routes = [
        build_route(sub, entry.edges, cost, shade, entry.cost, entry.origin, rank, f"route_{rank}")
        for rank, entry in enumerate(chosen, start=1)
    ]
    assign_badges(routes, profile, weather, shade_available=(shade_info.status == "computed"))

    metadata = SearchMetadata(
        profile=profile.id, profile_label=profile.label, weather_flags=weather.active_flags(),
        departure_at=departure_at.isoformat(), preferences=prefs.model_dump(),
        corridor_nodes=sub.num_nodes, corridor_edges=sub.num_edges, blocked_edges=cost.n_blocked,
        snap_origin_m=round(o.distance_m, 1), snap_destination_m=round(d.distance_m, 1),
        shade_status=shade_info.status, shade_note=shade_info.note, solar_elevation_deg=shade_info.solar_elevation_deg,
        building_height_coverage=(None if shade_info.coverage is None else round(shade_info.coverage, 3)),
        aco={"iterations": aco.iterations, "ants_completed": aco.ants_completed, "ants_failed": aco.ants_failed,
             "stopped_by": aco.stopped_by, "elapsed_ms": round(aco.elapsed_s * 1000, 1),
             "best_cost": (round(aco.best.cost, 1) if aco.best else None), "seed_cost": round(rc(best), 1)},
        ga=ga_meta, archive_size=len(archive), elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return SearchResponse(routes=routes, metadata=metadata)
