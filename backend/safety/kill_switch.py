from datetime import datetime, timezone
from utils.logger import setup_logger
from db.connection import db_cursor

logger = setup_logger(__name__)


def is_trading_halted() -> bool:
    """Return True if kill switch is active. Fails safe — returns True on DB error."""
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT is_active FROM kill_switch ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False
    except Exception as e:
        logger.error(f"[KILL_SWITCH] DB error checking kill switch — failing safe: {e}")
        return True


def activate_kill_switch(reason: str, activated_by: str) -> bool:
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO kill_switch (is_active, reason, activated_by)
                VALUES (TRUE, %s, %s)
                """,
                (reason, activated_by),
            )
        logger.warning(f"[KILL_SWITCH] ACTIVATED by '{activated_by}': {reason}")
        return True
    except Exception as e:
        logger.error(f"[KILL_SWITCH] Failed to activate: {e}")
        return False


def check_and_halt_if_degraded() -> bool:
    """
    Check model health and activate kill switch if model has degraded.

    Returns:
        True if kill switch was activated (trading halted).
        False if model is healthy (or insufficient data to judge).
    """
    try:
        from feedback.model_monitor import is_model_healthy
        if not is_model_healthy():
            logger.critical(
                "[SAFETY] Auto-halt triggered: model accuracy below threshold"
            )
            activated = activate_kill_switch(
                reason="Model accuracy below threshold — auto-halted",
                activated_by="model_monitor",
            )
            if activated:
                logger.critical("[SAFETY] Kill switch ACTIVATED by model monitor")
                return True
    except Exception as e:
        logger.warning(f"[KILL_SWITCH] check_and_halt_if_degraded error: {e}")
    return False


def deactivate_kill_switch() -> bool:
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO kill_switch (is_active, reason, activated_by, deactivated_at)
                VALUES (FALSE, 'manual_resume', 'system', %s)
                """,
                (datetime.now(timezone.utc),),
            )
        logger.info("[KILL_SWITCH] Deactivated — trading resumed")
        return True
    except Exception as e:
        logger.error(f"[KILL_SWITCH] Failed to deactivate: {e}")
        return False
