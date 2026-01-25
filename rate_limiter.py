"""
Rate Limiter for CSFloat API
Uses token bucket algorithm with per-account and global limits
"""
import asyncio
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, field
from loguru import logger

from config import settings


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    max_tokens: int
    refill_rate: float  # tokens per second
    tokens: float = field(default=0)
    last_refill: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        # Start with full bucket
        self.tokens = float(self.max_tokens)

    def refill(self):
        """Refill tokens based on elapsed time"""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, wait if necessary.
        Returns the wait time in seconds.
        """
        wait_time = 0.0

        while True:
            self.refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return wait_time

            # Calculate wait time
            needed = tokens - self.tokens
            wait = needed / self.refill_rate

            # Add small jitter to avoid thundering herd
            import random
            jitter = random.uniform(0.1, 0.5)
            actual_wait = wait + jitter

            logger.debug(f"Rate limiter: waiting {actual_wait:.2f}s for tokens")
            await asyncio.sleep(actual_wait)
            wait_time += actual_wait


class RateLimiter:
    """
    Global rate limiter for CSFloat API.
    Implements both global and per-account rate limiting.
    """

    def __init__(self):
        # Global rate limit
        # CSFloat typically allows ~60-120 requests per minute
        self.global_bucket = TokenBucket(
            max_tokens=settings.max_requests_per_minute,
            refill_rate=settings.max_requests_per_minute / 60.0  # tokens per second
        )

        # Per-account buckets (more conservative)
        self.account_buckets: Dict[int, TokenBucket] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"RateLimiter initialized: global={settings.max_requests_per_minute}/min, "
            f"per_account={settings.max_requests_per_account}/min"
        )

    def get_account_bucket(self, account_id: int) -> TokenBucket:
        """Get or create rate limit bucket for an account"""
        if account_id not in self.account_buckets:
            self.account_buckets[account_id] = TokenBucket(
                max_tokens=settings.max_requests_per_account,
                refill_rate=settings.max_requests_per_account / 60.0
            )
        return self.account_buckets[account_id]

    async def acquire(self, account_id: int, tokens: int = 1) -> float:
        """
        Acquire rate limit tokens for both global and account limits.
        Returns total wait time.
        """
        async with self._lock:
            total_wait = 0.0

            # Wait for global rate limit
            wait = await self.global_bucket.acquire(tokens)
            total_wait += wait

            # Wait for account rate limit
            account_bucket = self.get_account_bucket(account_id)
            wait = await account_bucket.acquire(tokens)
            total_wait += wait

            if total_wait > 0:
                logger.debug(
                    f"Rate limiter: waited {total_wait:.2f}s total for account {account_id}"
                )

            return total_wait

    async def wait_after_rate_limit_error(self, account_id: int, retry_after: int = 60):
        """
        Called when we get a 429 (rate limited) response.
        Drains the bucket and waits.
        """
        logger.warning(
            f"Rate limited by CSFloat API for account {account_id}. "
            f"Backing off for {retry_after}s"
        )

        # Drain the account bucket
        account_bucket = self.get_account_bucket(account_id)
        account_bucket.tokens = 0

        # Wait for the specified time
        await asyncio.sleep(retry_after)

    def get_status(self) -> dict:
        """Get current rate limiter status"""
        self.global_bucket.refill()

        return {
            "global_tokens": round(self.global_bucket.tokens, 2),
            "global_max": self.global_bucket.max_tokens,
            "accounts": {
                acc_id: {
                    "tokens": round(bucket.tokens, 2),
                    "max": bucket.max_tokens
                }
                for acc_id, bucket in self.account_buckets.items()
            }
        }


# Global singleton instance
rate_limiter = RateLimiter()


# Utility functions for anti-detection
async def random_delay(min_seconds: float = 0.5, max_seconds: float = 2.0):
    """Add random delay between requests to avoid detection patterns"""
    import random
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def backoff_on_error(attempt: int, max_backoff: int = 300) -> float:
    """
    Exponential backoff for retries.
    Returns the wait time.
    """
    import random

    # Exponential backoff: 2^attempt seconds (with some randomness)
    base_wait = min(2 ** attempt, max_backoff)
    jitter = random.uniform(0, base_wait * 0.1)
    wait_time = base_wait + jitter

    logger.debug(f"Backoff: waiting {wait_time:.2f}s (attempt {attempt})")
    await asyncio.sleep(wait_time)

    return wait_time
