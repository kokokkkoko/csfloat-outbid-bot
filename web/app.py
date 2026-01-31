"""
FastAPI Web Interface для CSFloat Bot
"""
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from database import db, get_db, Account, BuyOrder, OutbidHistory, User, AppSettings
from accounts import AccountManager
from bot.manager import bot_manager
from config import settings
from auth import (
    get_current_user, get_current_user_optional, require_admin,
    authenticate_user, create_user, create_access_token, get_password_hash,
    decode_token
)
from websocket_manager import ws_manager, WSEventType, create_ws_message


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
    max_outbid_multiplier: Optional[float] = None
    max_outbid_premium: Optional[float] = None  # в долларах, конвертируем в центы


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


# Создаем FastAPI приложение
app = FastAPI(
    title="CSFloat Outbid Bot",
    description="Automatic buy order outbidding bot for CSFloat",
    version="1.0.0"
)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Проверяем наличие React build и подключаем его
REACT_BUILD_PATH = Path("frontend/dist")
REACT_INDEX_PATH = REACT_BUILD_PATH / "index.html"
USE_REACT_SPA = REACT_BUILD_PATH.exists() and REACT_INDEX_PATH.exists()

if USE_REACT_SPA:
    # Монтируем статические файлы React (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(REACT_BUILD_PATH / "assets")), name="react-assets")
    logger.info(f"React SPA enabled from {REACT_BUILD_PATH}")
else:
    logger.info("React build not found, using Jinja2 templates")


# === Startup/Shutdown Events ===

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Starting web application...")
    await db.init()

    # Load settings from database (overrides environment variables)
    async for session in db.get_session():
        result = await session.execute(select(AppSettings))
        db_settings = result.scalars().all()

        for setting in db_settings:
            if setting.key == "check_interval":
                settings.check_interval = int(setting.value)
                logger.info(f"Loaded check_interval from DB: {settings.check_interval}")
            elif setting.key == "outbid_step":
                settings.outbid_step = float(setting.value)
                logger.info(f"Loaded outbid_step from DB: {settings.outbid_step}")
            elif setting.key == "max_outbids":
                settings.max_outbids = int(setting.value)
                logger.info(f"Loaded max_outbids from DB: {settings.max_outbids}")
            elif setting.key == "max_outbid_multiplier":
                settings.max_outbid_multiplier = float(setting.value)
                logger.info(f"Loaded max_outbid_multiplier from DB: {settings.max_outbid_multiplier}")
            elif setting.key == "max_outbid_premium_cents":
                settings.max_outbid_premium_cents = int(setting.value)
                logger.info(f"Loaded max_outbid_premium_cents from DB: {settings.max_outbid_premium_cents}")

        break  # Exit after first session

    logger.success("Web application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("Shutting down...")
    await bot_manager.stop()
    await db.close()
    logger.success("Application stopped")


# === Web Pages ===

def serve_react_or_template(request: Request, template_name: str):
    """Отдаёт React SPA если билд есть, иначе Jinja2 шаблон"""
    if USE_REACT_SPA:
        return FileResponse(str(REACT_INDEX_PATH))
    return templates.TemplateResponse(template_name, {"request": request})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница"""
    return serve_react_or_template(request, "index.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return serve_react_or_template(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    return serve_react_or_template(request, "register.html")


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


# === Authentication API ===

@app.post("/api/auth/login")
async def login(
    user_data: UserLogin,
    session: AsyncSession = Depends(get_db)
):
    """Авторизация пользователя"""
    user = await authenticate_user(session, user_data.username, user_data.password)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await session.commit()

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }
    }


@app.post("/api/auth/register")
async def register(
    user_data: UserRegister,
    session: AsyncSession = Depends(get_db)
):
    """Регистрация нового пользователя"""
    if not settings.allow_registration:
        raise HTTPException(
            status_code=403,
            detail="Registration is currently disabled"
        )

    # Validate username
    if len(user_data.username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters"
        )

    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters"
        )

    try:
        user = await create_user(
            session=session,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            is_admin=False
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }
    }


@app.get("/api/auth/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о текущем пользователе"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at.isoformat()
    }


@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Выход пользователя"""
    logger.info(f"User logged out: {current_user.username}")
    return {"status": "success", "message": "Logged out successfully"}


# === Accounts API ===

@app.get("/api/accounts")
async def get_accounts(
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Получить аккаунты (фильтрация по user_id если авторизован)"""
    manager = AccountManager(session)

    if current_user and not current_user.is_admin:
        # Regular user sees only their accounts
        accounts = await manager.get_accounts_by_user(current_user.id)
    else:
        # Admin or unauthenticated (for backward compatibility) sees all
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
            "error_message": acc.error_message,
            "user_id": acc.user_id
        }
        for acc in accounts
    ]


@app.post("/api/accounts")
async def create_account(
    account_data: AccountCreate,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Создать новый аккаунт"""
    try:
        manager = AccountManager(session)
        account = await manager.create_account(
            name=account_data.name,
            api_key=account_data.api_key,
            proxy=account_data.proxy,
            user_id=current_user.id if current_user else None
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

            # Проверяем, есть ли уже в БД ДЛЯ ЭТОГО АККАУНТА
            result = await session.execute(
                select(BuyOrder).where(
                    BuyOrder.order_id == str(order_id),
                    BuyOrder.account_id == account.id
                )
            )
            existing_order = result.scalar_one_or_none()

            # Определяем тип ордера и название предмета
            expression = cf_order.get('expression', '')
            market_hash_name_field = cf_order.get('market_hash_name', '')
            icon_url = None  # Для иконки скина

            # Логируем для отладки
            logger.info(f"Order {order_id}: expression={expression[:100] if expression else 'None'}..., market_hash_name_field={market_hash_name_field}")

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

                # 2. Проверяем есть ли Item == "название" в expression (поддерживаем разные кавычки)
                if not market_hash_name:
                    # Пробуем разные паттерны кавычек: "", '', «», и без кавычек
                    item_patterns = [
                        r'Item\s*==\s*"([^"]+)"',           # Item == "name"
                        r"Item\s*==\s*'([^']+)'",           # Item == 'name'
                        r'Item\s*==\s*«([^»]+)»',           # Item == «name»
                        r'Item\s*==\s*"([^"]+)"',           # Item == "name" (unicode quotes)
                    ]
                    for pattern in item_patterns:
                        item_match = re.search(pattern, expression)
                        if item_match:
                            market_hash_name = item_match.group(1)
                            logger.info(f"Extracted item name from expression: {market_hash_name}")
                            break

                # 3. Если всё ещё нет, получаем через CSFloat API напрямую
                if not market_hash_name:
                    if def_index and paint_index:
                        try:
                            logger.info(f"Fetching skin info from CSFloat: def={def_index}, paint={paint_index}")
                            listings_response = await client.get_all_listings(
                                def_index=def_index,
                                paint_index=paint_index,
                                limit=1
                            )
                            logger.info(f"CSFloat listings response: {type(listings_response)}")

                            if listings_response:
                                # Может быть dict или объект с атрибутом listings
                                listings = None
                                if isinstance(listings_response, dict):
                                    listings = listings_response.get("data") or listings_response.get("listings") or []
                                elif hasattr(listings_response, 'listings'):
                                    listings = listings_response.listings
                                elif hasattr(listings_response, 'data'):
                                    listings = listings_response.data

                                logger.info(f"Found {len(listings) if listings else 0} listings")

                                if listings and len(listings) > 0:
                                    first = listings[0]
                                    # Получаем item object
                                    item_obj = first.get("item", {}) if isinstance(first, dict) else getattr(first, 'item', None)

                                    if item_obj:
                                        # Извлекаем имя
                                        if isinstance(item_obj, dict):
                                            item_name = item_obj.get("item_name") or item_obj.get("name") or item_obj.get("market_hash_name", "")
                                            icon_url = item_obj.get("icon_url")
                                        else:
                                            item_name = getattr(item_obj, 'item_name', None) or getattr(item_obj, 'name', None) or getattr(item_obj, 'market_hash_name', "")
                                            icon_url = getattr(item_obj, 'icon_url', None)

                                        # Убираем wear из имени если есть
                                        if item_name and " (" in item_name:
                                            item_name = item_name.rsplit(" (", 1)[0]

                                        logger.info(f"Extracted from CSFloat: name={item_name}, icon={'yes' if icon_url else 'no'}")

                                        if item_name:
                                            # Добавляем wear на основе float range
                                            wear = ""
                                            if float_min is not None and float_max is not None:
                                                avg = (float_min + float_max) / 2
                                                if avg < 0.07: wear = "Factory New"
                                                elif avg < 0.15: wear = "Minimal Wear"
                                                elif avg < 0.38: wear = "Field-Tested"
                                                elif avg < 0.45: wear = "Well-Worn"
                                                else: wear = "Battle-Scarred"

                                            market_hash_name = f"{item_name} ({wear})" if wear else item_name

                        except Exception as e:
                            logger.error(f"Error fetching skin info: {e}")

                    # Fallback если ничего не получилось
                    if not market_hash_name:
                        from skin_lookup import WEAPON_NAMES, get_wear_name
                        weapon = WEAPON_NAMES.get(def_index, f"Weapon #{def_index}") if def_index else "Unknown"
                        wear = get_wear_name(float_min, float_max) if float_min or float_max else ""
                        market_hash_name = f"{weapon} | Skin #{paint_index} ({wear})" if wear else f"{weapon} | Skin #{paint_index}"
                        logger.warning(f"Using fallback name: {market_hash_name}")
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

                # Получаем icon_url для simple order
                try:
                    if market_hash_name and market_hash_name != 'Unknown':
                        listings_response = await client.get_all_listings(
                            market_hash_name=market_hash_name,
                            limit=1,
                            type_="buy_now"
                        )
                        if listings_response and "listings" in listings_response:
                            listings = listings_response["listings"]
                            if listings and len(listings) > 0:
                                first_listing = listings[0]
                                if first_listing.item and first_listing.item.icon_url:
                                    icon_url = first_listing.item.icon_url
                                    logger.info(f"Fetched icon_url for simple order: {icon_url[:50]}...")
                except Exception as e:
                    logger.debug(f"Could not fetch icon for {market_hash_name}: {e}")

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
                if icon_url:
                    existing_order.icon_url = icon_url  # Обновляем иконку
                existing_order.is_active = True
                existing_order.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Создаем новый
                new_order = BuyOrder(
                    account_id=account.id,
                    order_id=str(order_id),
                    market_hash_name=market_hash_name,
                    icon_url=icon_url,  # Сохраняем иконку
                    price_cents=price_cents,
                    quantity=quantity,
                    order_type=order_type,  # Используем определенный тип
                    float_min=float_min,  # Сохраняем float range
                    float_max=float_max,
                    def_index=def_index,  # Сохраняем DefIndex/PaintIndex
                    paint_index=paint_index,
                    outbid_count=0,
                    max_price_cents=None,  # Будет рассчитан динамически от lowest listing при перебивании
                    is_active=True
                )
                try:
                    session.add(new_order)
                    await session.flush()  # Flush to catch IntegrityError immediately
                    synced_count += 1
                except IntegrityError:
                    # Ордер уже существует (возможно, был создан другим запросом)
                    await session.rollback()
                    logger.warning(f"Order {order_id} already exists, updating instead")
                    # Пробуем найти и обновить
                    result = await session.execute(
                        select(BuyOrder).where(BuyOrder.order_id == str(order_id))
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.price_cents = price_cents
                        existing.quantity = quantity
                        existing.is_active = True
                        existing.updated_at = datetime.utcnow()
                        if icon_url:
                            existing.icon_url = icon_url
                        updated_count += 1

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
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Получить ордера (фильтрация по user_id если авторизован)"""
    # Build query with optional user filtering
    if current_user and not current_user.is_admin:
        # Regular user: filter orders through their accounts
        query = (
            select(BuyOrder)
            .join(Account, BuyOrder.account_id == Account.id)
            .where(Account.user_id == current_user.id)
        )
    else:
        # Admin or unauthenticated: see all orders
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
            "icon_url": order.icon_url,
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
    session: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Получить историю перебивов (фильтрация по user_id если авторизован)"""
    # Build query with optional user filtering
    if current_user and not current_user.is_admin:
        # Regular user: filter history through their accounts
        query = (
            select(OutbidHistory)
            .join(Account, OutbidHistory.account_id == Account.id)
            .where(Account.user_id == current_user.id)
            .order_by(desc(OutbidHistory.timestamp))
            .limit(limit)
        )
    else:
        # Admin or unauthenticated: see all history
        query = (
            select(OutbidHistory)
            .order_by(desc(OutbidHistory.timestamp))
            .limit(limit)
        )

    result = await session.execute(query)
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
        "max_outbids": settings.max_outbids,
        "max_outbid_multiplier": settings.max_outbid_multiplier,
        "max_outbid_premium": settings.max_outbid_premium_cents / 100,  # центы -> доллары
        "admin_enabled": settings.admin_enabled
    }


@app.put("/api/settings")
async def update_settings(settings_data: SettingsUpdate, session: AsyncSession = Depends(get_db)):
    """Обновить настройки"""
    async def save_setting(key: str, value):
        """Save a setting to database"""
        result = await session.execute(select(AppSettings).where(AppSettings.key == key))
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = AppSettings(key=key, value=str(value))
            session.add(setting)
        await session.commit()

    # Update runtime settings and save to database
    if settings_data.check_interval is not None:
        old_value = settings.check_interval
        settings.check_interval = settings_data.check_interval
        await save_setting("check_interval", settings_data.check_interval)
        logger.info(f"Updated check_interval: {old_value} -> {settings.check_interval} (saved to DB)")
    if settings_data.outbid_step is not None:
        old_value = settings.outbid_step
        settings.outbid_step = settings_data.outbid_step
        await save_setting("outbid_step", settings_data.outbid_step)
        logger.info(f"Updated outbid_step: {old_value} -> {settings.outbid_step} (saved to DB)")
    if settings_data.max_outbids is not None:
        old_value = settings.max_outbids
        settings.max_outbids = settings_data.max_outbids
        await save_setting("max_outbids", settings_data.max_outbids)
        logger.info(f"Updated max_outbids: {old_value} -> {settings.max_outbids} (saved to DB)")
    if settings_data.max_outbid_multiplier is not None:
        old_value = settings.max_outbid_multiplier
        settings.max_outbid_multiplier = settings_data.max_outbid_multiplier
        await save_setting("max_outbid_multiplier", settings_data.max_outbid_multiplier)
        logger.info(f"Updated max_outbid_multiplier: {old_value} -> {settings.max_outbid_multiplier} (saved to DB)")
    if settings_data.max_outbid_premium is not None:
        old_value = settings.max_outbid_premium_cents
        settings.max_outbid_premium_cents = int(settings_data.max_outbid_premium * 100)  # доллары -> центы
        await save_setting("max_outbid_premium_cents", settings.max_outbid_premium_cents)
        logger.info(f"Updated max_outbid_premium_cents: {old_value} -> {settings.max_outbid_premium_cents} (saved to DB)")

    return {"status": "success"}


# === Health Check ===

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# === WebSocket ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    # Try to get user_id from query parameter (token)
    user_id = None
    token = websocket.query_params.get("token")
    if token:
        try:
            payload = decode_token(token)
            if payload:
                user_id = payload.get("user_id")
        except Exception:
            pass  # Continue without user_id

    client_id = await ws_manager.connect(websocket, user_id)

    try:
        # Send welcome message with current status
        await websocket.send_json(create_ws_message(
            WSEventType.NOTIFICATION,
            data={"level": "info", "connections": ws_manager.get_connection_count()},
            message="Connected to WebSocket"
        ))

        # Send current bot status
        status = await bot_manager.get_status()
        await websocket.send_json(create_ws_message(
            WSEventType.BOT_STATUS_CHANGED,
            data=status
        ))

        # Listen for messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle ping
                if data.get("type") == WSEventType.PING:
                    await websocket.send_json(create_ws_message(WSEventType.PONG))

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for {client_id}: {e}")
                break

    finally:
        ws_manager.disconnect(client_id, user_id)


@app.get("/api/ws/status")
async def websocket_status():
    """Get WebSocket connection statistics"""
    return {
        "active_connections": ws_manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }


# === Admin Panel (conditionally enabled) ===

if settings.admin_enabled:
    logger.info("Admin panel ENABLED (ADMIN_ENABLED=true)")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request):
        """Admin panel page"""
        return templates.TemplateResponse("admin.html", {"request": request})

    @app.get("/api/admin/stats")
    async def get_admin_stats(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_admin)
    ):
        """Get admin dashboard statistics"""
        from datetime import timedelta

        # Count users
        result = await session.execute(select(User))
        total_users = len(result.scalars().all())

        # Count active accounts
        result = await session.execute(
            select(Account).where(Account.is_active == True)
        )
        active_accounts = len(result.scalars().all())

        # Count active orders
        result = await session.execute(
            select(BuyOrder).where(BuyOrder.is_active == True)
        )
        active_orders = len(result.scalars().all())

        # Count outbids in last 24 hours
        yesterday = datetime.utcnow() - timedelta(hours=24)
        result = await session.execute(
            select(OutbidHistory).where(OutbidHistory.timestamp >= yesterday)
        )
        outbids_24h = len(result.scalars().all())

        return {
            "total_users": total_users,
            "active_accounts": active_accounts,
            "active_orders": active_orders,
            "outbids_24h": outbids_24h
        }

    @app.get("/api/admin/users")
    async def get_admin_users(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_admin)
    ):
        """Get all users for admin panel"""
        result = await session.execute(select(User).order_by(User.created_at))
        users = result.scalars().all()

        return [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
            for user in users
        ]

    class AdminUserUpdate(BaseModel):
        is_active: Optional[bool] = None
        is_admin: Optional[bool] = None

    @app.put("/api/admin/users/{user_id}")
    async def update_admin_user(
        user_id: int,
        user_data: AdminUserUpdate,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_admin)
    ):
        """Update user as admin"""
        # Find user
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent self-demotion
        if user.id == current_user.id:
            if user_data.is_admin == False:
                raise HTTPException(status_code=400, detail="Cannot remove your own admin status")
            if user_data.is_active == False:
                raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

        # Update fields
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        if user_data.is_admin is not None:
            user.is_admin = user_data.is_admin

        await session.commit()

        return {"status": "success"}

    # Simple in-memory log storage for admin panel
    _admin_logs = []
    MAX_LOGS = 500

    def add_admin_log(level: str, message: str):
        """Add a log entry for admin panel"""
        global _admin_logs
        _admin_logs.append({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level.upper(),
            "message": message
        })
        # Keep only last MAX_LOGS entries
        if len(_admin_logs) > MAX_LOGS:
            _admin_logs = _admin_logs[-MAX_LOGS:]

    # Hook into loguru for admin logs
    def setup_admin_logging():
        """Setup loguru to capture logs for admin panel"""
        def admin_sink(message):
            record = message.record
            add_admin_log(record["level"].name, record["message"])

        logger.add(admin_sink, format="{message}", level="DEBUG")

    # Initialize admin logging
    setup_admin_logging()

    @app.get("/api/admin/logs")
    async def get_admin_logs(
        level: Optional[str] = None,
        limit: int = 100,
        current_user: User = Depends(require_admin)
    ):
        """Get system logs for admin panel"""
        logs = _admin_logs.copy()

        # Filter by level if specified
        if level:
            logs = [log for log in logs if log["level"].lower() == level.lower()]

        # Return last N logs
        return logs[-limit:]

else:
    logger.info("Admin panel DISABLED (ADMIN_ENABLED=false)")

    # Return 404 for all admin routes when disabled
    @app.get("/admin")
    async def admin_disabled():
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/api/admin/{path:path}")
    async def admin_api_disabled(path: str):
        raise HTTPException(status_code=404, detail="Not found")


# === SPA Catch-All Route (должен быть последним!) ===
# Обрабатывает все остальные маршруты для React Router

if USE_REACT_SPA:
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Catch-all route для React SPA (обрабатывает client-side routing)"""
        # Не обрабатываем API и WebSocket запросы
        if full_path.startswith(("api/", "ws", "static/", "assets/", "health")):
            raise HTTPException(status_code=404, detail="Not found")

        # Проверяем, есть ли файл в корне React build (vite.svg, favicon.ico и т.д.)
        static_file = REACT_BUILD_PATH / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(str(static_file))

        # Отдаём React index.html для всех остальных маршрутов
        return FileResponse(str(REACT_INDEX_PATH))
