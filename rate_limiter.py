import asyncio
import time
import logging
from typing import Dict, List
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int = 1200  # Binance limit
    requests_per_second: int = 20    # Conservative limit
    burst_limit: int = 50            # Max burst requests
    backoff_factor: float = 2.0      # Exponential backoff multiplier
    max_retries: int = 3             # Max retry attempts

class BinanceRateLimiter:
    """
    Advanced rate limiter for Binance API with exponential backoff
    Handles both per-second and per-minute limits
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.requests_per_minute = deque()
        self.requests_per_second = deque()
        self.lock = asyncio.Lock()
        self.retry_delays: Dict[str, float] = {}
        
    async def acquire(self, endpoint: str = "default") -> None:
        """
        Acquire permission to make a request
        Blocks until it's safe to proceed
        """
        async with self.lock:
            await self._wait_for_rate_limit()
            self._record_request()
            
    async def _wait_for_rate_limit(self) -> None:
        """Wait if we're approaching rate limits"""
        now = time.time()
        
        # Clean old requests (older than 1 minute)
        while self.requests_per_minute and now - self.requests_per_minute[0] > 60:
            self.requests_per_minute.popleft()
            
        # Clean old requests (older than 1 second)
        while self.requests_per_second and now - self.requests_per_second[0] > 1:
            self.requests_per_second.popleft()
            
        # Check per-minute limit
        if len(self.requests_per_minute) >= self.config.requests_per_minute:
            sleep_time = 60 - (now - self.requests_per_minute[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
                
        # Check per-second limit
        if len(self.requests_per_second) >= self.config.requests_per_second:
            sleep_time = 1 - (now - self.requests_per_second[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                
    def _record_request(self) -> None:
        """Record a request timestamp"""
        now = time.time()
        self.requests_per_minute.append(now)
        self.requests_per_second.append(now)
        
    async def handle_rate_limit_error(self, endpoint: str) -> None:
        """
        Handle rate limit error with exponential backoff
        """
        if endpoint not in self.retry_delays:
            self.retry_delays[endpoint] = 1.0
        else:
            self.retry_delays[endpoint] *= self.config.backoff_factor
            
        delay = min(self.retry_delays[endpoint], 60.0)  # Max 60 seconds
        logger.warning(f"Rate limit error for {endpoint}, backing off for {delay:.2f} seconds")
        await asyncio.sleep(delay)
        
    def reset_retry_delay(self, endpoint: str) -> None:
        """Reset retry delay after successful request"""
        if endpoint in self.retry_delays:
            del self.retry_delays[endpoint]
            
    def get_stats(self) -> Dict[str, int]:
        """Get current rate limiter statistics"""
        now = time.time()
        
        # Count recent requests
        recent_minute = sum(1 for req_time in self.requests_per_minute if now - req_time <= 60)
        recent_second = sum(1 for req_time in self.requests_per_second if now - req_time <= 1)
        
        return {
            "requests_last_minute": recent_minute,
            "requests_last_second": recent_second,
            "minute_limit": self.config.requests_per_minute,
            "second_limit": self.config.requests_per_second,
            "minute_remaining": max(0, self.config.requests_per_minute - recent_minute),
            "second_remaining": max(0, self.config.requests_per_second - recent_second)
        }

class AsyncSemaphoreRateLimiter:
    """
    Simple semaphore-based rate limiter for concurrent request control
    """
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        
    async def __aenter__(self):
        await self.semaphore.acquire()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()
        
    def available_permits(self) -> int:
        """Get number of available permits"""
        return self.semaphore._value
        
    def get_stats(self) -> Dict[str, int]:
        """Get semaphore statistics"""
        return {
            "max_concurrent": self.max_concurrent,
            "available": self.available_permits(),
            "in_use": self.max_concurrent - self.available_permits()
        }

# Global rate limiter instances
binance_rate_limiter = BinanceRateLimiter()
concurrent_limiter = AsyncSemaphoreRateLimiter(max_concurrent=10)

async def rate_limited_request(func, *args, endpoint: str = "default", **kwargs):
    """
    Wrapper function for rate-limited API requests
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Acquire rate limit permission
            await binance_rate_limiter.acquire(endpoint)
            
            # Use concurrent limiter
            async with concurrent_limiter:
                result = await func(*args, **kwargs)
                
            # Reset retry delay on success
            binance_rate_limiter.reset_retry_delay(endpoint)
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a rate limit error
            if "rate limit" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    await binance_rate_limiter.handle_rate_limit_error(endpoint)
                    continue
                else:
                    logger.error(f"Max retries exceeded for {endpoint}")
                    raise
            else:
                # Non-rate-limit error, re-raise immediately
                raise
                
    raise Exception(f"Failed to complete request after {max_retries} attempts")

# User rate limiter for Telegram bot commands
class UserRateLimiter:
    """Simple rate limiter for individual users"""
    
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests_per_minute = max_requests_per_minute
        self.user_requests = {}
        
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make a request"""
        import time
        now = time.time()
        
        if user_id not in self.user_requests:
            self.user_requests[user_id] = deque()
            
        # Clean old requests (older than 1 minute)
        while self.user_requests[user_id] and now - self.user_requests[user_id][0] > 60:
            self.user_requests[user_id].popleft()
            
        # Check if user is within limit
        if len(self.user_requests[user_id]) >= self.max_requests_per_minute:
            return False
            
        # Record this request
        self.user_requests[user_id].append(now)
        return True

# Global user rate limiter instance
user_rate_limiter = UserRateLimiter(max_requests_per_minute=60)

def get_rate_limiter_stats() -> Dict[str, Dict]:
    """Get comprehensive rate limiter statistics"""
    return {
        "binance_rate_limiter": binance_rate_limiter.get_stats(),
        "concurrent_limiter": concurrent_limiter.get_stats(),
        "user_rate_limiter": user_rate_limiter.get_stats()
    }

# Example usage and testing
if __name__ == "__main__":
    async def test_rate_limiter():
        """Test the rate limiter functionality"""
        import aiohttp
        
        async def mock_api_call():
            await asyncio.sleep(0.1)  # Simulate API call
            return {"status": "success"}
            
        print("Testing rate limiter...")
        
        # Test multiple concurrent requests
        tasks = []
        for i in range(25):
            task = rate_limited_request(mock_api_call, endpoint="test")
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        print(f"Completed {len(results)} requests")
        
        # Print stats
        stats = get_rate_limiter_stats()
        print("Rate limiter stats:", stats)
        
    # Run test
    # asyncio.run(test_rate_limiter())