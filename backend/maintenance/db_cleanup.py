"""
Database maintenance tasks — run daily at 03:00 IST via scheduler.
"""
import logging

from db.connection import db_cursor

_logger = logging.getLogger("db_cleanup")


def vacuum_tables() -> bool:
    """
    Run ANALYZE on all major tables to update query planner statistics.
    Does NOT run VACUUM (may require superuser).

    Returns:
        True on success, False on error.
    """
    tables = [
        "trades", "positions", "orders", "capital_account",
        "weights", "audit_log", "pipeline_metrics", "llm_calls",
        "backtest_runs", "backtest_trades", "pnl_snapshots",
        "model_performance", "kill_switch", "idempotency_log",
    ]
    try:
        # ANALYZE must run outside a transaction block
        import psycopg2
        from db.connection import get_connection, release_connection
        conn = get_connection()
        conn.set_isolation_level(0)   # autocommit
        cur = conn.cursor()
        for table in tables:
            try:
                cur.execute(f"ANALYZE {table}")
            except Exception as e:
                _logger.warning(f"[DB_CLEANUP] ANALYZE {table} failed: {e}")
        cur.close()
        conn.set_isolation_level(1)   # restore default
        release_connection(conn)
        _logger.info(f"[DB_CLEANUP] ANALYZE complete for {len(tables)} tables")
        return True
    except Exception as e:
        _logger.error(f"[DB_CLEANUP] vacuum_tables error: {e}")
        return False


def reset_stale_backtest_runs() -> int:
    """
    Find backtest_runs stuck in 'running' status for > 2 hours and mark them failed.
    These are runs that crashed without updating their status.

    Returns:
        Number of runs reset.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                UPDATE backtest_runs
                SET status        = 'failed',
                    error_message = 'Stale run reset by maintenance job',
                    completed_at  = NOW()
                WHERE status     = 'running'
                  AND created_at < NOW() - INTERVAL '2 hours'
                """
            )
            count = cur.rowcount or 0
        if count:
            _logger.info(f"[DB_CLEANUP] Reset {count} stale backtest run(s)")
        return count
    except Exception as e:
        _logger.error(f"[DB_CLEANUP] reset_stale_backtest_runs error: {e}")
        return 0


def cleanup_orphaned_idempotency_keys() -> int:
    """
    Delete idempotency_log rows older than 24 hours.
    Keys are only valid for 15-minute windows and can safely be purged.

    Returns:
        Number of rows deleted.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                "DELETE FROM idempotency_log WHERE created_at < NOW() - INTERVAL '24 hours'"
            )
            count = cur.rowcount or 0
        if count:
            _logger.info(f"[DB_CLEANUP] Purged {count} orphaned idempotency key(s)")
        return count
    except Exception as e:
        _logger.error(f"[DB_CLEANUP] cleanup_orphaned_idempotency_keys error: {e}")
        return 0


def run_all() -> dict:
    """Run all cleanup tasks and return a summary."""
    analyzed  = vacuum_tables()
    stale     = reset_stale_backtest_runs()
    idem_keys = cleanup_orphaned_idempotency_keys()
    _logger.info(
        f"[DB_CLEANUP] Maintenance complete — "
        f"analyzed={analyzed} stale_runs_reset={stale} "
        f"idem_keys_purged={idem_keys}"
    )
    return {
        "vacuum_ok":               analyzed,
        "stale_runs_reset":        stale,
        "idempotency_keys_purged": idem_keys,
    }
