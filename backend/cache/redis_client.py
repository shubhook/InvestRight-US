import os
from typing import Optional
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger(__name__)

_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is None:
        import redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            _redis_client = redis.from_url(url, decode_responses=True)
            _redis_client.ping()
            logger.info(f"[REDIS] Connected to {url}")
        except Exception as e:
            logger.warning(f"[REDIS] Could not connect to Redis ({url}): {e}")
            return None
    return _redis_client


def set_ohlcv(symbol: str, data: pd.DataFrame, ttl_seconds: int = 900):
    client = _get_client()
    if client is None:
        return
    try:
        key = f"ohlcv:{symbol}"
        serialised = data.to_json(orient="records")
        client.setex(key, ttl_seconds, serialised)
        logger.info(f"[REDIS] Cached OHLCV for {symbol} (ttl={ttl_seconds}s)")
    except Exception as e:
        logger.warning(f"[REDIS] Failed to cache OHLCV for {symbol}: {e}")


def get_ltp(symbol: str) -> Optional[float]:
    client = _get_client()
    if client is None:
        return None
    try:
        val = client.get(f"ltp:{symbol}")
        return float(val) if val is not None else None
    except Exception:
        return None


def set_ltp(symbol: str, price: float, ttl_seconds: int = 60):
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(f"ltp:{symbol}", ttl_seconds, str(price))
    except Exception:
        pass


def get_ohlcv(symbol: str) -> Optional[pd.DataFrame]:
    client = _get_client()
    if client is None:
        return None
    try:
        key = f"ohlcv:{symbol}"
        raw = client.get(key)
        if raw is None:
            return None
        df = pd.read_json(raw, orient="records")
        if df.empty:
            return None
        logger.info(f"[REDIS] Cache hit for {symbol}")
        return df
    except Exception as e:
        logger.warning(f"[REDIS] Failed to retrieve OHLCV for {symbol}: {e}")
        return None
