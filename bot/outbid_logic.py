"""
Outbid logic - логика перебивания ордеров
"""
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database import BuyOrder, OutbidHistory, Account
from config import settings


class OutbidLogic:
    """Логика автоматического перебивания buy orders"""

    def __init__(self, session: AsyncSession):
        self.session = session

    def calculate_price_ceiling(self, lowest_listing_cents: int) -> int:
        """
        Рассчитать потолок цены на основе lowest listing

        Args:
            lowest_listing_cents: Цена самого дешёвого листинга в центах

        Returns:
            Максимально допустимая цена для перебивания в центах
        """
        # Вариант 1: multiplier (например 1.20 = +20% от lowest)
        from_multiplier = int(lowest_listing_cents * settings.max_outbid_multiplier)

        # Вариант 2: фиксированная надбавка (например +$5.00)
        from_premium = lowest_listing_cents + settings.max_outbid_premium_cents

        # Берём минимум из двух
        ceiling = min(from_multiplier, from_premium)

        logger.debug(
            f"Price ceiling calculated: ${ceiling/100:.2f} "
            f"(lowest: ${lowest_listing_cents/100:.2f}, "
            f"multiplier: {settings.max_outbid_multiplier}x=${from_multiplier/100:.2f}, "
            f"premium: +${settings.max_outbid_premium_cents/100:.2f}=${from_premium/100:.2f})"
        )

        return ceiling

    def should_outbid(
        self,
        our_order: BuyOrder,
        competitor_price_cents: int,
        price_ceiling_cents: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Определить, нужно ли перебивать ордер

        Args:
            our_order: Наш ордер
            competitor_price_cents: Цена конкурента в центах
            price_ceiling_cents: Потолок цены (рассчитанный от lowest listing)

        Returns:
            (should_outbid, reason)
        """
        # Проверка 1: Конкурент перебил нас?
        if competitor_price_cents <= our_order.price_cents:
            return False, "Our order is already highest or equal"

        # Проверка 2: Не превысили ли лимит перебивов?
        if our_order.outbid_count >= settings.max_outbids:
            return False, f"Max outbids reached ({settings.max_outbids})"

        # Проверка 3: Не превысим ли максимальную цену?
        new_price_cents = competitor_price_cents + int(settings.outbid_step * 100)

        if our_order.max_price_cents and new_price_cents > our_order.max_price_cents:
            return False, f"New price (${new_price_cents/100:.2f}) exceeds max price (${our_order.max_price_cents/100:.2f})"

        # Проверка 4: Не превысим ли потолок (от lowest listing)?
        if price_ceiling_cents and new_price_cents > price_ceiling_cents:
            return False, f"Price ceiling reached: ${new_price_cents/100:.2f} > ${price_ceiling_cents/100:.2f}"

        return True, None

    def calculate_new_price(
        self,
        competitor_price_cents: int,
        outbid_step_cents: Optional[int] = None
    ) -> int:
        """
        Рассчитать новую цену для перебивания

        Args:
            competitor_price_cents: Цена конкурента в центах
            outbid_step_cents: Шаг перебивания в центах (если None, используется из настроек)

        Returns:
            Новая цена в центах
        """
        if outbid_step_cents is None:
            outbid_step_cents = int(settings.outbid_step * 100)

        new_price = competitor_price_cents + outbid_step_cents

        logger.debug(
            f"Calculated new price: ${new_price/100:.2f} "
            f"(competitor: ${competitor_price_cents/100:.2f}, step: ${outbid_step_cents/100:.2f})"
        )

        return new_price

    async def record_outbid(
        self,
        account: Account,
        order: BuyOrder,
        old_price_cents: int,
        new_price_cents: int,
        competitor_price_cents: int
    ):
        """
        Записать перебив в историю

        Args:
            account: Аккаунт
            order: Ордер
            old_price_cents: Старая цена
            new_price_cents: Новая цена
            competitor_price_cents: Цена конкурента
        """
        history = OutbidHistory(
            account_id=account.id,
            order_id=order.order_id,
            market_hash_name=order.market_hash_name,
            old_price_cents=old_price_cents,
            new_price_cents=new_price_cents,
            competitor_price_cents=competitor_price_cents,
            timestamp=datetime.utcnow()
        )

        self.session.add(history)

        # Обновляем счетчик перебивов и цену в ордере
        order.outbid_count += 1
        order.price_cents = new_price_cents
        order.updated_at = datetime.utcnow()

        await self.session.commit()

        logger.info(
            f"Outbid recorded for {order.market_hash_name}: "
            f"${old_price_cents/100:.2f} -> ${new_price_cents/100:.2f} "
            f"(competitor: ${competitor_price_cents/100:.2f}, count: {order.outbid_count})"
        )

    def format_price(self, price_cents: int) -> str:
        """Форматировать цену для отображения"""
        return f"${price_cents / 100:.2f}"

    def cents_to_dollars(self, cents: int) -> float:
        """Конвертировать центы в доллары"""
        return cents / 100

    def dollars_to_cents(self, dollars: float) -> int:
        """Конвертировать доллары в центы"""
        return int(dollars * 100)
