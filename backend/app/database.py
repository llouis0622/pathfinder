from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# 비동기 엔진 생성
engine = create_async_engine(settings.database_url, echo=False)

# 비동기 세션 팩토리
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# 테이블 자동 생성 (앱 시작 시 호출)
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 의존성 주입용 세션 제공자
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
