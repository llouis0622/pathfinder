# 관리자 페이지

`/admin` 에서 서비스 운영 상태를 본다. 로그(경로 요청·접근/인증·엔진 성능·경로 선택·장소 검색),
사용자와 학습된 취향, 이용 추이·경로 품질·공간 분석 대시보드, CSV 내보내기를 제공한다.

- 프론트: `frontend/src/admin/` (react-router `/admin/*`, 별도 청크)
- 백엔드: `backend/app/admin.py`(인증), `backend/app/admin_routers.py`(API), `backend/app/services/admin_stats.py`(집계), `backend/app/audit.py`(접근 로그)

## 인증

`ADMIN_PASSWORD` 가 있어도 `JWT_SECRET` 이 자리표시자·32자 미만이면 관리자 기능은 꺼진다(`/api/admin/me` 의 `reason: jwt_secret`). 로그인 실패 잠금과 제보 한도는 `X-Forwarded-For` 의 **마지막** 항목(프록시가 붙인 실제 접속 IP)을 기준으로 센다.

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
| GET | `/reports` | 시설 제보 목록 (`status, kind`), 상태별 수, 종류 라벨 |
| POST | `/reports/{id}/accept` `{edge_id?, kind?, expires_days?, note?}` | 제보 승인 → 엣지 오버라이드 생성. `edge_id` 를 비우면 엔진 `/api/nearest-edge` 로 제보 좌표에서 가장 가까운 보행 엣지를 찾는다. 검색 캐시를 비우고 접근 로그에 `report_accept:` 로 남는다 |
| POST | `/reports/{id}/reject` `{note?}` | 제보 거절 |
| GET | `/overrides?active=` | 오버라이드 목록 |
| POST | `/overrides` `{edge_id, kind, expires_days?, note?}` | 제보 없이 직접 추가 |
| DELETE | `/overrides/{id}` | 해제 (검색에서 즉시 제외) |
| GET | `/data-quality` | 엔진 그래프 통계(`/api/stats`: 노드·엣지 종류, 경사·폭·노면 커버리지, 계단·급경사·턱·횡단, 점자블록·조명·엘리베이터 확인/미확인, 대중교통, 건물 높이 커버리지, 보행망 연결성) + 제보 상태별 수, 활성 오버라이드, 검색 캐시 적중 |
| GET | `/setup` | 설정 상태: 필수/권장/선택 항목별 준비됨·축소 동작·없음, 요약(`runnable`, `ready_for_production`), 엔진 상태. 같은 기준을 `/health` 의 `features` 와 `scripts/doctor.py` 가 쓴다 |
| GET | `/alerts/settings` | 알림 설정 (웹훅 URL 은 앞 28자만 마스킹해 돌려준다) |
| PUT | `/alerts/settings` | 보낸 필드만 갱신. `webhook_url` 은 http(s) 만, `rules` 키는 정해진 6개만 |
| POST | `/alerts/test` | 웹훅으로 테스트 메시지 |
| POST | `/alerts/evaluate` | 지금 규칙 평가 + (웹훅이 있으면) 전송. `{findings, sent}` |
| GET | `/alerts/events?rule=` | 알림 이력 (전송 성공·HTTP 상태·오류) |
| GET | `/analytics/ips?days=` | 개인화 오프라인 평가: 로그된 propensity 로 엔진 순위·개인화 탐욕 정책의 1순위 적중률을 IPS/SNIPS 로 추정, ESS 포함 |

집계는 기간 창 안의 행을 가벼운 열만 읽어 Python 에서 KST 일 단위로 묶는다(PostgreSQL/SQLite 공통).
검색량이 커지면 `route_requests.created_at`, `api_access_logs.created_at` 인덱스가 있으므로 기간을 줄이거나 집계 테이블을 두면 된다.

## 화면

| 경로 | 내용 |
|---|---|
| `/admin` | 대시보드: **설정 상태** 카드(빠진 키·데이터, 축소 동작 중인 기능, 가이드 링크), KPI 타일, 30일 검색·선택·사용자 선 차트, 프로필 비중, 최근 검색·인증 |
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
| `/admin/data-quality` | 데이터 품질: 경사·건물 높이·연결성 커버리지 타일(60% 미만 경고, 90% 이상 양호), 보행 엣지 속성, 대중교통·노드 종류, 턱·횡단 정보, 제보·오버라이드·캐시 |
| `/admin/reports` | 제보 검토: 대기/반영/거절 필터, 행마다 "반영…"(종류·엣지 ID·만료·메모) 또는 "거절", 활성 오버라이드 표와 직접 추가·해제 |
| `/admin/alerts` | 알림: 웹훅 URL·형식(Slack/JSON)·주기·집계 창·재알림 간격, 규칙별 켜기·임계·최소 표본, 테스트 전송, 지금 평가, 알림 이력 |

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

## 알림 (Slack 수신 웹훅)

백엔드가 `ALERT_INTERVAL_MIN`(기본 5분)마다 아래 규칙을 평가해 웹훅으로 보낸다(`backend/app/services/alerts.py`).
설정은 `admin_settings` 표의 `alerts` 키에 저장되고, 없으면 환경변수(`ALERT_WEBHOOK_URL`, `ALERT_ENABLED`, `ALERT_INTERVAL_MIN`) 기본값을 쓴다.

| 규칙 | 기본 임계 | 뜻 |
|---|---|---|
| `engine_down` | — | 엔진 `/health` 가 200 이 아님 |
| `error_rate` | 10 % (표본 10건 이상) | 집계 창(기본 30분) 안 검색 중 오류 비율 |
| `no_route_rate` | 40 % (표본 10건 이상) | 집계 창 안 검색 중 경로 없음 비율 |
| `engine_p95_ms` | 3000 ms (표본 5건 이상) | 집계 창 안 엔진 응답 p95 |
| `access_5xx` | 5건 | 집계 창 안 서버 오류(5xx) 응답 수 |
| `open_reports` | 10건 | 검토 대기 제보 수 |

- 같은 규칙은 `cooldown_min`(기본 60분) 안에는 다시 보내지 않고, 정상으로 돌아오면 복구 메시지를 한 번 보낸다.
- 형식 `slack` 은 `{text}` 한 줄(마크다운), `json` 은 `{service, events:[{rule, level, message, value, threshold}]}` 라 Discord·Teams·자체 서버에서 받기 쉽다.
- 전송 수는 Prometheus `pathfinder_alerts_sent_total{rule}` 로 센다. 이력은 `/admin/alerts` 아래 표와 `alert_events` 표에 남는다.

Slack 웹훅 만들기: Slack 앱 만들기 → Incoming Webhooks 켜기 → 채널 선택 → 생성된 `https://hooks.slack.com/services/…` 를 `/admin/alerts` 에 붙여넣고 "테스트 전송".

## 개인화 오프라인 평가 (IPS)

행동을 "1순위에 놓은 경로", 보상을 "사용자가 그 경로를 골랐는가(0/1)" 로 두고, 로깅 확률
`p_b(a) = (1−ε)·1[a = 정책 argmax] + ε·π(a)` (ε-greedy 혼합, π 는 저장된 propensity)로 두 결정적 정책을 역확률 가중한다.

```
w   = 1[a_target = a_shown] / p_b(a_shown)
IPS = 평균(r·w),   SNIPS = Σ(r·w) / Σw,   ESS = (Σw)² / Σw²
```

탐험(ε) 표본이 없으면 엔진 정책의 추정은 개인화 1순위가 엔진 1순위와 같은 검색에만 기대므로 ESS 가 작다.
ESS 가 표본 수에 가까울수록 믿을 만하다. 화면: `/admin/analytics/quality` 의 "오프라인 평가" 카드.
