"""
Log retention — deletes old rows from high-volume ephemeral tables.
Permanent records (trades, positions, orders, backtest_*, weights,
pnl_snapshots, model_performance) are never touched.

Run daily at 02:00 IST via scheduler.
"""
from datetime import datetime, timezone
import logging

from db.connection import db_cursor

_logger = logging.getLogger("log_retention")

_SAFE_TABLES = {
    "trades", "positions", "orders", "backtest_runs",
    "backtest_trades", "backtest_equity_curve",
    "weights", "pnl_snapshots", "model_performance", "capital_account",
}


def run_retention(
    audit_log_days: int = 30,
    pipeline_metrics_days: int = 7,
    llm_calls_days: int = 14,
    rate_limit_days: int = 1,
) -> dict:
    """
    Delete aged rows from ephemeral log tables.

    Args:
        audit_log_days:         Retain audit_log rows for N days.
        pipeline_metrics_days:  Retain pipeline_metrics rows for N days.
        llm_calls_days:         Retain llm_calls rows for N days.
        rate_limit_days:        Retain rate_limit_log rows for N days.

    Returns:
        dict with deleted row counts per table and ran_at timestamp.

    Raises:
        ValueError if any retention period is 0 (safeguard).
    """
    for name, days in [
        ("audit_log_days",          audit_log_days),
        ("pipeline_metrics_days",   pipeline_metrics_days),
        ("llm_calls_days",          llm_calls_days),
        ("rate_limit_days",         rate_limit_days),
    ]:
        if days <= 0:
            raise ValueError(
                f"Retention period {name}={days} must be > 0. "
                "Set to 1+ to prevent accidental full table deletion."
            )

    result = {
        "audit_log_deleted":          0,
        "pipeline_metrics_deleted":   0,
        "llm_calls_deleted":          0,
        "rate_limit_deleted":         0,
        "ran_at":                     datetime.now(timezone.utc).isoformat(),
    }

    deletions = [
        ("audit_log",        "audit_log_deleted",        audit_log_days),
        ("pipeline_metrics", "pipeline_metrics_deleted",  pipeline_metrics_days),
        ("llm_calls",        "llm_calls_deleted",         llm_calls_days),
        ("rate_limit_log",   "rate_limit_deleted",        rate_limit_days),
    ]

    for table, key, days in deletions:
        try:
            with db_cursor() as cur:
                cur.execute(
                    f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '{days} days'"
                )
                result[key] = cur.rowcount or 0
        except Exception as e:
            _logger.error(f"[LOG_RETENTION] Failed to clean {table}: {e}")

    # Log summary after deletion (not before)
    try:
        from observability.audit_log import log_event
        log_event(
            trace_id="maintenance",
            event_type="log_retention",
            component="log_retention",
            message=(
                f"Retention complete: "
                f"audit_log={result['audit_log_deleted']} "
                f"pipeline_metrics={result['pipeline_metrics_deleted']} "
                f"llm_calls={result['llm_calls_deleted']} "
                f"rate_limit={result['rate_limit_deleted']}"
            ),
            metadata=result,
        )
    except Exception:
        pass

    _logger.info(
        f"[LOG_RETENTION] Done — "
        f"audit_log={result['audit_log_deleted']} "
        f"pipeline_metrics={result['pipeline_metrics_deleted']} "
        f"llm_calls={result['llm_calls_deleted']} "
        f"rate_limit={result['rate_limit_deleted']}"
    )
    return result
