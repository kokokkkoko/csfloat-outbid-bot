"""
Bot Manager - главный координатор работы бота
"""
import asyncio
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

                # Проверяем каждый аккаунт параллельно
                tasks = [
                    self._check_account(session, account)
                    for account in accounts
                ]

                await asyncio.gather(*tasks, return_exceptions=True)

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

            # Проверяем каждый ордер
            for order in orders:
                try:
                    logger.info(
                        f"Checking order {order.order_id} ({order.order_type}): "
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

            # Проверяем, нужно ли перебивать
            outbid_logic = OutbidLogic(session)
            should_outbid, reason = outbid_logic.should_outbid(order, competitor_price)

            if not should_outbid:
                logger.debug(
                    f"No outbid needed for {order.market_hash_name}: {reason}"
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

        except Exception as e:
            logger.error(f"Error in outbid process: {e}", exc_info=True)
            raise

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
                # Фильтруем по float range, чтобы найти листинг нужного качества
                listings_response = await client.get_all_listings(
                    def_index=order.def_index,
                    paint_index=order.paint_index,
                    category=1,  # Только normal (не StatTrak)
                    min_float=order.float_min if order.float_min is not None else None,
                    max_float=order.float_max if order.float_max is not None else None,
                    limit=1,
                    type_="buy_now"
                )

            # Проверяем есть ли листинги
            if not listings_response or "listings" not in listings_response:
                logger.debug(f"No listings found for {order.market_hash_name}")
                return None

            listings = listings_response["listings"]
            if not listings:
                logger.debug(f"No active listings for {order.market_hash_name}")
                return None

            # Берем первый листинг
            listing = listings[0]
            listing_id = listing.id

            logger.debug(f"Found listing {listing_id} for {order.market_hash_name}")

            # Шаг 2: Получить buy orders для этого листинга
            # Для advanced orders нужно больше, так как многие могут не пересекаться по float
            limit = 100 if order.order_type == "advanced" else 50
            buy_orders = await client.get_buy_orders(
                listing_id=listing_id,
                limit=limit,
                raw_response=True
            )

            logger.debug(f"Got {len(buy_orders) if buy_orders else 0} buy orders from API")

            if not buy_orders or len(buy_orders) == 0:
                logger.debug(f"No buy orders for {order.market_hash_name}")
                return None

            # Шаг 3: Фильтрация для advanced orders
            if order.order_type == "advanced":
                # Фильтруем только те buy orders, у которых float диапазон пересекается с нашим
                import re
                filtered_orders = []

                logger.debug(f"Filtering {len(buy_orders)} buy orders for float range overlap")

                for bo in buy_orders:
                    # Парсим expression из buy order
                    expression = bo.get('expression', '')
                    if not expression:
                        # Это simple order, пропускаем
                        logger.debug(f"  Skipping simple order: price={bo.get('price', 0)}")
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
                        f"  Competitor: price={bo.get('price', 0)}, "
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
