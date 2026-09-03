"""경로 개인화: 사용자가 고른 경로로 학습하는 온라인 정책 (컨텍스트 밴딧 + 정책 경사).

모델
- 후보 경로 r 의 특성 φ(r) ∈ R^d 를 후보 집합 안에서 0~1 로 정규화하고 0.5 를 빼 중심화한다.
- 사용자 가중치 w 로 점수 s(r) = base(r) + w·φ(r) 를 만들고 softmax(s/τ) 가 정책 π 다.
  base(r) 는 엔진 순위(비용) 기반 사전 점수라, 학습 전에는 엔진 순위와 같다.
- 사용자가 후보 중 하나를 고르면 보상 1 로 REINFORCE 갱신:  w ← w + lr · (φ(chosen) − Σ_i π_i φ(r_i)) − λ·w
  (선택 확률 대비 실제 선택의 차이만큼 이동. 로그된 propensity 로 오프라인 IPS 평가가 가능하다.)
- 재정렬: 갱신이 ≥ MIN_UPDATES 이면 s(r) 내림차순으로 순위를 다시 매긴다. 확률 ε 로는 π 에서 표본을 뽑아
  1순위를 정하는 탐험을 하고, 그때의 propensity 를 함께 남긴다.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

FEATURES: tuple[str, ...] = (
    "duration",        # total_duration_s
    "walk",            # walk_distance_m
    "transfers",       # transfers
    "grade",           # max_grade_pct
    "stairs",          # stairs_count
    "shade",           # shade_ratio (높을수록 좋음)
    "unshaded",        # unshaded_walk_m
    "unverified",      # unverified_vertical_count
    "wait",            # wait_duration_s
    "ride_share",      # ride_duration_s / total_duration_s
)
FEATURE_LABELS: dict[str, tuple[str, str]] = {
    # (양의 가중치일 때, 음의 가중치일 때)
    "duration": ("오래 걸려도 괜찮음", "빠른 길 선호"),
    "walk": ("도보 많아도 괜찮음", "도보 적은 길 선호"),
    "transfers": ("환승 많아도 괜찮음", "환승 적은 길 선호"),
    "grade": ("경사 있어도 괜찮음", "완만한 길 선호"),
    "stairs": ("계단 있어도 괜찮음", "계단 없는 길 선호"),
    "shade": ("그늘 많은 길 선호", "그늘 신경 안 씀"),
    "unshaded": ("볕 걷기 괜찮음", "볕 걷기 피함"),
    "unverified": ("미확인 엘리베이터 괜찮음", "확인된 엘리베이터 선호"),
    "wait": ("대기 괜찮음", "대기 짧은 길 선호"),
    "ride_share": ("대중교통 위주 선호", "도보 위주 선호"),
}

LEARNING_RATE = 0.35
L2 = 0.01
TEMPERATURE = 0.5
BASE_RANK_GAP = 0.6          # 엔진 순위 간 사전 점수 차 (1순위 0, 2순위 -0.6, ...)
MIN_UPDATES = 1
EXPLORE_EPSILON = 0.1
MAX_ABS_WEIGHT = 3.0


@dataclass
class Policy:
    weights: dict[str, float] = field(default_factory=lambda: {f: 0.0 for f in FEATURES})
    updates: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "Policy":
        if not data:
            return cls()
        w = {f: float((data.get("weights") or {}).get(f, 0.0)) for f in FEATURES}
        return cls(weights=w, updates=int(data.get("updates", 0)))

    def to_dict(self) -> dict:
        return {"weights": self.weights, "updates": self.updates, "features": list(FEATURES)}

    def summary(self, threshold: float = 0.25) -> list[str]:
        """사람이 읽는 학습 요약 (|w| 가 큰 순)."""
        ranked = sorted(self.weights.items(), key=lambda kv: -abs(kv[1]))
        out: list[str] = []
        for f, w in ranked:
            if abs(w) < threshold:
                break
            pos, neg = FEATURE_LABELS[f]
            out.append(pos if w > 0 else neg)
        return out[:4]


def raw_features(route: dict[str, Any]) -> dict[str, float]:
    f = route.get("features") or {}
    total = float(f.get("total_duration_s") or 0.0)
    return {
        "duration": total,
        "walk": float(f.get("walk_distance_m") or 0.0),
        "transfers": float(f.get("transfers") or 0),
        "grade": float(f.get("max_grade_pct") or 0.0),
        "stairs": float(f.get("stairs_count") or 0),
        "shade": float(f.get("shade_ratio") or 0.0),
        "unshaded": float(f.get("unshaded_walk_m") or 0.0),
        "unverified": float(f.get("unverified_vertical_count") or 0),
        "wait": float(f.get("wait_duration_s") or 0.0),
        "ride_share": (float(f.get("ride_duration_s") or 0.0) / total) if total > 0 else 0.0,
    }


def normalized_features(routes: list[dict[str, Any]]) -> list[dict[str, float]]:
    """후보 집합 안에서 min-max 정규화 후 중심화. 후보가 모두 같으면 0."""
    raws = [raw_features(r) for r in routes]
    out: list[dict[str, float]] = []
    for i in range(len(raws)):
        out.append({})
    for name in FEATURES:
        vals = [r[name] for r in raws]
        lo, hi = min(vals), max(vals)
        for i, v in enumerate(vals):
            out[i][name] = ((v - lo) / (hi - lo) - 0.5) if hi > lo else 0.0
    return out


def _base_scores(routes: list[dict[str, Any]]) -> list[float]:
    return [-(int(r.get("rank", i + 1)) - 1) * BASE_RANK_GAP for i, r in enumerate(routes)]


def scores(policy: Policy, routes: list[dict[str, Any]]) -> list[float]:
    phis = normalized_features(routes)
    base = _base_scores(routes)
    return [b + sum(policy.weights[f] * phi[f] for f in FEATURES) for b, phi in zip(base, phis)]


def softmax(values: list[float], temperature: float = TEMPERATURE) -> list[float]:
    if not values:
        return []
    m = max(values)
    exps = [math.exp((v - m) / temperature) for v in values]
    s = sum(exps)
    return [e / s for e in exps]


def update(policy: Policy, routes: list[dict[str, Any]], chosen_id: str, lr: float = LEARNING_RATE) -> Policy:
    """사용자가 후보 중 chosen_id 를 골랐다는 신호로 정책 경사 갱신."""
    ids = [str(r.get("id")) for r in routes]
    if chosen_id not in ids or len(routes) < 2:
        return policy
    phis = normalized_features(routes)
    probs = softmax(scores(policy, routes))
    k = ids.index(chosen_id)
    new_w: dict[str, float] = {}
    for f in FEATURES:
        expected = sum(p * phi[f] for p, phi in zip(probs, phis))
        grad = phis[k][f] - expected
        w = policy.weights[f] + lr * grad - L2 * policy.weights[f]
        new_w[f] = max(-MAX_ABS_WEIGHT, min(MAX_ABS_WEIGHT, w))
    return Policy(weights=new_w, updates=policy.updates + 1)


@dataclass
class Rerank:
    routes: list[dict[str, Any]]
    applied: bool
    explored: bool
    propensities: dict[str, float]


def rerank(policy: Policy, routes: list[dict[str, Any]], rng: random.Random | None = None, epsilon: float = EXPLORE_EPSILON) -> Rerank:
    """학습된 정책으로 순위를 다시 매긴다. rank 필드를 갱신하고 원래 순위는 engine_rank 에 남긴다."""
    if policy.updates < MIN_UPDATES or len(routes) < 2:
        return Rerank(routes, False, False, {})
    rng = rng or random.Random()
    s = scores(policy, routes)
    probs = softmax(s)
    order = sorted(range(len(routes)), key=lambda i: -s[i])
    explored = False
    if epsilon > 0 and rng.random() < epsilon:
        # 정책에서 표본 하나를 뽑아 1순위로 (나머지는 점수순)
        r = rng.random()
        acc = 0.0
        pick = order[0]
        for i, p in enumerate(probs):
            acc += p
            if r <= acc:
                pick = i
                break
        order = [pick] + [i for i in order if i != pick]
        explored = True
    out: list[dict[str, Any]] = []
    for new_rank, i in enumerate(order, start=1):
        r = dict(routes[i])
        r["engine_rank"] = int(r.get("rank", i + 1))
        r["rank"] = new_rank
        r["personal_score"] = round(s[i], 3)
        out.append(r)
    return Rerank(out, True, explored, {str(routes[i].get("id")): round(probs[i], 4) for i in range(len(routes))})
