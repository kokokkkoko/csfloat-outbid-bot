"""
CSFloat Outbid Bot - Main Entry Point
Запуск веб-интерфейса и бота
"""
import sys
import asyncio
import uvicorn
from loguru import logger

from config import settings

# Настройка логирования
logger.remove()  # Удаляем дефолтный handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level
)
logger.add(
    "logs/bot_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)


def main():
    """Главная функция запуска"""
    logger.info("=" * 60)
    logger.info("CSFloat Outbid Bot v1.0.0")
    logger.info("=" * 60)

    try:
        # Запускаем веб-сервер
        logger.info(f"Starting web server on {settings.host}:{settings.port}")

        uvicorn.run(
            "web.app:app",
            host=settings.host,
            port=settings.port,
            reload=False,  # В продакшене отключаем reload
            log_level=settings.log_level.lower()
        )

    except KeyboardInterrupt:
        logger.info("Received shutdown signal (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
