# Pathfinder — 교통약자 맞춤형 경로 추천 서비스

부산광역시를 시작으로, 교통약자 및 이동취약자를 위한 맞춤형 경로 추천 웹앱 서비스입니다.

## 서비스 구성

| 서비스 | 설명 | 포트 |
|---|---|---|
| Frontend | React + Vite 웹앱 | 5173 |
| Backend | FastAPI 백엔드 서버 | 8000 |
| AI Server | 경로탐색 AI 서버 | 8001 |
| Database | PostgreSQL + PostGIS | 5432 |

## 빠른 시작 (로컬 실행)

### 사전 요구사항

- Docker Desktop 설치
- Docker Compose v2 이상

### 1. 레포지토리 클론

```bash
git clone https://github.com/YOUR_ORG/pathfinder.git
cd pathfinder
```

### 2. 환경변수 설정

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env
cp ai/.env.example ai/.env
```

`frontend/.env`를 열고 카카오맵 앱 키를 입력한다.

```env
VITE_KAKAO_MAP_KEY=발급받은_카카오맵_앱키_입력
```

카카오 앱 키 발급 방법:
1. https://developers.kakao.com 접속
2. 애플리케이션 추가
3. 앱 키 중 **JavaScript 키** 복사 → `VITE_KAKAO_MAP_KEY`에 입력
4. 카카오 REST API 키 복사 → `backend/.env`의 `KAKAO_REST_API_KEY`에 입력

### 3. 서버 실행

```bash
docker compose up --build
```

### 4. 접속

| 서비스 | URL |
|---|---|
| 웹앱 | http://localhost:5173 |
| 백엔드 API 문서 | http://localhost:8000/docs |
| AI 서버 API 문서 | http://localhost:8001/docs |

### 5. 서버 종료

```bash
docker compose down
```

데이터베이스 데이터까지 초기화하려면:

```bash
docker compose down -v
```

## 개발 환경 (컨테이너 없이 실행)

### 프론트엔드

```bash
cd frontend
pnpm install
pnpm dev
```

### 백엔드

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### AI 서버

```bash
cd ai
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## 프로젝트 구조

```
pathfinder/
├── frontend/    # React + Vite 웹앱
├── backend/     # FastAPI 백엔드
├── ai/          # 경로탐색 AI 서버
└── docker-compose.yml
```

## 현재 구현 상태

| 기능 | 상태 | 비고 |
|---|---|---|
| 위치 검색 | ✅ 구현 완료 | 카카오 로컬 API 연동 |
| 지도 표시 | ✅ 구현 완료 | 카카오맵 SDK |
| 길찾기 경로 표시 | ✅ 구현 완료 | 플레이스홀더 경로 |
| 사용자 프로필 선택 | ✅ 구현 완료 | 가중치 파라미터 전달 구조 |
| AI 경로 추천 | ⏳ 미구현 | 데이터 수집 및 모델 학습 후 적용 |
| 실시간 재탐색 | ⏳ 미구현 | AI 모델 완성 후 적용 |

## 기여 방법

브랜치 전략:
- `main`: 배포 브랜치
- `develop`: 통합 개발 브랜치
- `feature/기능명`: 기능 개발 브랜치
