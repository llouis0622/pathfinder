# 관리자 페이지

`/admin` 에서 서비스 운영 상태를 본다. 로그(경로 요청·접근/인증·엔진 성능·경로 선택·장소 검색),
사용자와 학습된 취향, 이용 추이·경로 품질·공간 분석 대시보드, CSV 내보내기를 제공한다.

- 프론트: `frontend/src/admin/` (react-router `/admin/*`, 별도 청크)
- 백엔드: `backend/app/admin.py`(인증), `backend/app/admin_routers.py`(API), `backend/app/services/admin_stats.py`(집계), `backend/app/audit.py`(접근 로그)

## 인증

관리자 비밀번호 하나로 로그인한다. 소셜 로그인과 무관하며, 별도 쿠키 `pf_admin`(HS256 JWT, 기본 12시간)을 쓴다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ADMIN_PASSWORD` | (비어 있음) | 비어 있으면 관리자 기능 전체가 꺼진다 (`/api/admin/*` 404, `/admin` 은 설정 안내) |
| `ADMIN_SESSION_HOURS` | 12 | 관리자 세션 길이 |
| `ADMIN_LOGIN_MAX_FAILURES` | 5 | 같은 IP 에서 이 횟수만큼 실패하면 잠금 |
| `ADMIN_LOGIN_LOCKOUT_S` | 300 | 잠금 시간(초) |
| `ACCESS_LOG_ENABLED` | true | `/api` 호출을 `api_access_logs` 에 기록 |
| `LOG_RETENTION_DAYS` | 90 | 접근 로그·장소 검색·엔진 성능 로그 보존 일수. 시작 60초 뒤와 이후 하루 한 번 자동 삭제. 0 이면 끔. `route_requests` 등 분석 원본은 지우지 않는다 |

운영에서는 `JWT_SECRET` 을 32자 이상으로, `COOKIE_SECURE=true` 로 두고, 가능하면 `/admin` 과 `/api/admin` 을 사내망/VPN 으로 제한한다.

## 기록되는 것

| 테이블 | 언제 | 내용 |
|---|---|---|
| `api_access_logs` | 모든 `/api` 요청 (미들웨어) | 종류(api/auth/admin), 메서드, 경로, 상태 코드, 응답 시간, 사용자, IP, UA, 상세(로그인 공급자, 관리자 이벤트 등) |
| `route_requests` / `route_results` | 경로 검색 | 요청·후보 3개 (기존) |
| `route_choices` | 경로 선택 | 고른 순위, propensity, 학습 여부 (기존) |
| `engine_runs` | 검색 성공 | 회랑 크기, 차단 엣지, 스냅 거리, ACO 반복/개미 성공·실패/종료 사유/시간, GA 세대/시간, 보관 경로 수, 엔진·백엔드 시간, 그늘 계산 상태 |
| `policy_updates` | 로그인 사용자의 선택으로 정책이 갱신될 때 | 고른 순위·엔진 순위·탐험 여부, 갱신 전후 가중치 |
| `place_searches` | 장소 검색 | 검색어, 출처, 결과 수 (기존) |

인증 이벤트는 요청 1건 = 행 1개 원칙으로 접근 로그의 `detail` 에 담긴다:
`login:kakao`, `login:naver`, `login:dev`, `login_cancelled:*`, `logout`, 관리자 `login`, `login_failed`, `login_locked`, `logout`, `reset_policy:<user_id>`.

## API

모두 `/api/admin` 아래. `me`·`login`·`logout` 을 제외하면 관리자 세션이 필요하다(401).

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/me` | `{configured, admin}` |
| POST | `/login` `{password}` | 로그인 (실패 401, 잠금 429) |
| POST | `/logout` | 로그아웃 |
| GET | `/overview` | KPI(오늘/7일 검색, 활성·신규 사용자, 선택률, 개인화 비율, 경로 없음/오류율, 평균 응답, 학습 사용자, 서버 오류), 30일 시계열, 프로필 비중, 최근 검색·인증 |
| GET | `/analytics/usage?days=` | 일별 검색·상태·선택·사용자·신규, 시간대/요일 분포, 프로필·상태·그늘 비율, 날씨 조건, 장소 검색 통계 |
| GET | `/analytics/quality?days=` | 제시 순위별·엔진 순위별 선택률, 개인화/엔진/탐험별 1순위 적중률, 프로필별 평균 소요·도보·환승·경로 없음, 배지·주의 빈도 |
| GET | `/analytics/spatial?days=` | 인기 출발·도착·OD 쌍(경로 없음 포함), 많이 지나는 역, 노선, 수직 시설, 미확인 엘리베이터 역 |
| GET | `/analytics/engine?days=` | 엔진/ACO/GA p50·p95, 반복·세대 평균, 개미 실패율, 회랑 크기, 종료 사유, 프로필별, 일별 p50/p95 |
| GET | `/preferences` | 특성별 평균 가중치와 +/− 사용자 수, 취향 요약 분포, 학습 횟수 분포, 사용자별 가중치 |
| GET | `/logs/requests` | 필터: `profile, status, personalized, user_id, q(출발/도착), from, to`, 페이지 `page, size` |
| GET | `/logs/requests/{id}` | 요청·후보 경로(payload 포함)·선택·엔진 실행·정책 갱신 |
| GET | `/logs/access` | 필터: `kind, path(접두), status_min, user_id, from, to` |
| GET | `/logs/engine` | 필터: `profile, from, to` |
| GET | `/logs/choices` | 필터: `user_id, learned` |
| GET | `/logs/policy-updates` | 필터: `user_id` |
| GET | `/logs/places` | 필터: `q` |
| GET | `/users` | 필터 `q, provider`, 정렬 `last_login|created|requests|choices|updates`, 활동 수·취향 요약 포함 |
| GET | `/users/{id}` | 프로필, 통계, 정책(가중치·요약), 최근 요청, 선택 이력, 정책 갱신 이력, 최근 접근 |
| DELETE | `/users/{id}/policy` | 취향 초기화 (접근 로그에 기록) |
| GET | `/export/{requests,choices,users,access,engine}.csv?days=` | CSV (BOM 포함, 최대 5만 행) |
| GET | `/maintenance` | 로그 보존 일수와 접근 로그·장소 검색·엔진 성능 표의 행 수·가장 오래된 시각 |
| POST | `/maintenance/prune` `{days?}` | 그 일수보다 오래된 위 세 표의 행 삭제 (0 = 전부, 생략 = `LOG_RETENTION_DAYS`). 접근 로그에 `prune_logs:<days>d:<n>` 로 남는다 |
| GET | `/analytics/ips?days=` | 개인화 오프라인 평가: 로그된 propensity 로 엔진 순위·개인화 탐욕 정책의 1순위 적중률을 IPS/SNIPS 로 추정, ESS 포함 |

집계는 기간 창 안의 행을 가벼운 열만 읽어 Python 에서 KST 일 단위로 묶는다(PostgreSQL/SQLite 공통).
검색량이 커지면 `route_requests.created_at`, `api_access_logs.created_at` 인덱스가 있으므로 기간을 줄이거나 집계 테이블을 두면 된다.

## 화면

| 경로 | 내용 |
|---|---|
| `/admin` | 대시보드: KPI 타일, 30일 검색·선택·사용자 선 차트, 프로필 비중, 최근 검색·인증 |
| `/admin/logs/requests` | 요청 로그 (필터·페이지) → 상세: 요청 정보, 약식 지도, 후보 경로 표, 엔진 실행 지표, 이번 선택으로 움직인 가중치 |
| `/admin/logs/access` | 접근·인증 로그 |
| `/admin/logs/engine` | 엔진 성능 로그 |
| `/admin/logs/choices` | 경로 선택 로그 |
| `/admin/logs/places` | 장소 검색 로그 (결과 없음 강조) |
| `/admin/users` | 사용자 목록 → 상세: 학습된 취향(발산 막대), 가중치 변화 이력, 선택·검색·접근 이력, 취향 초기화 |
| `/admin/preferences` | 특성별 평균 가중치, 취향 요약 분포, 학습 횟수 분포, 사용자별 가중치 표 |
| `/admin/analytics/usage` | 이용 추이 + 엔진 응답 시간 |
| `/admin/analytics/quality` | 경로 품질·선택률 |
| `/admin/analytics/spatial` | 공간 분석 |

차트는 외부 라이브러리 없이 SVG 로 그린다(`frontend/src/admin/charts.tsx`). 계열색은 4가지(파랑·주황·청록·노랑)만 쓰고,
모든 선·막대 차트에 호버 툴팁과 "표로 보기" 를 둔다. 가중치는 0 을 가운데 둔 발산 막대(양수 파랑, 음수 주황)로 보인다.

## 로컬에서 보기

```bash
# backend
ADMIN_PASSWORD=admin-demo-1234 ALLOW_DEV_LOGIN=true uvicorn app.main:app --port 8000
# frontend
npm run dev   # http://localhost:5173/admin
```

데모 로그인으로 검색·선택을 몇 번 하면 대시보드와 취향 화면이 채워진다.

## 개인화 오프라인 평가 (IPS)

행동을 "1순위에 놓은 경로", 보상을 "사용자가 그 경로를 골랐는가(0/1)" 로 두고, 로깅 확률
`p_b(a) = (1−ε)·1[a = 정책 argmax] + ε·π(a)` (ε-greedy 혼합, π 는 저장된 propensity)로 두 결정적 정책을 역확률 가중한다.

```
w   = 1[a_target = a_shown] / p_b(a_shown)
IPS = 평균(r·w),   SNIPS = Σ(r·w) / Σw,   ESS = (Σw)² / Σw²
```

탐험(ε) 표본이 없으면 엔진 정책의 추정은 개인화 1순위가 엔진 1순위와 같은 검색에만 기대므로 ESS 가 작다.
ESS 가 표본 수에 가까울수록 믿을 만하다. 화면: `/admin/analytics/quality` 의 "오프라인 평가" 카드.
