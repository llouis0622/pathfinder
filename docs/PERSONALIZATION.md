# 개인화 (강화학습 기반 경로 재정렬)

로그인한 사용자가 실제로 고른 경로를 보상 신호로 삼아, 다음 검색부터 그 사람의 취향에 맞게
추천 순위를 바꾼다. 엔진(ACO+GA)은 여전히 후보 3개와 기본 순위를 만들고, 개인화는 그 위에서
**순위만** 바꾼다. 안전 제약(계단 차단·경사 한계 등)은 엔진 비용 모델에 있으므로 개인화가 이를 무너뜨리지 못한다.

구현: `backend/app/services/personalization.py`, 저장: `user_policies`, `route_choices`

## 문제 정의: 컨텍스트 밴딧

- 컨텍스트: 한 번의 검색에서 제시된 후보 경로 집합 {r₁, r₂, r₃}
- 행동: 사용자가 고른 경로 하나
- 보상: 고른 경로 1, 나머지 0 (이후 실제 이용 완료·평점 등으로 확장 가능)
- 정책 π(r | 후보) = softmax(s(r) / τ), τ = 0.5

## 특성 φ(r)

후보 집합 안에서 min-max 정규화 후 0.5 를 빼 중심화한다 (후보끼리의 상대 비교만 학습).

| 특성 | 원천 |
|---|---|
| duration | 총 소요시간 |
| walk | 도보 거리 |
| transfers | 환승 수 |
| grade | 최대 경사 |
| stairs | 계단 수 |
| shade | 그늘 비율 |
| unshaded | 그늘 없는 도보 |
| unverified | 미확인 엘리베이터 수 |
| wait | 대기 시간 |
| ride_share | 탑승 시간 비율 |

## 점수와 학습

```
s(r) = base(r) + w · φ(r)          base: 엔진 순위 사전점수 (1순위 0, 2순위 −0.6, 3순위 −1.2)
π    = softmax(s / τ)
갱신 (REINFORCE, 보상 1):  w ← clip( w + lr · (φ(chosen) − Σᵢ πᵢ φ(rᵢ)) − λ·w , ±3 )
        lr = 0.35, λ = 0.01
```

학습 전(w = 0)에는 엔진 순위가 그대로다. 사용자가 엔진 1순위가 아닌 경로를 고를수록
그 경로가 가진 특성 방향으로 w 가 이동하고, 다음 검색에서 같은 특성을 가진 후보가 위로 올라간다.

## 재정렬과 탐험

- `updates ≥ 1` 이면 s(r) 내림차순으로 `rank` 를 다시 매기고 원래 순위는 `engine_rank` 에 남긴다.
- 확률 ε = 0.1 로 π 에서 표본을 뽑아 1순위로 놓는 탐험을 한다. 이때의 π 값(propensity)을
  `route_requests.propensities` 에 남겨 나중에 IPS(역확률 가중) 오프라인 평가가 가능하다.
- 응답의 `personalized: true`, 프론트의 "내 취향 반영" 태그로 재정렬 여부를 알린다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/route/{request_id}/choose` `{route_id}` | 선택 기록. 로그인 사용자면 정책 갱신 (`learned`, `updates`, `summary`) |
| GET | `/api/me/preferences` | 학습된 가중치와 사람이 읽는 요약 ("도보 적은 길 선호" 등) |
| DELETE | `/api/me/preferences` | 초기화 |

## 로그인

카카오·네이버 OAuth 2.0 인가 코드 흐름 (`backend/app/auth.py`).

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/auth/providers` | 설정된 공급자 목록 |
| GET | `/api/auth/{kakao,naver}/login` | 공급자 동의 화면으로 302 (state 쿠키) |
| GET | `/api/auth/{provider}/callback` | 토큰 교환 → 프로필 → `users` upsert → `pf_session` JWT 쿠키 → `FRONTEND_URL?login=ok` |
| GET | `/api/auth/me` | `{user}` (게스트면 `null`) |
| POST | `/api/auth/logout` | 쿠키 삭제 |
| POST | `/api/auth/dev/login` | `ALLOW_DEV_LOGIN=true` 일 때만. 키 없이 로컬에서 개인화를 시험 |

필요 환경변수: `PUBLIC_BASE_URL`(콜백 베이스), `FRONTEND_URL`, `KAKAO_CLIENT_ID`(REST API 키), `KAKAO_CLIENT_SECRET`(선택),
`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `JWT_SECRET`(32자 이상 권장), `COOKIE_SECURE`(HTTPS 에서 true).
Kakao Developers 와 Naver Developers 콘솔에 Redirect URI 로 `{PUBLIC_BASE_URL}/api/auth/kakao/callback`,
`{PUBLIC_BASE_URL}/api/auth/naver/callback` 을 등록해야 한다.
