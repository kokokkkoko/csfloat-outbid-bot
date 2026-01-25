# 🛠️ Development Guide

Руководство для разработчиков, желающих доработать или расширить бота.

## Архитектура проекта

### Основные компоненты

```
┌─────────────────────────────────────────────────┐
│           FastAPI Web Interface                 │
│   (web/app.py, web/templates, web/static)      │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│              Bot Manager                         │
│           (bot/manager.py)                      │
│  - Координация проверок                         │
│  - Управление задачами                          │
│  - Параллельная обработка аккаунтов            │
└────┬─────────────────────────────────┬──────────┘
     │                                  │
     ▼                                  ▼
┌────────────────┐           ┌──────────────────┐
│ OutbidLogic    │           │ AdvancedOrderAPI │
│ (outbid_logic) │           │ (advanced_api)   │
│ - Принятие     │           │ - HTTP клиент    │
│   решений      │           │ - Direct API     │
│ - Расчеты      │           │   calls          │
└────────────────┘           └──────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────┐
│         Account Manager (accounts.py)           │
│  - Управление аккаунтами                       │
│  - CSFloat клиенты (csfloat-api)               │
│  - Кэширование клиентов                        │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│          Database Layer (database.py)           │
│  - SQLAlchemy AsyncSession                     │
│  - Models: Account, BuyOrder, OutbidHistory    │
└─────────────────────────────────────────────────┘
```

## Кодовая база

### 1. Database Layer (`database.py`)

**Модели:**
- `Account` - аккаунты CSFloat
- `BuyOrder` - buy ордера для отслеживания
- `OutbidHistory` - история перебивов

**Важные методы:**
- `db.init()` - инициализация БД
- `db.get_session()` - получение async сессии
- `get_db()` - FastAPI dependency

### 2. Account Management (`accounts.py`)

**AccountManager:**
```python
# Создание аккаунта
account = await manager.create_account(name, api_key, proxy)

# Получение клиента для работы с CSFloat API
client = manager.get_client(account)

# Тест подключения
success, error = await manager.test_account_connection(account)
```

### 3. Bot Logic

#### Manager (`bot/manager.py`)

Главный цикл:
```python
async def _main_loop(self):
    while self.is_running:
        await self._check_and_outbid_all()
        await asyncio.sleep(settings.check_interval)
```

Проверка аккаунта:
```python
async def _check_account(self, session, account):
    # 1. Получить активные ордера из БД
    # 2. Для каждого ордера:
    #    - Получить top buy price
    #    - Проверить нужно ли перебивать
    #    - Перебить если нужно
```

#### Outbid Logic (`bot/outbid_logic.py`)

Принятие решений:
```python
should_outbid, reason = outbid_logic.should_outbid(
    our_order,
    competitor_price
)
# Проверяет:
# - Конкурент перебил нас?
# - Не превышен лимит перебивов?
# - Не превышена максимальная цена?
```

#### Advanced API (`bot/advanced_api.py`)

⚠️ **ТРЕБУЕТ ДОРАБОТКИ**

Прямые HTTP запросы к CSFloat:
```python
api = AdvancedOrderAPI(api_key, proxy)

# Создать advanced order
order = await api.create_advanced_order(
    market_hash_name="AK-47 | Redline (FT)",
    max_price_cents=1234,
    float_min=0.15,
    float_max=0.25
)

# Удалить
await api.delete_advanced_order(order_id)
```

## Добавление новых функций

### Пример: Добавить уведомления в Telegram

1. **Добавить настройки** (`config.py`):
```python
class Settings(BaseSettings):
    # ...
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
```

2. **Создать модуль** (`notifications.py`):
```python
import httpx

async def send_telegram(message: str):
    if not settings.telegram_bot_token:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    await httpx.post(url, json={
        "chat_id": settings.telegram_chat_id,
        "text": message
    })
```

3. **Интегрировать** (`bot/manager.py`):
```python
from notifications import send_telegram

async def _check_and_outbid_order(...):
    # ...
    if new_order_id:
        await send_telegram(
            f"✅ Outbid successful!\n"
            f"Item: {order.market_hash_name}\n"
            f"Price: ${old_price/100:.2f} → ${new_price/100:.2f}"
        )
```

4. **Добавить в UI** (опционально)

### Пример: Добавить поддержку других маркетплейсов

1. Создать абстрактный класс:
```python
# marketplace/base.py
from abc import ABC, abstractmethod

class MarketplaceClient(ABC):
    @abstractmethod
    async def get_my_orders(self) -> List[Order]:
        pass

    @abstractmethod
    async def create_order(self, ...):
        pass

    @abstractmethod
    async def delete_order(self, order_id):
        pass
```

2. Реализовать для CSFloat:
```python
# marketplace/csfloat.py
class CSFloatMarketplace(MarketplaceClient):
    # ...
```

3. Добавить для Skinport:
```python
# marketplace/skinport.py
class SkinportMarketplace(MarketplaceClient):
    # ...
```

4. Обновить AccountManager для поддержки разных маркетплейсов

## Тестирование

### Unit тесты

```bash
# Установить pytest
pip install pytest pytest-asyncio

# Создать tests/test_outbid_logic.py
import pytest
from bot.outbid_logic import OutbidLogic

@pytest.mark.asyncio
async def test_should_outbid():
    # ...
```

### Интеграционные тесты

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from web.app import app

client = TestClient(app)

def test_get_accounts():
    response = client.get("/api/accounts")
    assert response.status_code == 200
```

## Полезные команды

```bash
# Форматирование кода
pip install black
black .

# Проверка типов
pip install mypy
mypy .

# Линтинг
pip install pylint
pylint bot/ web/

# Запуск тестов
pytest

# Запуск с автоперезагрузкой (для разработки)
uvicorn web.app:app --reload --port 8000
```

## Debugging

### Включить подробное логирование

В `config.py`:
```python
log_level: str = "DEBUG"
```

### Использовать breakpoints

```python
import pdb; pdb.set_trace()  # Python debugger

# Или с ipdb (улучшенный):
# pip install ipdb
import ipdb; ipdb.set_trace()
```

### Логирование SQL запросов

В `database.py`:
```python
self.engine = create_async_engine(
    settings.database_url,
    echo=True,  # ← Включить SQL logging
)
```

## Code Style

- **PEP 8** для форматирования
- **Type hints** везде где возможно
- **Docstrings** для всех публичных функций (Google style)
- **Async/await** вместо callbacks
- **Context managers** для ресурсов

Пример:
```python
async def create_account(
    self,
    name: str,
    api_key: str,
    proxy: Optional[str] = None
) -> Account:
    """
    Создать новый аккаунт CSFloat.

    Args:
        name: Название аккаунта
        api_key: API ключ от CSFloat
        proxy: Прокси сервер (опционально)

    Returns:
        Созданный аккаунт

    Raises:
        ValueError: Если аккаунт с таким именем уже существует
    """
    # ...
```

## Performance

### Оптимизация запросов к БД

Используйте `selectinload` для eager loading:
```python
from sqlalchemy.orm import selectinload

result = await session.execute(
    select(Account)
    .options(selectinload(Account.orders))
)
```

### Кэширование

Используйте кэширование для частых запросов:
```python
from functools import lru_cache
import asyncio

# Простой async cache
_cache = {}
_cache_lock = asyncio.Lock()

async def cached_get_top_price(item_name: str) -> int:
    async with _cache_lock:
        if item_name in _cache:
            return _cache[item_name]

        price = await fetch_price(item_name)
        _cache[item_name] = price
        return price
```

## Contributing

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/amazing`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Создайте Pull Request

---

**Happy coding! 🚀**
