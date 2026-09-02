import os
from datetime import datetime, timezone
from typing import Optional
from db.connection import db_cursor
from utils.logger import setup_logger

logger = setup_logger(__name__)


def initialise() -> bool:
    """
    Seed capital_account from TOTAL_CAPITAL env var on first run.
    Idempotent — does nothing if a row already exists.
    """
    total = float(os.getenv("TOTAL_CAPITAL", 0))
    if total <= 0:
        raise EnvironmentError("TOTAL_CAPITAL must be set and greater than zero.")
    try:
        with db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM capital_account")
            count = cur.fetchone()[0]
            if count == 0:
                cur.execute(
                    """
                    INSERT INTO capital_account
                        (total_capital, deployed_capital, available_capital, realised_pnl)
                    VALUES (%s, 0.00, %s, 0.00)
                    """,
                    (total, total),
                )
                logger.info(f"[CAPITAL_ACCOUNT] Seeded with ₹{total:,.2f}")
            else:
                # If no capital has been deployed and no trades closed, allow
                # TOTAL_CAPITAL changes in .env to take effect.
                cur.execute(
                    "SELECT total_capital, deployed_capital, realised_pnl FROM capital_account"
                )
                row = cur.fetchone()
                stored_total = float(row[0])
                deployed = float(row[1])
                realised = float(row[2])
                if stored_total != total and deployed == 0.0 and realised == 0.0:
                    cur.execute(
                        """
                        UPDATE capital_account
                        SET total_capital=%s, available_capital=%s, updated_at=NOW()
                        """,
                        (total, total),
                    )
                    logger.info(f"[CAPITAL_ACCOUNT] Updated to ₹{total:,.2f} (no trades yet)")
                else:
                    logger.info("[CAPITAL_ACCOUNT] Already initialised — skipping seed")
        return True
    except Exception as e:
        logger.error(f"[CAPITAL_ACCOUNT] Initialisation failed: {e}")
        return False


def get_account() -> Optional[dict]:
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT total_capital, deployed_capital, available_capital,
                       realised_pnl, updated_at
                FROM capital_account
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "total_capital":     float(row[0]),
            "deployed_capital":  float(row[1]),
            "available_capital": float(row[2]),
            "realised_pnl":      float(row[3]),
            "updated_at":        row[4].isoformat() if row[4] else None,
        }
    except Exception as e:
        logger.error(f"[CAPITAL_ACCOUNT] get_account failed: {e}")
        return None


def deploy_capital(amount: float, symbol: str) -> bool:
    if amount <= 0:
        logger.error(f"[CAPITAL_ACCOUNT] deploy_capital called with non-positive amount: {amount}")
        return False
    try:
        with db_cursor() as cur:
            # Atomic UPDATE: the WHERE clause checks available_capital in the same
            # statement that modifies it, preventing the SELECT-then-INSERT race condition.
            cur.execute(
                """
                UPDATE capital_account
                SET deployed_capital  = deployed_capital + %s,
                    available_capital = available_capital - %s,
                    updated_at        = NOW()
                WHERE available_capital >= %s
                RETURNING deployed_capital, available_capital
                """,
                (amount, amount, amount),
            )
            row = cur.fetchone()
            if row is None:
                logger.warning(
                    f"[CAPITAL_ACCOUNT] Insufficient capital for {symbol}: "
                    f"requested ₹{amount:,.2f} — no account row or available_capital too low"
                )
                return False
            new_deployed, new_available = float(row[0]), float(row[1])

        logger.info(
            f"[CAPITAL_ACCOUNT] Deployed ₹{amount:,.2f} for {symbol}. "
            f"Available: ₹{new_available:,.2f}"
        )
        return True
    except Exception as e:
        logger.error(f"[CAPITAL_ACCOUNT] deploy_capital failed: {e}")
        return False


def release_capital(amount: float, realised_pnl: float) -> bool:
    try:
        with db_cursor() as cur:
            # Atomic UPDATE — avoids SELECT-then-INSERT race condition.
            cur.execute(
                """
                UPDATE capital_account
                SET deployed_capital  = GREATEST(deployed_capital - %s, 0),
                    available_capital = available_capital + %s + %s,
                    total_capital     = total_capital + %s,
                    realised_pnl      = realised_pnl + %s,
                    updated_at        = NOW()
                RETURNING total_capital, deployed_capital, available_capital
                """,
                (amount, amount, realised_pnl, realised_pnl, realised_pnl),
            )
            row = cur.fetchone()
            if row is None:
                logger.error("[CAPITAL_ACCOUNT] No account row found during release")
                return False
            new_total, new_deployed, new_available = float(row[0]), float(row[1]), float(row[2])

        logger.info(
            f"[CAPITAL_ACCOUNT] Released ₹{amount:,.2f}, P&L={realised_pnl:+.2f}. "
            f"Total: ₹{new_total:,.2f}, Available: ₹{new_available:,.2f}"
        )
        return True
    except Exception as e:
        logger.error(f"[CAPITAL_ACCOUNT] release_capital failed: {e}")
        return False


def get_available_capital() -> float:
    acct = get_account()
    if acct is None:
        return 0.0
    return acct.get("available_capital", 0.0)


def get_deployed_capital() -> float:
    acct = get_account()
    if acct is None:
        return 0.0
    return acct.get("deployed_capital", 0.0)
