import json
from datetime import datetime, timezone
from typing import Optional
from utils.logger import setup_logger
from db.connection import db_cursor

logger = setup_logger(__name__)


def _save_memory(memory_data: dict):
    """Deprecated shim — memory is now in PostgreSQL. No-op."""
    logger.warning("[MEMORY_STORE] _save_memory() is deprecated; data is persisted via PostgreSQL.")


def store_trade(trade_record: dict) -> bool:
    trade_id = trade_record.get("trade_id")
    if not trade_id:
        logger.error("[MEMORY_STORE] Trade record missing trade_id")
        return False

    features = trade_record.get("features_vector") or {}

    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades (
                    trade_id, timestamp, symbol, action,
                    entry, stop_loss, target, rr_ratio,
                    max_loss_pct, position_size_fraction,
                    features_vector, result, rejection_reason
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    trade_id,
                    trade_record.get("timestamp"),
                    trade_record.get("symbol"),
                    trade_record.get("action"),
                    trade_record.get("entry"),
                    trade_record.get("stop_loss"),
                    trade_record.get("target"),
                    trade_record.get("rr_ratio"),
                    trade_record.get("max_loss_pct"),
                    trade_record.get("position_size_fraction"),
                    json.dumps(features),
                    trade_record.get("result"),
                    trade_record.get("rejection_reason"),
                ),
            )
        logger.info(f"[MEMORY_STORE] Trade stored: {trade_id}")
        return True
    except Exception as e:
        # UniqueViolation and all other DB errors
        logger.error(f"[MEMORY_STORE] Error storing trade {trade_id}: {e}")
        return False


def get_trade(trade_id: str) -> Optional[dict]:
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT * FROM trades WHERE trade_id = %s",
                (trade_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in cur.description]
            return _row_to_dict(cols, row)
    except Exception as e:
        logger.error(f"[MEMORY_STORE] Error retrieving trade {trade_id}: {e}")
        return None


def update_trade_result(trade_id: str, result: str) -> bool:
    if result not in ("correct", "wrong"):
        logger.error(f"[MEMORY_STORE] Invalid result value: {result}")
        return False
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                UPDATE trades
                SET result = %s, updated_at = %s
                WHERE trade_id = %s
                """,
                (result, datetime.now(timezone.utc), trade_id),
            )
            if cur.rowcount == 0:
                logger.error(f"[MEMORY_STORE] Trade not found for update: {trade_id}")
                return False
        logger.info(f"[MEMORY_STORE] Trade {trade_id} result updated to: {result}")
        return True
    except Exception as e:
        logger.error(f"[MEMORY_STORE] Error updating trade result {trade_id}: {e}")
        return False


def get_all_trades() -> dict:
    try:
        with db_cursor() as cur:
            cur.execute("SELECT * FROM trades")
            rows = cur.fetchall()
            if not rows:
                return {}
            cols = [desc[0] for desc in cur.description]
            return {
                str(row[cols.index("trade_id")]): _row_to_dict(cols, row)
                for row in rows
            }
    except Exception as e:
        logger.error(f"[MEMORY_STORE] Error getting all trades: {e}")
        return {}


def _row_to_dict(cols: list, row: tuple) -> dict:
    d = dict(zip(cols, row))
    # Normalise types for downstream consumers
    for k, v in d.items():
        if hasattr(v, "isoformat"):          # datetime → ISO string
            d[k] = v.isoformat()
        elif hasattr(v, "__float__"):        # Decimal → float
            try:
                d[k] = float(v)
            except Exception:
                pass
    if "trade_id" in d:
        d["trade_id"] = str(d["trade_id"])
    return d
