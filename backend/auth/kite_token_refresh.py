"""
Kite token storage and validity management.

Kite access tokens expire at 06:00 IST daily.
This module stores tokens in the kite_tokens table and provides
a clean interface for the broker to read the active token.

Known limitation: Full OAuth auto-refresh requires a hosted redirect
URL. Manual refresh via POST /broker/kite/token is the supported flow.
"""
import os
import logging
import pytz
from datetime import datetime, timezone, timedelta
from typing import Optional

from db.connection import db_cursor

_logger = logging.getLogger("kite_token_refresh")

_IST = pytz.timezone("Asia/Kolkata")


def _next_kite_expiry() -> datetime:
    """
    Return the next 06:00 IST expiry as a UTC datetime.
    If 06:00 IST today is already past, returns 06:00 IST tomorrow.
    Uses pytz for correct timezone-aware arithmetic.
    """
    now_ist = datetime.now(_IST)

    # Build today's 06:00 IST (tz-aware)
    expiry_ist = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)
    if expiry_ist <= now_ist:
        # Already past today's 06:00 IST → use tomorrow
        expiry_ist += timedelta(days=1)

    # Convert to UTC (pytz handles DST automatically, though India has none)
    return expiry_ist.astimezone(timezone.utc)


def store_token(access_token: str, request_token: str = "") -> bool:
    """
    Store a new Kite access token in the DB.

    Deactivates all existing tokens then inserts a new active row.
    Updates os.environ["KITE_ACCESS_TOKEN"] so KiteBroker picks it up
    immediately without restart.

    Args:
        access_token:  The Kite access token string.
        request_token: Optional request token (for audit purposes).

    Returns:
        True on success, False on error.
    """
    try:
        valid_until = _next_kite_expiry()
        now_utc     = datetime.now(timezone.utc)

        with db_cursor() as cur:
            # Deactivate all previous tokens
            cur.execute("UPDATE kite_tokens SET is_active = FALSE")
            # Insert new active token
            cur.execute(
                """
                INSERT INTO kite_tokens
                    (access_token, request_token, valid_from, valid_until, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (access_token, request_token or None, now_utc, valid_until),
            )

        # Update live environment so KiteBroker reads it immediately
        os.environ["KITE_ACCESS_TOKEN"] = access_token

        _logger.info(
            f"[KITE_TOKEN] Stored new token, valid until {valid_until.isoformat()}"
        )
        return True

    except Exception as e:
        _logger.error(f"[KITE_TOKEN] store_token error: {e}")
        return False


def get_active_token() -> Optional[str]:
    """
    Return the active Kite access token if it has not expired.

    Returns:
        Access token string, or None if no valid token exists.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT access_token
                FROM kite_tokens
                WHERE is_active = TRUE
                  AND valid_until > NOW()
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        _logger.warning(f"[KITE_TOKEN] get_active_token error: {e}")
        return None


def is_token_valid() -> bool:
    """Return True if there is a currently valid active token."""
    return get_active_token() is not None


def get_token_expiry() -> Optional[datetime]:
    """
    Return the valid_until datetime for the active token, or None.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT valid_until
                FROM kite_tokens
                WHERE is_active = TRUE
                  AND valid_until > NOW()
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        _logger.warning(f"[KITE_TOKEN] get_token_expiry error: {e}")
        return None
