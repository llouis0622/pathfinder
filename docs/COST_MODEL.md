# 비용 모델

모든 비용은 **일반화 시간(초)** 이다. 실제 이동 시간에 프로필·날씨에 따른 부담을
시간으로 환산해 더한다. 사용자에게 보여주는 소요 시간은 부담을 뺀 실제 시간이다.

구현: `engine/app/cost/`

## 프로필

| id | 이름 | 평지 보행 속도 | 핵심 제약 |
|---|---|---|---|
| `wheelchair` | 휠체어 이용자 | 1.0 m/s | 계단(경사로 없음) 차단, 경사 10% 초과 차단, 폭 0.9m 미만 차단, 엘리베이터 없는 수직 이동 차단, 저상버스 아닌 노선 차단 |
| `elderly` | 고령자 | 0.85 m/s | 계단·급경사 강한 패널티, 총 도보 부담, 폭염·한파 민감 |
| `walking_aid` | 보행보조기·목발 이용자 | 0.7 m/s | 고령자보다 계단 패널티 큼, 엘리베이터 선호 |
| `visually_impaired` | 시각장애인 | 0.9 m/s | 신호 없는 횡단 패널티, 점자블록 가중, 복잡한 환승 패널티 |

## 보행 엣지 (`walk`, `link`)

```
t0 = length_m / speed
```

### 경사 (grade_pct, u→v 방향 부호)

이동 시간 계수는 순 경사 `grade_pct`, 소프트 임계·하드 차단 판정은 `max(|grade_pct|, max_grade_pct)`(엣지 안 45 m 표본 구간의 최대 경사)를 쓴다.

| 프로필 | 오르막 계수 a_up | 내리막 계수 a_down | 소프트 임계 | 하드 차단 |
|---|---|---|---|---|
| wheelchair | 0.25 | 0.10 | 6 % | > 10 % |
| elderly | 0.12 | 0.05 | 8 % | 없음 |
| walking_aid | 0.15 | 0.10 | 8 % | 없음 |
| visually_impaired | 0.08 | 0.03 | 10 % | 없음 |

```
g = |grade_pct|
t = t0 * (1 + a * g)                       # a = a_up 또는 a_down
if g > soft_threshold: t += length_m * 1.5  # 급경사 추가 부담(초/m)
```

### 계단 (`stairs=True`)

| 프로필 | 처리 |
|---|---|
| wheelchair | `ramp=True`면 통과(경사 규칙 적용), 아니면 **차단** |
| elderly | + 25 s + 3 s × step_count |
| walking_aid | + 45 s + 5 s × step_count |
| visually_impaired | + 20 s + 2 s × step_count (난간 `handrail=True`면 절반) |

`step_count` 미상은 12로 가정한다.

### 표면 (`surface`)

| 표면 | wheelchair | elderly | walking_aid | visually_impaired |
|---|---|---|---|---|
| asphalt, concrete, paved, paving_stones | ×1.0 | ×1.0 | ×1.0 | ×1.0 |
| cobblestone, sett | ×1.6 | ×1.15 | ×1.4 | ×1.15 |
| gravel, fine_gravel, compacted | ×1.5 | ×1.15 | ×1.3 | ×1.1 |
| unpaved, dirt, ground, grass, sand | ×1.8 | ×1.2 | ×1.5 | ×1.2 |

### 보도 폭 (`width_m`)

- wheelchair: < 0.9 m 차단, < 1.2 m 이면 + 0.5 s/m
- 그 외: 영향 없음

### 횡단보도 (`crossing`)

| crossing | wheelchair | elderly | walking_aid | visually_impaired |
|---|---|---|---|---|
| traffic_signals | +20 s | +20 s | +20 s | +20 s (`tactile_paving=False`면 +40 s 추가) |
| marked / zebra | +10 s | +10 s | +10 s | +45 s |
| unmarked / 없음 | +15 s | +15 s | +15 s | +90 s |
| `kerb=raised` | **차단** | +10 s | +20 s | 0 |

### 점자블록 (`tactile_paving`)

visually_impaired: `tactile_paving=True`이면 ×0.85, 명시적으로 `False`이고 `footway=sidewalk`면 ×1.15.

## 날씨 수정자 (실외 엣지에만 적용, `indoor=False`)

`WeatherContext`는 백엔드가 만든다. 플래그 기준:

- `heat`: 체감온도 ≥ 28 ℃, `heatwave`: ≥ 33 ℃
- `cold`: 체감온도 ≤ -5 ℃ 또는 기온 ≤ 0 ℃ 이고 풍속 ≥ 5 m/s, `coldwave`: 체감 ≤ -12 ℃
- `rain`: 시간당 강수 ≥ 0.5 mm 또는 sky ∈ {rain, snow}
- `bad_air`: PM10 ≥ 81 ㎍/㎥
- `windy`: 풍속 ≥ 9 m/s

```
heat:     t *= 1 + h * (1 - shade_ratio)     h = 0.5 (wheelchair) / 0.6 (elderly, walking_aid) / 0.3 (vi); heatwave면 h 두 배
cold:     t *= 1.3 (coldwave 1.5); 실외 정류장 대기 ×1.5
rain:     t *= 1.25; 계단 패널티 ×1.5; 급경사 추가 부담 ×1.5; 미끄러운 표면(cobblestone, sett, 비포장) 추가 ×1.2
bad_air:  t *= 1.2 (elderly 1.3)
windy:    wheelchair 실외 ×1.15
```

`shade_ratio`는 출발 시각의 태양 위치로 계산한 엣지의 건물 그늘 비율(0~1)이다. 밤이거나 건물 정보가 없으면 0으로 두고 응답에 `shade_status`로 알린다.

## 수직 이동 엣지 (`vertical`, 역 출입구 ↔ 승강장)

| 수단 | wheelchair | elderly | walking_aid | visually_impaired |
|---|---|---|---|---|
| elevator=True | 90 s | 90 s | 90 s | 100 s |
| escalator=True (엘리베이터 없음) | **차단** | 70 s | 90 s | 80 s |
| stairs만 | **차단** | 150 s | 240 s | 120 s |
| elevator=None (미확인) | 90 s + **600 s 패널티**, 주의 표시 | 120 s | 150 s | 110 s |

## 승차 엣지 (`board`)

```
wait = min(headway_s / 2, 900)
t = wait + boarding
boarding: 지하철 30 s / 버스 20 s
wheelchair 버스: low_floor_ratio == 0 → 차단; 그 외 wait /= low_floor_ratio, boarding = 120 s
elderly·walking_aid 버스: boarding + 30 s
환승 패널티(첫 승차 제외): wheelchair 300 s / elderly 240 s / walking_aid 300 s / visually_impaired 360 s
```

## 하차 엣지 (`alight`)

wheelchair 버스 60 s, 그 외 10 s.

## 탑승 엣지 (`ride`)

`t = time_s` 그대로. 실내 취급(날씨 수정자 없음).

## 경로 총점

`cost(route) = Σ cost(e)`. 응답의 `total_duration_min`은 부담 없는 순수 시간 합
(`Σ time_s`)을 분 단위로 보여준다.
