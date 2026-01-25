"""
Конфигурация бота и приложения
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Основные настройки приложения"""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Host to bind")
    port: int = Field(default=8000, description="Port to bind")

    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        description="Database connection URL"
    )

    # Bot settings
    check_interval: int = Field(
        default=120,
        description="Интервал проверки ордеров в секундах"
    )
    outbid_step: float = Field(
        default=0.01,
        description="Шаг перебивания в долларах"
    )
    max_outbids: int = Field(
        default=10,
        description="Максимальное количество перебивов на один ордер"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True  # Разрешаем изменение настроек


# Singleton instance
settings = Settings()
