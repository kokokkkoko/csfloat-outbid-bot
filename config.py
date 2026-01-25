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

    # Price ceiling settings
    max_outbid_multiplier: float = Field(
        default=1.20,
        description="Максимальный множитель от lowest listing (1.20 = +20%)"
    )
    max_outbid_premium_cents: int = Field(
        default=500,
        description="Максимальная надбавка в центах над lowest listing ($5.00)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    # Authentication
    jwt_secret_key: str = Field(
        default="your-super-secret-key-change-in-production-123",
        description="Secret key for JWT tokens"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=1440, description="JWT token expiry in minutes (24h)")
    allow_registration: bool = Field(default=True, description="Allow new user registration")

    # Rate limiting
    max_requests_per_minute: int = Field(default=60, description="Global API rate limit")
    max_requests_per_account: int = Field(default=30, description="Per-account rate limit")

    # Admin panel settings
    admin_enabled: bool = Field(
        default=True,
        description="Enable admin panel (set to false for shared/production deployments)"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True  # Разрешаем изменение настроек


# Singleton instance
settings = Settings()
