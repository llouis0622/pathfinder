"""서비스 로그 테이블. 그래프 테이블은 엔진 파이프라인(engine/app/graph/schema.sql)이 소유한다."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_users_provider_uid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(16))              # kakao | naver | dev
    provider_user_id: Mapped[str] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(100), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserPolicy(Base):
    """사용자별 개인화 정책 (personalization.Policy 직렬화)."""

    __tablename__ = "user_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    updates: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class RouteChoice(Base):
    """사용자가 실제로 고른 경로 (RL 보상 신호)."""

    __tablename__ = "route_choices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    route_id: Mapped[str] = mapped_column(String(32))
    shown_rank: Mapped[int] = mapped_column(Integer)
    propensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    learned: Mapped[bool] = mapped_column(Boolean, default=False)


class RouteRequest(Base):
    __tablename__ = "route_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    personalized: Mapped[bool] = mapped_column(Boolean, default=False)
    explored: Mapped[bool] = mapped_column(Boolean, default=False)
    propensities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    engine_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)

    request: Mapped[RouteRequest] = relationship(back_populates="results")


class PlaceSearch(Base):
    __tablename__ = "place_searches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    query: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(16), default="")
    result_count: Mapped[int] = mapped_column(Integer, default=0)


class ApiAccessLog(Base):
    """API 접근·인증 이벤트 로그 (미들웨어가 기록)."""

    __tablename__ = "api_access_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="api", index=True)      # api | auth | admin
    method: Mapped[str] = mapped_column(String(8), default="")
    path: Mapped[str] = mapped_column(String(200), default="", index=True)
    status: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)               # 인증 이벤트 종류, 오류 메시지 등
    request_id: Mapped[str] = mapped_column(String(64), default="")               # X-Request-ID (프론트→백엔드→엔진 추적)


class EngineRun(Base):
    """검색 1건의 엔진 성능 지표 (튜닝 근거)."""

    __tablename__ = "engine_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_requests.id", ondelete="CASCADE"), index=True)
    profile: Mapped[str] = mapped_column(String(32), index=True)
    k: Mapped[int] = mapped_column(Integer, default=3)
    corridor_nodes: Mapped[int] = mapped_column(Integer, default=0)
    corridor_edges: Mapped[int] = mapped_column(Integer, default=0)
    blocked_edges: Mapped[int] = mapped_column(Integer, default=0)
    snap_origin_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    snap_destination_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    aco_iterations: Mapped[int] = mapped_column(Integer, default=0)
    aco_ants_completed: Mapped[int] = mapped_column(Integer, default=0)
    aco_ants_failed: Mapped[int] = mapped_column(Integer, default=0)
    aco_stopped_by: Mapped[str] = mapped_column(String(32), default="")
    aco_elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ga_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ga_generations: Mapped[int] = mapped_column(Integer, default=0)
    ga_elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    archive_size: Mapped[int] = mapped_column(Integer, default=0)
    routes_returned: Mapped[int] = mapped_column(Integer, default=0)
    engine_elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    backend_elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    shade_status: Mapped[str] = mapped_column(String(32), default="")
    weather_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    request: Mapped[RouteRequest] = relationship()


class PolicyUpdate(Base):
    """개인화 정책 갱신 이력 (선택 1건당 1행)."""

    __tablename__ = "policy_updates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_requests.id", ondelete="SET NULL"), nullable=True)
    route_id: Mapped[str] = mapped_column(String(32))
    shown_rank: Mapped[int] = mapped_column(Integer)
    engine_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explored: Mapped[bool] = mapped_column(Boolean, default=False)
    updates_after: Mapped[int] = mapped_column(Integer, default=0)
    weights_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weights_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Report(Base):
    """사용자 시설 제보 (엘리베이터 고장·계단·턱·통행 불가·데이터 정정)."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_requests.id", ondelete="SET NULL"), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(24), index=True)          # elevator_broken | stairs | kerb | blocked | ok | other
    note: Mapped[str] = mapped_column(Text, default="")
    place_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)   # open | accepted | rejected
    edge_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    edge_kind: Mapped[str] = mapped_column(String(16), default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")


class EdgeOverride(Base):
    """검토를 통과한 제보가 만든 엣지 속성 오버라이드. 활성이면 모든 검색에 전달된다."""

    __tablename__ = "edge_overrides"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    edge_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(24))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserPlace(Base):
    """즐겨찾기 장소 (집·직장 등). 로그인 사용자 전용, 게스트는 브라우저에 저장한다."""

    __tablename__ = "user_places"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(40))                # 집, 직장, 병원 …
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class AdminSetting(Base):
    """관리자가 화면에서 바꾸는 설정 (알림 임계 등). 키 하나에 JSON 하나."""

    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AlertEvent(Base):
    """임계 초과·복구 알림 이력 (웹훅 전송 결과 포함)."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    rule: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[str] = mapped_column(String(8), default="warn")      # warn | ok(복구) | test
    message: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str] = mapped_column(String(300), default="")
