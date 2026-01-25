"""
Database models and connection management
"""
from datetime import datetime
from typing import Optional, AsyncGenerator
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from loguru import logger

from config import settings


# Base class для всех моделей
class Base(DeclarativeBase):
    pass


class Account(Base):
    """Модель аккаунта CSFloat"""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    proxy: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle, online, error, rate_limited
    last_check: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BuyOrder(Base):
    """Модель buy-ордера"""
    __tablename__ = "buy_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # CSFloat order ID
    order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Order details
    market_hash_name: Mapped[str] = mapped_column(String(500), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # цена в центах
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # Type: simple or advanced
    order_type: Mapped[str] = mapped_column(String(20), default="simple")

    # For advanced orders
    float_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    float_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    def_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID оружия (DefIndex)
    paint_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID скина (PaintIndex)

    # Outbid tracking
    outbid_count: Mapped[int] = mapped_column(Integer, default=0)
    max_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # максимальная цена для перебивания

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OutbidHistory(Base):
    """История перебивов"""
    __tablename__ = "outbid_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    market_hash_name: Mapped[str] = mapped_column(String(500), nullable=False)

    old_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    new_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    competitor_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Database engine and session
class Database:
    """Database connection manager"""

    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def init(self):
        """Инициализация базы данных"""
        logger.info(f"Initializing database: {settings.database_url}")

        self.engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Создаем таблицы
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    async def close(self):
        """Закрытие соединения с БД"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Получить сессию БД"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")

        async with self.session_factory() as session:
            yield session


# Singleton instance
db = Database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для FastAPI"""
    async for session in db.get_session():
        yield session
