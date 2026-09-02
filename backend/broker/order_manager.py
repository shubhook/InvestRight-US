import math
import os
import time
from datetime import datetime, timezone

from broker.base import BaseBroker
from db.connection import db_cursor
from utils.logger import setup_logger

logger = setup_logger(__name__)

_MAX_RETRIES       = 3
_TERMINAL_STATUSES = {"FILLED", "CANCELLED", "FAILED", "REJECTED"}


# ---------------------------------------------------------------------------
# Quantity calculator
# ---------------------------------------------------------------------------

def calculate_quantity(
    position_size_fraction: float,
    entry_price: float,
    total_capital: float,
) -> int:
    """
    Return the number of whole shares to buy/sell.
    Returns 0 when the result would be less than 1 share.
    """
    if total_capital <= 0:
        logger.error(
            "[ORDER_MGR] TOTAL_CAPITAL is zero or not set — "
            "cannot calculate quantity. Returning 0."
        )
        return 0
    if not entry_price:
        logger.error("[ORDER_MGR] entry_price is zero or None — returning 0 shares")
        return 0

    fraction = min(float(position_size_fraction), 1.0)
    qty = math.floor((fraction * total_capital) / entry_price)
    return max(qty, 0)


def _total_capital() -> float:
    val = os.getenv("TOTAL_CAPITAL")
    if not val:
        raise EnvironmentError("TOTAL_CAPITAL environment variable is not set.")
    tc = float(val)
    if tc <= 0:
        raise EnvironmentError("TOTAL_CAPITAL must be greater than zero.")
    return tc


# ---------------------------------------------------------------------------
# Order submission with exponential-backoff retry
# ---------------------------------------------------------------------------

def submit_order(broker: BaseBroker, order_params: dict) -> dict:
    """
    Place an order; retry up to _MAX_RETRIES times on FAILED status.
    Delays: 2 s, 4 s, 8 s.
    """
    result = None
    for attempt in range(_MAX_RETRIES):
        result = broker.place_order(order_params)

        if result.get("status") != "FAILED":
            return result

        wait = 2 ** (attempt + 1)          # 2, 4, 8
        logger.warning(
            f"[ORDER_MGR] Placement attempt {attempt + 1}/{_MAX_RETRIES} failed "
            f"({result.get('failure_reason')}) — retrying in {wait}s"
        )
        _update_retry_count(result.get("order_id"), attempt + 1)
        if attempt < _MAX_RETRIES - 1:
            time.sleep(wait)

    # All retries exhausted
    logger.error(
        f"[ORDER_MGR] All {_MAX_RETRIES} attempts failed for "
        f"{order_params.get('symbol')} {order_params.get('action')}"
    )
    return result


# ---------------------------------------------------------------------------
# Status polling
# ---------------------------------------------------------------------------

def poll_order_status(
    broker: BaseBroker,
    broker_order_id: str,
    trade_id: str,
    max_polls: int = 10,
    poll_interval_seconds: int = 3,
) -> dict:
    """
    Poll until the order reaches a terminal state or max_polls is exceeded.
    Paper orders fill immediately so this exits on the first poll.
    """
    status_result = None
    for poll in range(max_polls):
        status_result = broker.get_order_status(broker_order_id)
        status = status_result.get("status")

        if status == "FILLED":
            handle_fill(broker_order_id, status_result)
            return status_result

        if status in ("PARTIAL",):
            logger.warning(
                f"[ORDER_MGR] Partial fill for {broker_order_id}: "
                f"{status_result.get('filled_quantity')} filled — accepting partial"
            )
            handle_fill(broker_order_id, status_result)
            return status_result

        if status in ("CANCELLED", "FAILED", "REJECTED"):
            _update_order_status(broker_order_id, status, status_result.get("failure_reason"))
            return status_result

        if poll < max_polls - 1:
            time.sleep(poll_interval_seconds)

    # Poll timeout — leave as PENDING, do NOT mark FAILED
    logger.warning(
        f"[ORDER_MGR] Poll timeout for {broker_order_id} — "
        f"status unknown, manual review required"
    )
    return status_result or {"status": "PENDING", "broker_order_id": broker_order_id}


# ---------------------------------------------------------------------------
# Fill handler
# ---------------------------------------------------------------------------

def handle_fill(broker_order_id: str, status_result: dict) -> bool:
    """
    Persist fill details to the orders table.
    Idempotent: UPDATE WHERE status != 'FILLED' — second call is a no-op.
    """
    filled_qty   = status_result.get("filled_quantity", 0)
    filled_price = status_result.get("filled_price")
    now          = datetime.now(timezone.utc)

    try:
        with db_cursor() as cur:
            cur.execute(
                """
                UPDATE orders
                SET status='FILLED',
                    filled_quantity=%s,
                    filled_price=%s,
                    filled_at=%s,
                    updated_at=%s
                WHERE broker_order_id=%s
                  AND status != 'FILLED'
                """,
                (filled_qty, filled_price, now, now, broker_order_id),
            )
        logger.info(
            f"[ORDER_MGR] Fill recorded: {broker_order_id} "
            f"qty={filled_qty} price={filled_price}"
        )
        return True
    except Exception as e:
        logger.critical(
            f"[ORDER_MGR] CRITICAL: Fill DB write failed for {broker_order_id} — "
            f"order filled at broker but DB is out of sync. Manual review required. Error: {e}"
        )
        return False


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

def _update_order_status(order_id: str, status: str, reason: str = None):
    if not order_id:
        logger.warning(
            f"[ORDER_MGR] _update_order_status called with null order_id (status={status}) — skipping"
        )
        return
    try:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE orders SET status=%s, failure_reason=%s, updated_at=%s "
                "WHERE order_id=%s OR broker_order_id=%s",
                (status, reason, datetime.now(timezone.utc), order_id, order_id),
            )
    except Exception as e:
        logger.error(f"[ORDER_MGR] Failed to update order status: {e}")


def _update_retry_count(order_id: str, count: int):
    if not order_id:
        return
    try:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE orders SET retry_count=%s, updated_at=%s WHERE order_id=%s",
                (count, datetime.now(timezone.utc), order_id),
            )
    except Exception:
        pass  # Non-critical
