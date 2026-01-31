"""
Bot Manager - главный координатор работы бота
"""
import asyncio
import random
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database import Account, BuyOrder, db
from accounts import AccountManager
from config import settings
from .advanced_api import AdvancedOrderAPI
from .outbid_logic import OutbidLogic


async def rate_limit_delay(min_delay: float = 2.0, max_delay: float = 5.0):
    """Add random delay between API requests to avoid rate limiting"""
    delay = random.uniform(min_delay, max_delay)
    logger.debug(f"Rate limit delay: {delay:.1f}s")
    await asyncio.sleep(delay)

# Import WebSocket broadcast functions (optional, fails gracefully if not available)
try:
    from websocket_manager import broadcast_bot_status, broadcast_order_outbid, broadcast_account_update
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False


class BotManager:
    """Главный менеджер бота для автоматического перебивания"""

    def __init__(self):
        self.is_running = False
        self.tasks: List[asyncio.Task] = []
        self._advanced_apis: Dict[int, AdvancedOrderAPI] = {}

    async def start(self):
        """Запустить бота"""
        if self.is_running:
            logger.warning("Bot is already running")
            return

        self.is_running = True
        logger.info("Starting CSFloat Outbid Bot...")

        # Запускаем главный цикл
        task = asyncio.create_task(self._main_loop())
        self.tasks.append(task)

        logger.success("Bot started successfully")

        # Broadcast status change via WebSocket
        if WS_ENABLED:
            try:
                await broadcast_bot_status(True, settings.check_interval)
            except Exception as e:
                logger.debug(f"WebSocket broadcast failed: {e}")

    async def stop(self):
        """Остановить бота"""
        if not self.is_running:
            logger.warning("Bot is not running")
            return

        logger.info("Stopping bot...")
        self.is_running = False

        # Отменяем все задачи
        for task in self.tasks:
            task.cancel()

        # Ждем завершения
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        # Закрываем все advanced API клиенты
        for api in self._advanced_apis.values():
            await api.close()
        self._advanced_apis.clear()

        logger.success("Bot stopped")

        # Broadcast status change via WebSocket
        if WS_ENABLED:
            try:
                await broadcast_bot_status(False, settings.check_interval)
            except Exception as e:
                logger.debug(f"WebSocket broadcast failed: {e}")

    async def _main_loop(self):
        """Главный цикл проверки и перебивания"""
        while self.is_running:
            try:
                await self._check_and_outbid_all()
            except asyncio.CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            # Ждем следующую итерацию
            await asyncio.sleep(settings.check_interval)

    async def _check_and_outbid_all(self):
        """Проверить все аккаунты и их ордера"""
        async for session in db.get_session():
            try:
                account_manager = AccountManager(session)
                accounts = await account_manager.get_active_accounts()

                if not accounts:
                    logger.debug("No active accounts found")
                    return

                logger.info(f"Checking {len(accounts)} active accounts...")

                # Проверяем каждый аккаунт ПОСЛЕДОВАТЕЛЬНО с задержками
                # (параллельная проверка вызывает rate limiting)
                for idx, account in enumerate(accounts, 1):
                    try:
                        # Cooldown между аккаунтами (кроме первого)
                        if idx > 1:
                            logger.info(f"Cooldown before checking account {idx}/{len(accounts)}...")
                            await rate_limit_delay(10.0, 15.0)

                        await self._check_account(session, account)
                    except Exception as e:
                        logger.error(f"Error checking account {account.name}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error checking accounts: {e}", exc_info=True)

    async def _check_account(self, session: AsyncSession, account: Account):
        """Проверить ордера одного аккаунта"""
        try:
            logger.debug(f"Checking account: {account.name}")

            account_manager = AccountManager(session)
            client = account_manager.get_client(account)

            # Получаем активные ордера из БД
            result = await session.execute(
                select(BuyOrder).where(
                    BuyOrder.account_id == account.id,
                    BuyOrder.is_active == True
                )
            )
            orders = list(result.scalars().all())

            if not orders:
                logger.debug(f"No active orders for {account.name}")
                await account_manager.update_account_status(account.id, "online")
                return

            logger.info(f"Found {len(orders)} active orders for {account.name}")

            # Проверяем каждый ордер с задержкой между проверками
            for idx, order in enumerate(orders, 1):
                try:
                    # Cooldown между проверками ордеров (кроме первого)
                    if idx > 1:
                        logger.debug(f"Cooldown before checking order {idx}/{len(orders)}...")
                        await rate_limit_delay(5.0, 10.0)

                    logger.info(
                        f"[{idx}/{len(orders)}] Checking order {order.order_id} ({order.order_type}): "
                        f"{order.market_hash_name} @ ${order.price_cents/100:.2f}"
                    )
                    await self._check_and_outbid_order(session, account, client, order)
                except Exception as e:
                    logger.error(
                        f"Error checking order {order.order_id} "
                        f"for {account.name}: {e}", exc_info=True
                    )

            await account_manager.update_account_status(account.id, "online")

        except Exception as e:
            logger.error(f"Error checking account {account.name}: {e}", exc_info=True)
            account_manager = AccountManager(session)
            await account_manager.update_account_status(
                account.id,
                "error",
                str(e)
            )

    async def _check_and_outbid_order(
        self,
        session: AsyncSession,
        account: Account,
        client,
        order: BuyOrder
    ):
        """
        Проверить и перебить конкретный ордер при необходимости

        Args:
            session: DB сессия
            account: Аккаунт
            client: CSFloat клиент
            order: Ордер для проверки
        """
        try:
            logger.debug(
                f"_check_and_outbid_order: order_type={order.order_type}, "
                f"def_index={order.def_index}, paint_index={order.paint_index}, "
                f"float_range=[{order.float_min}-{order.float_max}]"
            )

            # Получаем топовый buy order для этого предмета
            competitor_price = await self._get_top_buy_price(
                client,
                order
            )

            if competitor_price is None:
                logger.debug(f"No competitor orders for {order.market_hash_name}")
                return

            # Получаем lowest listing price для расчёта потолка
            outbid_logic = OutbidLogic(session)
            price_ceiling = None

            lowest_listing_price = await self._get_lowest_listing_price(client, order)
            if lowest_listing_price:
                price_ceiling = outbid_logic.calculate_price_ceiling(lowest_listing_price)
                logger.info(
                    f"Price ceiling for {order.market_hash_name}: ${price_ceiling/100:.2f} "
                    f"(from lowest listing: ${lowest_listing_price/100:.2f})"
                )
            else:
                # Fallback: используем среднюю цену последних продаж
                logger.info(f"No active listings found, checking sales history...")
                avg_sale_price = await self._get_average_sale_price(client, order)
                if avg_sale_price:
                    price_ceiling = outbid_logic.calculate_price_ceiling(avg_sale_price)
                    logger.info(
                        f"Price ceiling for {order.market_hash_name}: ${price_ceiling/100:.2f} "
                        f"(from avg sale price: ${avg_sale_price/100:.2f})"
                    )
                else:
                    logger.warning(
                        f"No price ceiling available for {order.market_hash_name} "
                        f"(no listings and no sales history)"
                    )

            # Проверяем, нужно ли перебивать (с учётом потолка)
            should_outbid, reason = outbid_logic.should_outbid(order, competitor_price, price_ceiling)

            if not should_outbid:
                logger.info(
                    f"No outbid for {order.market_hash_name}: {reason}"
                )
                return

            # Рассчитываем новую цену
            new_price = outbid_logic.calculate_new_price(competitor_price)

            logger.info(
                f"Outbidding {order.market_hash_name}: "
                f"${order.price_cents/100:.2f} -> ${new_price/100:.2f}"
            )

            # Удаляем старый ордер
            await self._delete_order(account, client, order)

            # Создаем новый ордер с новой ценой
            new_order_id = await self._create_order(
                account,
                client,
                order.market_hash_name,
                new_price,
                order.quantity,
                order.order_type,
                order.float_min,
                order.float_max,
                order.def_index,
                order.paint_index
            )

            if new_order_id:
                # Записываем перебив в историю
                old_price = order.price_cents
                await outbid_logic.record_outbid(
                    account,
                    order,
                    old_price,
                    new_price,
                    competitor_price
                )

                # Обновляем order_id
                order.order_id = new_order_id
                await session.commit()

                logger.success(
                    f"Successfully outbid {order.market_hash_name} "
                    f"(new order: {new_order_id})"
                )

                # Broadcast outbid event via WebSocket
                if WS_ENABLED:
                    try:
                        await broadcast_order_outbid(
                            order_id=new_order_id,
                            market_hash_name=order.market_hash_name,
                            old_price=old_price,
                            new_price=new_price,
                            competitor_price=competitor_price
                        )
                    except Exception as ws_err:
                        logger.debug(f"WebSocket broadcast failed: {ws_err}")

        except Exception as e:
            logger.error(f"Error in outbid process: {e}", exc_info=True)
            raise

    async def _get_lowest_listing_price(
        self,
        client,
        order: BuyOrder
    ) -> Optional[int]:
        """
        Получить цену самого дешёвого листинга (sell order) для предмета

        Используется для расчёта потолка цены перебивания.

        Args:
            client: CSFloat клиент
            order: Ордер

        Returns:
            Цена в центах или None если листингов нет
        """
        try:
            # Rate limiting delay
            await rate_limit_delay(1.0, 2.0)

            if order.order_type == "advanced":
                # Для advanced orders - фильтруем по def_index, paint_index и float range
                response = await client.get_all_listings(
                    def_index=order.def_index,
                    paint_index=order.paint_index,
                    min_float=order.float_min,
                    max_float=order.float_max,
                    category=1,  # Только normal (не StatTrak)
                    sort_by='lowest_price',
                    limit=1,
                    type_='buy_now'
                )
            else:
                # Для simple orders - по market_hash_name
                response = await client.get_all_listings(
                    market_hash_name=order.market_hash_name,
                    sort_by='lowest_price',
                    limit=1,
                    type_='buy_now'
                )

            if response and response.get('listings') and len(response['listings']) > 0:
                lowest_listing = response['listings'][0]
                lowest_price = lowest_listing.price
                logger.debug(
                    f"Lowest listing price for {order.market_hash_name}: ${lowest_price/100:.2f}"
                )
                return lowest_price

            logger.debug(f"No sell listings found for {order.market_hash_name}")
            return None

        except Exception as e:
            logger.warning(f"Error getting lowest listing price for {order.market_hash_name}: {e}")
            return None

    async def _get_average_sale_price(
        self,
        client,
        order: BuyOrder,
        limit: int = 50
    ) -> Optional[int]:
        """
        Получить среднюю цену последних продаж для предмета (fallback когда нет листингов)

        Args:
            client: CSFloat клиент
            order: Ордер
            limit: Количество продаж для анализа

        Returns:
            Средняя цена в центах или None если продаж нет
        """
        try:
            import urllib.parse

            # Rate limiting delay
            await rate_limit_delay(1.0, 2.0)

            # URL-encode market_hash_name для запроса
            encoded_name = urllib.parse.quote(order.market_hash_name)
            url = f"https://csfloat.com/api/v1/history/{encoded_name}/sales"

            params = {
                'paint_index': order.paint_index,
                'limit': limit
            }

            # Делаем запрос через aiohttp session клиента
            async with client._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Failed to get sales history: {response.status}")
                    return None

                sales_data = await response.json()

                if not sales_data or len(sales_data) == 0:
                    logger.debug(f"No sales history found for {order.market_hash_name}")
                    return None

                # Фильтруем продажи по float range (для advanced orders)
                if order.order_type == "advanced" and order.float_min and order.float_max:
                    filtered_sales = [
                        sale for sale in sales_data
                        if order.float_min <= sale['item']['float_value'] <= order.float_max
                    ]
                else:
                    filtered_sales = sales_data

                if not filtered_sales:
                    logger.debug(
                        f"No sales in float range [{order.float_min}-{order.float_max}] "
                        f"for {order.market_hash_name}"
                    )
                    return None

                # Берем последние 10 продаж
                recent_sales = filtered_sales[:10]
                prices = [sale['price'] for sale in recent_sales]
                avg_price = int(sum(prices) / len(prices))

                logger.info(
                    f"Average sale price for {order.market_hash_name} "
                    f"(last {len(recent_sales)} sales, float {order.float_min}-{order.float_max}): "
                    f"${avg_price/100:.2f}"
                )

                return avg_price

        except Exception as e:
            logger.warning(f"Error getting average sale price for {order.market_hash_name}: {e}")
            return None

    async def _get_top_buy_price(
        self,
        client,
        order: BuyOrder
    ) -> Optional[int]:
        """
        Получить цену топового buy order для предмета

        Для simple orders:
        1. Найти листинг по market_hash_name
        2. Получить buy orders для этого листинга
        3. Вернуть цену топового buy order

        Для advanced orders:
        1. Найти листинг по def_index и paint_index
        2. Получить buy orders для этого листинга
        3. Отфильтровать только те, у которых float диапазон пересекается с нашим
        4. Вернуть максимальную цену среди отфильтрованных
        """
        try:
            logger.info(
                f"_get_top_buy_price: Searching for {order.order_type} order, "
                f"item={order.market_hash_name}"
            )

            # Rate limiting delay before API calls
            await rate_limit_delay(1.0, 2.5)

            # Шаг 1: Найти листинг
            if order.order_type == "simple":
                # Для simple orders ищем по market_hash_name
                logger.debug(f"Searching simple order by market_hash_name={order.market_hash_name}")
                listings_response = await client.get_all_listings(
                    market_hash_name=order.market_hash_name,
                    limit=1,
                    type_="buy_now"
                )
            else:
                # Для advanced orders ищем по def_index и paint_index
                if not order.def_index or not order.paint_index:
                    logger.warning(f"Advanced order {order.order_id} missing def_index or paint_index")
                    return None

                logger.debug(
                    f"Searching advanced order by def_index={order.def_index}, "
                    f"paint_index={order.paint_index}, float=[{order.float_min}-{order.float_max}]"
                )

                # category: 0 = any, 1 = normal, 2 = stattrak, 3 = souvenir
                # Стратегия: Сначала пробуем найти листинги с НУЖНЫМ float диапазоном,
                # так как их buy orders - наши прямые конкуренты.
                # Если не найдем - возьмем ЛЮБЫЕ листинги этого скина (fallback ниже).
                logger.debug(
                    f"Searching for listings with float range "
                    f"[{order.float_min}-{order.float_max}]"
                )
                listings_response = await client.get_all_listings(
                    def_index=order.def_index,
                    paint_index=order.paint_index,
                    category=1,  # Только normal (не StatTrak)
                    min_float=order.float_min if order.float_min is not None else None,
                    max_float=order.float_max if order.float_max is not None else None,
                    limit=20  # Reduced from 50 to avoid rate limiting
                )

            # Проверяем есть ли листинги
            if not listings_response or "listings" not in listings_response:
                logger.warning(
                    f"No listings response for {order.market_hash_name} "
                    f"(response={listings_response is not None})"
                )
                return None

            listings = listings_response["listings"]
            if not listings:
                logger.warning(
                    f"No active listings for {order.market_hash_name} with float range "
                    f"[{order.float_min}-{order.float_max}]. "
                    f"Will try without float filter to find buy orders from other listings."
                )
                # Fallback 1: КРИТИЧЕСКИ ВАЖНО - пробуем БЕЗ фильтра по float
                # Buy orders существуют даже если нет листингов с нашим float!
                # Получим листинги с другим float (например 0.15-0.20 или 0.25-0.30),
                # и их buy orders могут пересекаться с нашим диапазоном.
                if order.order_type == "advanced":
                    logger.info("Trying to find ANY listings of this skin (without float filter)...")
                    await rate_limit_delay(3.0, 5.0)  # Longer delay before fallback
                    listings_response = await client.get_all_listings(
                        def_index=order.def_index,
                        paint_index=order.paint_index,
                        category=1,
                        limit=5  # Reduced to avoid rate limiting
                    )
                    if listings_response and "listings" in listings_response:
                        listings = listings_response["listings"]
                        if listings:
                            logger.info(
                                f"Found {len(listings)} listings without float filter. "
                                f"Buy orders from these listings may still compete with us!"
                            )

                # Fallback 2: по market_hash_name
                if not listings:
                    logger.info("Trying to find listings by market_hash_name...")
                    await rate_limit_delay(3.0, 5.0)  # Longer delay before fallback
                    listings_response = await client.get_all_listings(
                        market_hash_name=order.market_hash_name,
                        limit=5  # Reduced to avoid rate limiting
                    )
                    if listings_response and "listings" in listings_response:
                        listings = listings_response["listings"]
                        if listings:
                            logger.info(f"Found {len(listings)} listings by market_hash_name")

                if not listings:
                    logger.warning(
                        f"Still no listings found for {order.market_hash_name}. "
                        f"Cannot check for competing buy orders."
                    )
                    return None

            # Логируем float values найденных листингов для отладки
            float_values = [getattr(l, 'float_value', 'N/A') for l in listings[:5]]
            logger.info(
                f"Found {len(listings)} listings for {order.market_hash_name}, "
                f"will check buy orders for each. "
                f"Sample float values: {float_values}"
            )

            # Шаг 2: Для advanced orders проверяем buy orders для КАЖДОГО листинга
            # так как buy orders с разными float ranges конкурируют за разные листинги
            all_buy_orders = []
            limit = 100 if order.order_type == "advanced" else 50

            for idx, listing in enumerate(listings, 1):
                listing_id = listing.id
                logger.debug(
                    f"[{idx}/{len(listings)}] Checking listing {listing_id} "
                    f"(float={getattr(listing, 'float_value', 'N/A')})"
                )

                try:
                    # Rate limit delay between buy order requests (increased)
                    await rate_limit_delay(3.0, 6.0)

                    buy_orders = await client.get_buy_orders(
                        listing_id=listing_id,
                        limit=limit,
                        raw_response=True
                    )

                    if buy_orders and len(buy_orders) > 0:
                        logger.debug(f"  Got {len(buy_orders)} buy orders for listing {listing_id}")
                        all_buy_orders.extend(buy_orders)
                    else:
                        logger.debug(f"  No buy orders for listing {listing_id}")

                except Exception as e:
                    error_str = str(e)
                    # Check for rate limiting (429 error)
                    if "429" in error_str or "rate" in error_str.lower():
                        logger.warning(f"  Rate limited on listing {listing_id}. Rotating headers and waiting...")
                        client.rotate_headers()  # Rotate User-Agent
                        await asyncio.sleep(random.uniform(5, 10))  # Longer delay on rate limit
                        # Try to rotate proxy if available
                        if hasattr(client, 'rotate_proxy') and client.proxy_list:
                            client.rotate_proxy()
                    else:
                        logger.warning(f"  Error getting buy orders for listing {listing_id}: {e}")
                    continue

            if not all_buy_orders:
                logger.warning(
                    f"No buy orders found for {order.market_hash_name} "
                    f"across {len(listings)} listings"
                )
                return None

            # Дедупликация: один buy order может конкурировать за несколько листингов
            # Убираем дубликаты по price + expression/market_hash_name
            seen = set()
            unique_buy_orders = []
            for bo in all_buy_orders:
                key = (bo.get('price'), bo.get('expression') or bo.get('market_hash_name'))
                if key not in seen:
                    seen.add(key)
                    unique_buy_orders.append(bo)

            logger.info(
                f"Got {len(all_buy_orders)} total buy orders from {len(listings)} listings, "
                f"{len(unique_buy_orders)} unique for {order.market_hash_name}"
            )

            # Используем дедуплицированные buy orders
            buy_orders = unique_buy_orders

            # Шаг 3: Фильтрация для advanced orders
            if order.order_type == "advanced":
                # Фильтруем только те buy orders, у которых float диапазон пересекается с нашим
                import re
                filtered_orders = []

                logger.info(
                    f"Filtering {len(buy_orders)} buy orders for float range overlap "
                    f"(our range: [{order.float_min}-{order.float_max}])"
                )

                for idx, bo in enumerate(buy_orders, 1):
                    # Парсим expression из buy order
                    expression = bo.get('expression', '')
                    if not expression:
                        # Это simple order, пропускаем
                        logger.debug(f"  [{idx}/{len(buy_orders)}] Skipping simple order: price=${bo.get('price', 0)/100:.2f}")
                        continue

                    # Извлекаем float диапазон из expression
                    bo_float_min = None
                    bo_float_max = None

                    min_match = re.search(r'FloatValue\s*>=?\s*([\d.]+)', expression)
                    if min_match:
                        bo_float_min = float(min_match.group(1))

                    max_match = re.search(r'FloatValue\s*<=?\s*([\d.]+)', expression)
                    if max_match:
                        bo_float_max = float(max_match.group(1))

                    # Проверяем пересечение float диапазонов
                    # Диапазоны пересекаются, если:
                    # bo_float_min <= our_float_max AND bo_float_max >= our_float_min
                    ranges_overlap = True
                    if order.float_min is not None and bo_float_max is not None:
                        if bo_float_max < order.float_min:
                            ranges_overlap = False
                    if order.float_max is not None and bo_float_min is not None:
                        if bo_float_min > order.float_max:
                            ranges_overlap = False

                    logger.debug(
                        f"  [{idx}/{len(buy_orders)}] Competitor: price=${bo.get('price', 0)/100:.2f}, "
                        f"float=[{bo_float_min}-{bo_float_max}], "
                        f"overlap={ranges_overlap}"
                    )

                    if ranges_overlap:
                        filtered_orders.append(bo)

                if not filtered_orders:
                    logger.info(
                        f"No competing advanced orders with overlapping float range "
                        f"for {order.market_hash_name} (checked {len(buy_orders)} orders)"
                    )
                    return None

                # Сортируем по цене (от большей к меньшей) и берем топовый
                logger.info(f"Found {len(filtered_orders)} competing advanced orders with overlapping float range")
                filtered_orders.sort(key=lambda x: x.get('price', 0), reverse=True)
                top_order = filtered_orders[0]
            else:
                # Для simple orders берем первый (он уже топовый)
                top_order = buy_orders[0]

            top_price = top_order.get("price", 0)

            logger.info(
                f"Top buy order for {order.market_hash_name} "
                f"({order.order_type}): ${top_price/100:.2f} (qty: {top_order.get('qty', '?')})"
            )

            return top_price

        except Exception as e:
            logger.error(f"Error getting top buy price for {order.market_hash_name}: {e}", exc_info=True)
            return None

    async def _delete_order(self, account: Account, client, order: BuyOrder):
        """Удалить ордер"""
        try:
            if order.order_type == "simple":
                # Используем csfloat-api для simple orders
                # delete_buy_order принимает id как int
                await client.delete_buy_order(id=int(order.order_id))
            else:
                # Используем advanced API для advanced orders
                advanced_api = self._get_advanced_api(account)
                await advanced_api.delete_advanced_order(order.order_id)

            logger.debug(f"Deleted order {order.order_id}")

        except Exception as e:
            logger.error(f"Error deleting order {order.order_id}: {e}")
            raise

    async def _create_order(
        self,
        account: Account,
        client,
        market_hash_name: str,
        price_cents: int,
        quantity: int,
        order_type: str,
        float_min: Optional[float] = None,
        float_max: Optional[float] = None,
        def_index: Optional[int] = None,
        paint_index: Optional[int] = None
    ) -> Optional[str]:
        """
        Создать новый ордер

        Returns:
            Order ID или None в случае ошибки
        """
        try:
            if order_type == "simple":
                # Используем csfloat-api для simple orders
                response = await client.create_buy_order(
                    market_hash_name=market_hash_name,
                    max_price=price_cents,
                    quantity=quantity
                )
                # TODO: Уточнить структуру ответа!
                order_id = response.get("id", response.get("order_id"))

            else:
                # Используем advanced API для advanced orders
                advanced_api = self._get_advanced_api(account)
                response = await advanced_api.create_advanced_order(
                    def_index=def_index,
                    paint_index=paint_index,
                    max_price_cents=price_cents,
                    quantity=quantity,
                    float_min=float_min or 0.0,
                    float_max=float_max or 1.0
                )
                order_id = response.get("id", response.get("order_id"))

            logger.debug(f"Created new order: {order_id}")
            return order_id

        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    def _get_advanced_api(self, account: Account) -> AdvancedOrderAPI:
        """Получить Advanced API клиента для аккаунта"""
        if account.id not in self._advanced_apis:
            self._advanced_apis[account.id] = AdvancedOrderAPI(
                api_key=account.api_key,
                proxy=account.proxy
            )
        return self._advanced_apis[account.id]

    async def get_status(self) -> Dict[str, Any]:
        """Получить статус бота"""
        return {
            "is_running": self.is_running,
            "check_interval": settings.check_interval,
            "outbid_step": settings.outbid_step,
            "max_outbids": settings.max_outbids,
            "active_tasks": len(self.tasks)
        }


# Singleton instance
bot_manager = BotManager()
