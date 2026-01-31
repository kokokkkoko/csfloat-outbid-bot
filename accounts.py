"""
Account management module
"""
from typing import Optional, List
from datetime import datetime
import random
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from csfloat_api.csfloat_client import Client as CSFloatClientBase
import aiohttp
from loguru import logger

from database import Account


# Realistic User-Agent strings (Chrome, Firefox, Safari on different OS)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Languages for Accept-Language header
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,ru;q=0.8",
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
]


def get_random_headers() -> dict:
    """Generate realistic browser headers"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': random.choice(ACCEPT_LANGUAGES),
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://csfloat.com',
        'Referer': 'https://csfloat.com/',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Connection': 'keep-alive',
    }


class CSFloatClient(CSFloatClientBase):
    """Обертка над CSFloatClient с anti-detection features"""

    # Class-level rate limiting
    _last_request_time: float = 0
    _min_request_interval: float = 1.0  # Minimum 1 second between requests
    _request_lock = None

    def __init__(self, api_key: str, proxy: str = None, proxy_list: List[str] = None) -> None:
        self.API_KEY = api_key
        self.proxy = proxy
        self.proxy_list = proxy_list or []  # List of proxies for rotation
        self._current_proxy_index = 0
        self._validate_proxy()

        # Random browser-like headers + Authorization
        self._base_headers = get_random_headers()
        self._base_headers['Authorization'] = self.API_KEY

        self._connector = None
        self._session = None
        self._create_session()

        logger.debug(f"CSFloatClient initialized (proxy: {self.proxy is not None}, proxy_list: {len(self.proxy_list)})")

    def _create_session(self, proxy_url: str = None):
        """Create or recreate aiohttp session with given proxy"""
        proxy_to_use = proxy_url or self.proxy

        # Close existing session if any
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())

        # Rotate headers on session creation
        self._headers = get_random_headers()
        self._headers['Authorization'] = self.API_KEY

        if proxy_to_use:
            from aiohttp_socks.connector import ProxyConnector
            self._connector = ProxyConnector.from_url(
                proxy_to_use,
                ttl_dns_cache=300,
                force_close=True
            )
        else:
            self._connector = aiohttp.TCPConnector(
                resolver=aiohttp.ThreadedResolver(),
                limit_per_host=50,
                force_close=True,
                enable_cleanup_closed=True
            )

        self._session = aiohttp.ClientSession(
            connector=self._connector,
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )

    def rotate_proxy(self) -> Optional[str]:
        """Rotate to next proxy in the list"""
        if not self.proxy_list:
            return None

        self._current_proxy_index = (self._current_proxy_index + 1) % len(self.proxy_list)
        new_proxy = self.proxy_list[self._current_proxy_index]

        logger.info(f"Rotating proxy to: {new_proxy[:30]}...")
        self._create_session(new_proxy)
        return new_proxy

    def rotate_headers(self):
        """Rotate User-Agent and other headers"""
        new_headers = get_random_headers()
        new_headers['Authorization'] = self.API_KEY
        self._headers = new_headers

        # Update session headers
        if self._session:
            self._session._default_headers = aiohttp.typedefs.CIMultiDict(new_headers)

        logger.debug(f"Rotated headers, new UA: {new_headers['User-Agent'][:50]}...")

    async def _rate_limited_request(self):
        """Add random delay between requests to avoid detection"""
        # Random delay between 0.5 and 2 seconds
        delay = random.uniform(0.5, 2.0)
        await asyncio.sleep(delay)


class AccountManager:
    """Менеджер аккаунтов"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._clients: dict[int, CSFloatClient] = {}

    async def get_all_accounts(self) -> List[Account]:
        """Получить все аккаунты"""
        result = await self.session.execute(select(Account))
        return list(result.scalars().all())

    async def get_active_accounts(self) -> List[Account]:
        """Получить только активные аккаунты"""
        result = await self.session.execute(
            select(Account).where(Account.is_active == True)
        )
        return list(result.scalars().all())

    async def get_accounts_by_user(self, user_id: int) -> List[Account]:
        """Получить аккаунты пользователя"""
        result = await self.session.execute(
            select(Account).where(Account.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_account(self, account_id: int) -> Optional[Account]:
        """Получить аккаунт по ID"""
        result = await self.session.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_account_by_name(self, name: str) -> Optional[Account]:
        """Получить аккаунт по имени"""
        result = await self.session.execute(
            select(Account).where(Account.name == name)
        )
        return result.scalar_one_or_none()

    async def create_account(
        self,
        name: str,
        api_key: str,
        proxy: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Account:
        """Создать новый аккаунт"""
        # Проверяем, что аккаунт с таким именем не существует
        existing = await self.get_account_by_name(name)
        if existing:
            raise ValueError(f"Account with name '{name}' already exists")

        account = Account(
            name=name,
            api_key=api_key,
            proxy=proxy,
            is_active=True,
            status="idle",
            user_id=user_id
        )

        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)

        logger.info(f"Created account: {name} (ID: {account.id}, user_id: {user_id})")
        return account

    async def update_account(
        self,
        account_id: int,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        proxy: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Account]:
        """Обновить аккаунт"""
        account = await self.get_account(account_id)
        if not account:
            return None

        if name is not None:
            account.name = name
        if api_key is not None:
            account.api_key = api_key
            # Сбрасываем клиента при смене API key
            if account_id in self._clients:
                del self._clients[account_id]
        if proxy is not None:
            account.proxy = proxy
            # Сбрасываем клиента при смене прокси
            if account_id in self._clients:
                del self._clients[account_id]
        if is_active is not None:
            account.is_active = is_active

        await self.session.commit()
        await self.session.refresh(account)

        logger.info(f"Updated account: {account.name} (ID: {account_id})")
        return account

    async def delete_account(self, account_id: int) -> bool:
        """Удалить аккаунт"""
        account = await self.get_account(account_id)
        if not account:
            return False

        await self.session.delete(account)
        await self.session.commit()

        # Удаляем клиента
        if account_id in self._clients:
            del self._clients[account_id]

        logger.info(f"Deleted account: {account.name} (ID: {account_id})")
        return True

    async def update_account_status(
        self,
        account_id: int,
        status: str,
        error_message: Optional[str] = None
    ):
        """Обновить статус аккаунта"""
        account = await self.get_account(account_id)
        if not account:
            return

        account.status = status
        account.error_message = error_message
        account.last_check = datetime.utcnow()

        await self.session.commit()

    def get_client(self, account: Account) -> CSFloatClient:
        """
        Получить CSFloat клиента для аккаунта
        Использует кэширование для избежания создания множества клиентов
        """
        if account.id not in self._clients:
            # Создаем нового клиента с API ключом
            # Прокси передается через параметр proxy (если есть)
            client = CSFloatClient(
                api_key=account.api_key,
                proxy=account.proxy if account.proxy else None
            )
            self._clients[account.id] = client
            logger.debug(f"Created CSFloat client for account {account.name}")

        return self._clients[account.id]

    async def test_account_connection(self, account: Account) -> tuple[bool, Optional[str]]:
        """
        Проверить подключение аккаунта
        Returns: (success, error_message)
        """
        try:
            client = self.get_client(account)

            # Пробуем получить список своих buy orders для проверки
            # Это простой и безопасный запрос
            await client.get_my_buy_orders()

            await self.update_account_status(account.id, "online", None)
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Account {account.name} connection test failed: {error_msg}")
            await self.update_account_status(account.id, "error", error_msg)
            return False, error_msg

    async def close_all_clients(self):
        """Закрыть все клиенты"""
        for client in self._clients.values():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing client: {e}")
        self._clients.clear()
        logger.info("All CSFloat clients closed")
