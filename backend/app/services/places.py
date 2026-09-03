"""장소 검색: Kakao Local 키워드 검색 + 로컬 색인(지하철역·버스정류장) 보완."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from .. import http
from ..config import Settings
from ..schemas import PlaceOut

log = logging.getLogger("backend.places")
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
BUSAN_BBOX = (34.8, 128.7, 35.5, 129.4)


class LocalPlaceIndex:
    """data/subway/busan_subway_stations.csv + data/bus/*.csv 의 이름 부분 일치 색인."""

    def __init__(self, data_dir: str | Path) -> None:
        self.places: list[PlaceOut] = []
        d = Path(data_dir)
        st = d / "subway" / "busan_subway_stations.csv"
        if st.is_file():
            with open(st, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        self.places.append(PlaceOut(id=f"subway:{r['station_code']}", name=r["name"], address=r.get("address", ""),
                                                    lat=float(r["lat"]), lng=float(r["lng"]), category="지하철역", source="local"))
                    except (KeyError, ValueError):
                        continue
        for bus in sorted((d / "bus").glob("*.csv")) if (d / "bus").is_dir() else []:
            with open(bus, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        lat, lng = float(r["lat"]), float(r["lng"])
                    except (KeyError, ValueError):
                        continue
                    if not (BUSAN_BBOX[0] <= lat <= BUSAN_BBOX[2] and BUSAN_BBOX[1] <= lng <= BUSAN_BBOX[3]):
                        continue
                    self.places.append(PlaceOut(id=f"bus:{r.get('stop_id', '')}", name=r.get("name", ""), lat=lat, lng=lng,
                                                category="버스정류장", address=f"ARS {r.get('ars_no', '')}".strip(), source="local"))

    def search(self, query: str, limit: int = 10) -> list[PlaceOut]:
        q = query.strip().lower()
        if not q:
            return []
        exact = [p for p in self.places if p.name.lower() == q]
        prefix = [p for p in self.places if p.name.lower().startswith(q) and p not in exact]
        contains = [p for p in self.places if q in p.name.lower() and p not in exact and p not in prefix]
        # 지하철역 우선
        ranked = sorted(exact + prefix + contains, key=lambda p: 0 if p.category == "지하철역" else 1)
        return ranked[:limit]


_index: LocalPlaceIndex | None = None


def local_index(cfg: Settings) -> LocalPlaceIndex:
    global _index
    if _index is None:
        _index = LocalPlaceIndex(cfg.data_dir)
    return _index


async def kakao_search(cfg: Settings, query: str, lat: float | None, lng: float | None, size: int = 10) -> list[PlaceOut]:
    params: dict = {"query": query, "size": size}
    if lat is not None and lng is not None:
        params.update({"y": lat, "x": lng})
    async with http.client(timeout=5.0) as client:
        r = await client.get(KAKAO_URL, params=params, headers={"Authorization": f"KakaoAK {cfg.kakao_rest_api_key}"})
        r.raise_for_status()
        docs = r.json().get("documents", [])
    return [PlaceOut(id=f"kakao:{d['id']}", name=d["place_name"], address=d.get("road_address_name") or d.get("address_name", ""),
                     lat=float(d["y"]), lng=float(d["x"]), category=d.get("category_name", ""), source="kakao") for d in docs]


async def search_places(cfg: Settings, query: str, lat: float | None = None, lng: float | None = None) -> tuple[list[PlaceOut], str]:
    """반환: (places, source). Kakao 키가 있으면 Kakao 우선, 실패·없음이면 로컬 색인."""
    if cfg.kakao_rest_api_key:
        try:
            places = await kakao_search(cfg, query, lat, lng)
            if places:
                return places, "kakao"
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("Kakao 장소 검색 실패: %s", exc)
    return local_index(cfg).search(query), "local"
