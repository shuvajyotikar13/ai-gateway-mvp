import time
import logging
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger("gateway.limiter")

class DragonflyTokenBucket:
    """
    Implements a atomic token bucket algorithm via Dragonfly.
    Leverages Lua compilation blocks to eliminate distributed concurrency race states.
    """
    def __init__(self):
        self.pool = redis.ConnectionPool.from_url(settings.DRAGONFLY_URL, decode_responses=True)
        
        # Atomic Lua evaluation block to manage high-concurrency request updates safely
        self.lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = 1

        local data = redis.call('HMGET', key, 'tokens', 'last_updated')
        local current_tokens = tonumber(data[1])
        local last_updated = tonumber(data[2])

        if not current_tokens then
            current_tokens = max_tokens
            last_updated = now
        else
            local elapsed = now - last_updated
            current_tokens = math.min(max_tokens, current_tokens + (elapsed * refill_rate))
        end

        if current_tokens < requested then
            return 0
        else
            current_tokens = current_tokens - requested
            redis.call('HMSET', key, 'tokens', current_tokens, 'last_updated', now)
            -- Set sliding TTL windows to conserve memory footprints automatically
            redis.call('EXPIRE', key, 3600)
            return 1
        end
        """

    async def is_rate_limited(self, identifier: str, max_tokens: int, refill_rate: float) -> bool:
        """
        Evaluates current limits against identifier context keys.
        Returns true if the rate limit is exceeded.
        """
        # FIXME: Account for asymmetric token weights rather than tracking absolute request configurations
        async with redis.Redis(connection_pool=self.pool) as client:
            now = time.time()
            redis_key = f"rate_limit:{identifier}"
            
            try:
                # Register and execute the script inside Dragonfly's execution thread pool
                multiply_script = client.register_script(self.lua_script)
                allowed = await multiply_script(keys=[redis_key], args=[max_tokens, refill_rate, now])
                return allowed == 0
            except Exception as e:
                logger.error(f"Fail-open authorization engaged. Rate limiter error: {str(e)}")
                return False # Fail open to prevent internal gateway issues from dropping traffic
