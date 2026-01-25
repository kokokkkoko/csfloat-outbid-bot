"""
Advanced Buy Orders API
Работа с advanced buy orders через прямые HTTP запросы,
так как csfloat-api не поддерживает их нативно
"""
import httpx
from typing import Optional, List, Dict, Any
from loguru import logger


class AdvancedOrderAPI:
    """
    API для работы с advanced buy orders на CSFloat

    ВАЖНО: Эндпоинты для advanced orders нужно уточнить!
    Откройте CSFloat в браузере, зайдите в DevTools -> Network,
    создайте advanced buy order и посмотрите какой запрос отправляется.

    Предположительные эндпоинты (могут отличаться):
    - POST /api/v1/buy_orders/advanced - создание
    - GET /api/v1/buy_orders/advanced - получение списка
    - DELETE /api/v1/buy_orders/advanced/{order_id} - удаление
    """

    BASE_URL = "https://csfloat.com/api/v1"

    def __init__(self, api_key: str, proxy: Optional[str] = None):
        self.api_key = api_key
        self.proxy = proxy
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "User-Agent": "CSFloat-Bot/1.0"
        }

        # Создаем HTTP клиента
        self.client = httpx.AsyncClient(
            headers=self.headers,
            proxy=proxy,
            timeout=30.0
        )

    async def create_advanced_order(
        self,
        def_index: int,
        paint_index: int,
        max_price_cents: int,
        quantity: int = 1,
        float_min: float = 0.0,
        float_max: float = 1.0
    ) -> Dict[str, Any]:
        """
        Создать advanced buy order с указанием float диапазона

        Args:
            def_index: ID оружия (DefIndex)
            paint_index: ID скина (PaintIndex)
            max_price_cents: Максимальная цена в центах
            quantity: Количество
            float_min: Минимальный float (0.0 - 1.0)
            float_max: Максимальный float (0.0 - 1.0)

        Returns:
            Response с данными созданного ордера
        """
        # CSFloat API ожидает expression в виде объекта с правилами
        expression = {
            "condition": "and",
            "rules": [
                {
                    "field": "DefIndex",
                    "operator": "==",
                    "value": {"constant": str(def_index)}
                },
                {
                    "field": "PaintIndex",
                    "operator": "==",
                    "value": {"constant": str(paint_index)}
                },
                {
                    "field": "FloatValue",
                    "operator": ">=",
                    "value": {"constant": str(float_min)}
                },
                {
                    "field": "FloatValue",
                    "operator": "<",
                    "value": {"constant": str(float_max)}
                },
                {
                    "field": "StatTrak",
                    "operator": "==",
                    "value": {"constant": "false"}
                }
            ]
        }

        payload = {
            "expression": expression,
            "max_price": max_price_cents,
            "quantity": quantity
        }

        logger.info(
            f"Creating advanced order: DefIndex={def_index}, PaintIndex={paint_index}, "
            f"price={max_price_cents}¢, float={float_min}-{float_max}"
        )

        try:
            # CSFloat использует /buy-orders для всех типов ордеров
            response = await self.client.post(
                f"{self.BASE_URL}/buy-orders",
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            logger.success(f"Advanced order created: {data.get('id', 'unknown')}")
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating advanced order: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error creating advanced order: {e}")
            raise

    async def get_my_advanced_orders(self) -> List[Dict[str, Any]]:
        """
        Получить список своих advanced buy orders

        TODO: Уточнить эндпоинт через DevTools!
        Возможно это общий эндпоинт /buy_orders с фильтром по типу
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/buy_orders/advanced"  # или /buy_orders?type=advanced
            )
            response.raise_for_status()

            data = response.json()
            orders = data if isinstance(data, list) else data.get("orders", [])

            logger.debug(f"Retrieved {len(orders)} advanced orders")
            return orders

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting advanced orders: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error getting advanced orders: {e}")
            raise

    async def delete_advanced_order(self, order_id: str) -> bool:
        """
        Удалить advanced buy order

        TODO: Уточнить формат order_id и эндпоинт!
        """
        try:
            # CSFloat использует /buy-orders для всех типов ордеров
            response = await self.client.delete(
                f"{self.BASE_URL}/buy-orders/{order_id}"
            )
            response.raise_for_status()

            logger.success(f"Advanced order {order_id} deleted")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting advanced order: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Error deleting advanced order: {e}")
            return False

    async def get_top_buy_order(self, market_hash_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить топовый buy order для предмета (для проверки конкурентов)

        TODO: Уточнить эндпоинт! Возможно это часть /listings или отдельный эндпоинт
        """
        try:
            # Возможные варианты эндпоинтов:
            # - /listings?market_hash_name={name}&type=buy_order
            # - /buy_orders/top?market_hash_name={name}
            # - /market/{name}/buy_orders

            response = await self.client.get(
                f"{self.BASE_URL}/listings",
                params={
                    "market_hash_name": market_hash_name,
                    "type": "buy_order",
                    "sort_by": "price",
                    "limit": 1
                }
            )
            response.raise_for_status()

            data = response.json()
            orders = data if isinstance(data, list) else data.get("orders", [])

            if orders:
                return orders[0]
            return None

        except Exception as e:
            logger.error(f"Error getting top buy order: {e}")
            return None

    async def close(self):
        """Закрыть HTTP клиента"""
        await self.client.aclose()
