"""SQLAlchemy 引擎与声明基类"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.backend.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_async_session_maker = None


def init_db(database_url: str | None = None):
    """初始化数据库引擎和 session maker（应用启动时调用）"""
    global _engine, _async_session_maker
    settings = get_settings()
    url = database_url or settings.database_url
    _engine = create_async_engine(url, echo=settings.debug)
    _async_session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def get_engine():
    return _engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    assert _async_session_maker is not None, "init_db() 尚未调用"
    return _async_session_maker
