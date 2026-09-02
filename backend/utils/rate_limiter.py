"""
Sliding-window rate limiter.

Uses Redis INCR + EXPIRE for distributed rate limiting.
Falls back to an in-memory dict when Redis is unavailable.

Usage:
    from utils.rate_limiter import check_rate_limit

    allowed, headers = check_rate_limit(client_id="127.0.0.1", endpoint="/analyze")
    if not allowed:
        return jsonify({"error": "Too Many Requests"}), 429, headers
"""
import os
import time
import threading
from typing import Tuple, Dict

# ---------------------------------------------------------------------------
# Route-level limits  (requests per minute)
# ---------------------------------------------------------------------------
_LIMITS: Dict[str, int] = {
    "/analyze":               10,
    "/backtest/run":           3,
    "/backtest/walk-forward":  1,
}
_DEFAULT_LIMIT = 60

# ---------------------------------------------------------------------------
# Redis client (lazy init, None if unavailable)
# ---------------------------------------------------------------------------
_redis_client = None
_redis_lock   = threading.Lock()


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis as _redis
            r = _redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            r.ping()
            _redis_client = r
        except Exception:
            _redis_client = None
    return _redis_client


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------
_mem_store: Dict[str, Tuple[int, float]] = {}   # key → (count, window_start)
_mem_lock   = threading.Lock()
_WINDOW_SECS = 60


def _mem_check(key: str, limit: int) -> Tuple[bool, int, int]:
    """
    Returns (allowed, current_count, reset_at_unix).
    Thread-safe sliding-window backed by an in-memory dict.
    """
    now = time.time()
    with _mem_lock:
        count, window_start = _mem_store.get(key, (0, now))
        if now - window_start >= _WINDOW_SECS:
            # New window
            count        = 1
            window_start = now
        else:
            count += 1
        _mem_store[key] = (count, window_start)
        reset_at = int(window_start + _WINDOW_SECS)
    return count <= limit, count, reset_at


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_rate_limit(client_id: str, endpoint: str) -> Tuple[bool, dict]:
    """
    Check whether *client_id* may call *endpoint*.

    Returns:
        (allowed: bool, headers: dict)
        headers contains X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
        and (on rejection) Retry-After.
    """
    limit = _LIMITS.get(endpoint, _DEFAULT_LIMIT)
    key   = f"rl:{endpoint}:{client_id}"

    r = _get_redis()
    if r is not None:
        try:
            # Redis pipeline: INCR then EXPIRE (set TTL only on first request in window)
            pipe  = r.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()

            if ttl == -1:
                # Key exists but has no TTL yet (first hit) — set it.
                # ttl == -2 means the key does not exist, which should not
                # happen right after INCR, so only set expire for ttl == -1.
                r.expire(key, _WINDOW_SECS)
                ttl = _WINDOW_SECS

            reset_at   = int(time.time()) + ttl
            allowed    = count <= limit
            remaining  = max(0, limit - count)
            headers    = {
                "X-RateLimit-Limit":     str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset":     str(reset_at),
            }
            if not allowed:
                headers["Retry-After"] = str(ttl)
            return allowed, headers

        except Exception:
            # Redis failed mid-request → fall through to in-memory
            pass

    # In-memory fallback
    allowed, count, reset_at = _mem_check(key, limit)
    remaining = max(0, limit - count)
    headers   = {
        "X-RateLimit-Limit":     str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset":     str(reset_at),
    }
    if not allowed:
        headers["Retry-After"] = str(_WINDOW_SECS)
    return allowed, headers
