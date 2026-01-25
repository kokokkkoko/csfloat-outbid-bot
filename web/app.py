"""
FastAPI Web Interface для CSFloat Bot
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database import db, get_db, Account, BuyOrder, OutbidHistory
from accounts import AccountManager
from bot.manager import bot_manager
from config import settings


# Pydantic модели для API
class AccountCreate(BaseModel):
    name: str
    api_key: str
    proxy: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    proxy: Optional[str] = None
    is_active: Optional[bool] = None


class BuyOrderCreate(BaseModel):
    account_id: int
    market_hash_name: str
    price_cents: int
    quantity: int = 1
    order_type: str = "simple"  # simple or advanced
    float_min: Optional[float] = None
    float_max: Optional[float] = None
    max_price_cents: Optional[int] = None


class SettingsUpdate(BaseModel):
    check_interval: Optional[int] = None
    outbid_step: Optional[float] = None
    max_outbids: Optional[int] = None


# Создаем FastAPI приложение
app = FastAPI(
    title="CSFloat Outbid Bot",
    description="Automatic buy order outbidding bot for CSFloat",
    version="1.0.0"
)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


# === Startup/Shutdown Events ===

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Starting web application...")
    await db.init()
    logger.success("Web application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("Shutting down...")
    await bot_manager.stop()
    await db.close()
    logger.success("Application stopped")


# === Web Pages ===

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})


# === Bot Control API ===

@app.post("/api/bot/start")
async def start_bot():
    """Запустить бота"""
    try:
        await bot_manager.start()
        return {"status": "success", "message": "Bot started"}
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bot/stop")
async def stop_bot():
    """Остановить бота"""
    try:
        await bot_manager.stop()
        return {"status": "success", "message": "Bot stopped"}
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/status")
async def get_bot_status():
    """Получить статус бота"""
    status = await bot_manager.get_status()
    return status


# === Accounts API ===

@app.get("/api/accounts")
async def get_accounts(session: AsyncSession = Depends(get_db)):
    """Получить все аккаунты"""
    manager = AccountManager(session)
    accounts = await manager.get_all_accounts()

    return [
        {
            "id": acc.id,
            "name": acc.name,
            "api_key": acc.api_key[:10] + "...",  # Скрываем полный ключ
            "proxy": acc.proxy,
            "is_active": acc.is_active,
            "status": acc.status,
            "last_check": acc.last_check.isoformat() if acc.last_check else None,
            "error_message": acc.error_message
        }
        for acc in accounts
    ]


@app.post("/api/accounts")
async def create_account(
    account_data: AccountCreate,
    session: AsyncSession = Depends(get_db)
):
    """Создать новый аккаунт"""
    try:
        manager = AccountManager(session)
        account = await manager.create_account(
            name=account_data.name,
            api_key=account_data.api_key,
            proxy=account_data.proxy
        )

        return {
            "status": "success",
            "account": {
                "id": account.id,
                "name": account.name
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}")
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Обновить аккаунт"""
    try:
        manager = AccountManager(session)
        account = await manager.update_account(
            account_id=account_id,
            name=account_data.name,
            api_key=account_data.api_key,
            proxy=account_data.proxy,
            is_active=account_data.is_active
        )

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/accounts/{account_id}")
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_db)
):
    """Удалить аккаунт"""
    try:
        manager = AccountManager(session)
        success = await manager.delete_account(account_id)

        if not success:
            raise HTTPException(status_code=404, detail="Account not found")

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/{account_id}/test")
async def test_account(
    account_id: int,
    session: AsyncSession = Depends(get_db)
):
    """Тестировать подключение аккаунта"""
    try:
        manager = AccountManager(session)
        account = await manager.get_account(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        success, error = await manager.test_account_connection(account)

        return {
            "status": "success" if success else "error",
            "message": error if error else "Connection successful"
        }
    except Exception as e:
        logger.error(f"Error testing account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts/{account_id}/sync-orders")
async def sync_orders(
    account_id: int,
    session: AsyncSession = Depends(get_db)
):
    """Синхронизировать ордера из CSFloat в базу данных"""
    try:
        manager = AccountManager(session)
        account = await manager.get_account(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Получаем клиента
        client = manager.get_client(account)

        # Получаем все buy orders из CSFloat
        logger.info(f"Requesting buy orders from CSFloat for account {account.name}...")
        try:
            response = await client.get_my_buy_orders(limit=100)
            logger.success(f"Got response from CSFloat API")
        except Exception as api_error:
            logger.error(f"CSFloat API error: {api_error}", exc_info=True)
            raise

        # Логируем ответ для отладки
        logger.info(f"CSFloat response type: {type(response)}")
        logger.info(f"CSFloat response keys: {response.keys() if isinstance(response, dict) else 'not a dict'}")
        logger.debug(f"Full CSFloat response: {response}")

        synced_count = 0
        updated_count = 0
        deactivated_count = 0

        # Извлекаем список ордеров из ответа
        # API возвращает {'orders': [...], 'count': N}
        if isinstance(response, dict):
            csfloat_orders = response.get('orders', [])
            logger.info(f"Found {len(csfloat_orders)} orders in response")
        elif isinstance(response, list):
            csfloat_orders = response
            logger.info(f"Found {len(csfloat_orders)} orders in response (list format)")
        else:
            raise ValueError(f"Unexpected response type: {type(response)}")

        # Собираем ID всех ордеров из CSFloat для отслеживания
        csfloat_order_ids = set()

        # Синхронизируем каждый ордер
        for cf_order in csfloat_orders:
            # cf_order это словарь с ключами: id, created_at, expression, qty, price
            order_id = cf_order.get('id')
            if not order_id:
                logger.warning(f"Order without ID, skipping: {cf_order}")
                continue

            # Добавляем в список активных ID из CSFloat
            csfloat_order_ids.add(str(order_id))

            # Проверяем, есть ли уже в БД
            result = await session.execute(
                select(BuyOrder).where(BuyOrder.order_id == str(order_id))
            )
            existing_order = result.scalar_one_or_none()

            # Определяем тип ордера и название предмета
            expression = cf_order.get('expression', '')
            market_hash_name_field = cf_order.get('market_hash_name', '')

            # Advanced ордера имеют expression с логикой (DefIndex ==, and, etc.)
            # Simple ордера имеют просто market_hash_name
            if expression and ('==' in expression or 'and' in expression or '>=' in expression):
                # Advanced order
                order_type = "advanced"

                # Парсим DefIndex, PaintIndex и float диапазон из expression
                import re
                float_min = None
                float_max = None
                def_index = None
                paint_index = None

                # Парсим DefIndex (ID оружия)
                def_match = re.search(r'DefIndex\s*==\s*(\d+)', expression)
                if def_match:
                    def_index = int(def_match.group(1))

                # Парсим PaintIndex (ID скина)
                paint_match = re.search(r'PaintIndex\s*==\s*(\d+)', expression)
                if paint_match:
                    paint_index = int(paint_match.group(1))

                # Ищем минимальный float (FloatValue >= X или FloatValue > X)
                min_match = re.search(r'FloatValue\s*>=?\s*([\d.]+)', expression)
                if min_match:
                    float_min = float(min_match.group(1))

                # Ищем максимальный float (FloatValue <= X или FloatValue < X)
                max_match = re.search(r'FloatValue\s*<=?\s*([\d.]+)', expression)
                if max_match:
                    float_max = float(max_match.group(1))

                # Получаем читаемое название скина
                # 1. Сначала проверяем, есть ли в ответе CSFloat
                market_hash_name = market_hash_name_field if market_hash_name_field else None

                # 2. Если нет, пробуем получить через API
                if not market_hash_name:
                    market_hash_name = expression  # По умолчанию используем expression
                    try:
                        if def_index and paint_index:
                            logger.info(f"Fetching item name for DefIndex={def_index}, PaintIndex={paint_index}, float=[{float_min}-{float_max}]")
                            # Пробуем найти листинг с этими параметрами
                            # category: 0 = any, 1 = normal, 2 = stattrak, 3 = souvenir
                            # Фильтруем по float range, чтобы получить правильное качество (FT, MW, etc.)
                            listings_response = await client.get_all_listings(
                                def_index=def_index,
                                paint_index=paint_index,
                                category=1,  # Только normal (не StatTrak)
                                min_float=float_min if float_min is not None else None,
                                max_float=float_max if float_max is not None else None,
                                limit=1,
                                type_="buy_now"
                            )

                            logger.debug(f"Listings response: {listings_response}")

                            if listings_response and "listings" in listings_response:
                                listings = listings_response["listings"]
                                logger.debug(f"Found {len(listings)} listings")
                                if listings and len(listings) > 0:
                                    # Берем market_hash_name из первого листинга
                                    first_listing = listings[0]
                                    # Listing.item возвращает объект Item, у которого есть market_hash_name
                                    if first_listing.item and first_listing.item.market_hash_name:
                                        item_name = first_listing.item.market_hash_name
                                        logger.info(f"Successfully fetched item name: {item_name}")
                                        market_hash_name = item_name
                                    else:
                                        logger.warning(f"Listing found but no item/market_hash_name")
                                else:
                                    logger.warning(f"No listings found for DefIndex={def_index}, PaintIndex={paint_index}")
                            else:
                                logger.warning(f"Invalid response structure: {listings_response}")
                    except Exception as e:
                        logger.error(f"Error fetching item name for DefIndex={def_index}, PaintIndex={paint_index}: {e}", exc_info=True)
                        # Оставляем expression как название
                else:
                    logger.info(f"Using market_hash_name from CSFloat response: {market_hash_name}")
            else:
                # Simple order
                order_type = "simple"
                market_hash_name = market_hash_name_field or expression or 'Unknown'
                float_min = None
                float_max = None
                def_index = None
                paint_index = None

            price_cents = cf_order.get('price', 0)
            quantity = cf_order.get('qty', 1)

            float_range_str = f"[{float_min}-{float_max}]" if float_min is not None or float_max is not None else "N/A"
            def_paint_str = f"Def={def_index},Paint={paint_index}" if def_index and paint_index else "N/A"
            logger.debug(f"Processing order: ID={order_id}, Type={order_type}, {def_paint_str}, Item={market_hash_name[:50]}..., Price={price_cents}, Qty={quantity}, Float={float_range_str}")

            if existing_order:
                # Обновляем существующий
                existing_order.price_cents = price_cents
                existing_order.quantity = quantity
                existing_order.order_type = order_type  # Обновляем тип
                existing_order.float_min = float_min  # Обновляем float range
                existing_order.float_max = float_max
                existing_order.def_index = def_index  # Обновляем DefIndex/PaintIndex
                existing_order.paint_index = paint_index
                existing_order.market_hash_name = market_hash_name  # Обновляем название
                existing_order.is_active = True
                existing_order.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Создаем новый
                new_order = BuyOrder(
                    account_id=account.id,
                    order_id=str(order_id),
                    market_hash_name=market_hash_name,
                    price_cents=price_cents,
                    quantity=quantity,
                    order_type=order_type,  # Используем определенный тип
                    float_min=float_min,  # Сохраняем float range
                    float_max=float_max,
                    def_index=def_index,  # Сохраняем DefIndex/PaintIndex
                    paint_index=paint_index,
                    outbid_count=0,
                    max_price_cents=price_cents * 2,  # Устанавливаем макс цену в 2 раза выше текущей
                    is_active=True
                )
                session.add(new_order)
                synced_count += 1

        # Деактивируем ордера, которых больше нет на CSFloat
        # (например, выполненные или отмененные вручную)
        result = await session.execute(
            select(BuyOrder).where(
                BuyOrder.account_id == account.id,
                BuyOrder.is_active == True
            )
        )
        all_db_orders = result.scalars().all()

        for db_order in all_db_orders:
            if db_order.order_id not in csfloat_order_ids:
                # Ордер есть в БД, но нет на CSFloat - деактивируем
                db_order.is_active = False
                db_order.updated_at = datetime.utcnow()
                deactivated_count += 1
                logger.info(f"Deactivated missing order: {db_order.order_id} ({db_order.market_hash_name[:50]}...)")

        await session.commit()

        logger.info(
            f"Synced {synced_count} new orders, updated {updated_count}, "
            f"deactivated {deactivated_count} for account {account.name}"
        )

        return {
            "status": "success",
            "synced": synced_count,
            "updated": updated_count,
            "deactivated": deactivated_count,
            "total": synced_count + updated_count
        }

    except Exception as e:
        logger.error(f"Error syncing orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# === Buy Orders API ===

@app.get("/api/orders")
async def get_orders(
    active_only: bool = False,
    session: AsyncSession = Depends(get_db)
):
    """Получить все ордера"""
    query = select(BuyOrder)
    if active_only:
        query = query.where(BuyOrder.is_active == True)

    result = await session.execute(query.order_by(desc(BuyOrder.created_at)))
    orders = result.scalars().all()

    return [
        {
            "id": order.id,
            "account_id": order.account_id,
            "order_id": order.order_id,
            "market_hash_name": order.market_hash_name,
            "price_cents": order.price_cents,
            "price_usd": order.price_cents / 100,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "float_min": order.float_min,
            "float_max": order.float_max,
            "outbid_count": order.outbid_count,
            "max_price_cents": order.max_price_cents,
            "is_active": order.is_active,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat()
        }
        for order in orders
    ]


@app.post("/api/orders")
async def create_order(
    order_data: BuyOrderCreate,
    session: AsyncSession = Depends(get_db)
):
    """Создать новый ордер (для ручного добавления в БД)"""
    # TODO: Можно добавить автоматическое создание через API
    # Пока просто сохраняем в БД для отслеживания
    raise HTTPException(
        status_code=501,
        detail="Creating orders through API not yet implemented. Create orders directly on CSFloat and they will be tracked automatically."
    )


@app.delete("/api/orders/{order_id}")
async def delete_order(
    order_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Отменить ордер"""
    try:
        # Находим ордер
        result = await session.execute(
            select(BuyOrder).where(BuyOrder.order_id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Получаем аккаунт
        result = await session.execute(
            select(Account).where(Account.id == order.account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Удаляем через API
        manager = AccountManager(session)
        client = manager.get_client(account)

        if order.order_type == "simple":
            await client.delete_buy_order(order_id)
        else:
            from bot.advanced_api import AdvancedOrderAPI
            api = AdvancedOrderAPI(account.api_key, account.proxy)
            await api.delete_advanced_order(order_id)
            await api.close()

        # Помечаем как неактивный в БД
        order.is_active = False
        await session.commit()

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error deleting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Outbid History API ===

@app.get("/api/history")
async def get_history(
    limit: int = 100,
    session: AsyncSession = Depends(get_db)
):
    """Получить историю перебивов"""
    result = await session.execute(
        select(OutbidHistory)
        .order_by(desc(OutbidHistory.timestamp))
        .limit(limit)
    )
    history = result.scalars().all()

    return [
        {
            "id": h.id,
            "account_id": h.account_id,
            "order_id": h.order_id,
            "market_hash_name": h.market_hash_name,
            "old_price_cents": h.old_price_cents,
            "old_price_usd": h.old_price_cents / 100,
            "new_price_cents": h.new_price_cents,
            "new_price_usd": h.new_price_cents / 100,
            "competitor_price_cents": h.competitor_price_cents,
            "competitor_price_usd": h.competitor_price_cents / 100,
            "timestamp": h.timestamp.isoformat()
        }
        for h in history
    ]


# === Settings API ===

@app.get("/api/settings")
async def get_settings():
    """Получить настройки"""
    return {
        "check_interval": settings.check_interval,
        "outbid_step": settings.outbid_step,
        "max_outbids": settings.max_outbids
    }


@app.put("/api/settings")
async def update_settings(settings_data: SettingsUpdate):
    """Обновить настройки"""
    # TODO: Сохранять в БД или файл
    # Пока обновляем только в памяти
    if settings_data.check_interval is not None:
        old_value = settings.check_interval
        settings.check_interval = settings_data.check_interval
        logger.info(f"Updated check_interval: {old_value} -> {settings.check_interval}")
    if settings_data.outbid_step is not None:
        old_value = settings.outbid_step
        settings.outbid_step = settings_data.outbid_step
        logger.info(f"Updated outbid_step: {old_value} -> {settings.outbid_step}")
    if settings_data.max_outbids is not None:
        old_value = settings.max_outbids
        settings.max_outbids = settings_data.max_outbids
        logger.info(f"Updated max_outbids: {old_value} -> {settings.max_outbids}")

    return {"status": "success"}


# === Health Check ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
