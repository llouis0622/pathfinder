"""서비스 로그 테이블. 그래프 테이블은 엔진 파이프라인(engine/app/graph/schema.sql)이 소유한다."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RouteRequest(Base):
    __tablename__ = "route_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    origin_name: Mapped[str] = mapped_column(String(200), default="")
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lng: Mapped[float] = mapped_column(Float)
    dest_name: Mapped[str] = mapped_column(String(200), default="")
    profile: Mapped[str] = mapped_column(String(32), index=True)
    departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    weather_mode: Mapped[str] = mapped_column(String(16), default="auto")
    weather: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")     # ok | no_route | error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    results: Mapped[list["RouteResult"]] = relationship(back_populates="request", cascade="all, delete-orphan", order_by="RouteResult.rank")


class RouteResult(Base):
    __tablename__ = "route_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_requests.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(300), default="")
    badges: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cautions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_duration_min: Mapped[float] = mapped_column(Float)
    walk_distance_m: Mapped[float] = mapped_column(Float)
    transfers: Mapped[int] = mapped_column(Integer, default=0)
    generalized_cost_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)

    request: Mapped[RouteRequest] = relationship(back_populates="results")


class PlaceSearch(Base):
    __tablename__ = "place_searches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    query: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(16), default="")
    result_count: Mapped[int] = mapped_column(Integer, default=0)
