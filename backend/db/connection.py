import atexit
import os
import threading
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from utils.logger import setup_logger

logger = setup_logger(__name__)

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise EnvironmentError(
                "DATABASE_URL environment variable is not set. "
                "Expected format: postgresql://user:password@host:port/dbname"
            )
        try:
            _pool = pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)
            logger.info("[DB] Connection pool initialised (min=2, max=10)")
        except Exception as e:
            logger.error(f"[DB] Failed to initialise connection pool: {e}")
            raise

        def _close_pool():
            if _pool is not None:
                _pool.closeall()
                logger.info("[DB] Connection pool closed on exit")

        atexit.register(_close_pool)

    return _pool


def get_connection():
    return _get_pool().getconn()


def release_connection(conn):
    _get_pool().putconn(conn)


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)
