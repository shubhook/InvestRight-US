"""
In-memory latency metrics collector.
Aggregates per-component timing, flushes to pipeline_metrics every 5 minutes.
"""
import os
import threading
import time
from collections import defaultdict
from typing import List, Optional

_lock = threading.Lock()
# Stores list of (timestamp, duration_ms, status, trace_id, symbol)
_timings: dict = defaultdict(list)
_last_flush: float = time.monotonic()
_FLUSH_INTERVAL_S = int(os.getenv("METRICS_FLUSH_INTERVAL_S", "300"))  # default 5 minutes


def record_timing(
    trace_id: str,
    component: str,
    symbol: Optional[str],
    duration_ms: int,
    status: str,
) -> None:
    """
    Record a component execution timing.

    Args:
        trace_id:    Pipeline trace UUID.
        component:   Component name (e.g. "analysis_agent").
        symbol:      Stock symbol or None.
        duration_ms: Execution time in milliseconds.
        status:      "success" or "failure".
    """
    entry = {
        "ts":          time.monotonic(),
        "trace_id":    trace_id,
        "symbol":      symbol,
        "duration_ms": duration_ms,
        "status":      status,
    }
    with _lock:
        _timings[component].append(entry)

    # Flush if interval elapsed
    if time.monotonic() - _last_flush > _FLUSH_INTERVAL_S:
        _try_flush()


def get_component_stats(
    component: str,
    last_n_minutes: int = 60,
) -> dict:
    """
    Return aggregated stats for a component over the last N minutes.

    Returns a dict with total_calls, success_rate, avg/p95/p99 latency.
    """
    cutoff = time.monotonic() - last_n_minutes * 60

    with _lock:
        entries = [e for e in _timings.get(component, []) if e["ts"] >= cutoff]

    if not entries:
        return {
            "component":      component,
            "period_minutes": last_n_minutes,
            "total_calls":    0,
            "success_rate":   0.0,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "failure_count":  0,
        }

    durations     = sorted(e["duration_ms"] for e in entries)
    success_count = sum(1 for e in entries if e["status"] == "success")
    total         = len(entries)
    avg_ms        = int(sum(durations) / total)

    if total >= 20:
        p95_ms = durations[int(total * 0.95)]
        p99_ms = durations[int(total * 0.99)]
    else:
        p95_ms = avg_ms
        p99_ms = avg_ms

    return {
        "component":      component,
        "period_minutes": last_n_minutes,
        "total_calls":    total,
        "success_rate":   round(success_count / total, 4),
        "avg_latency_ms": avg_ms,
        "p95_latency_ms": p95_ms,
        "p99_latency_ms": p99_ms,
        "failure_count":  total - success_count,
    }


def get_all_stats(last_n_minutes: int = 60) -> dict:
    """Return stats for all recorded components."""
    with _lock:
        components = list(_timings.keys())
    return {c: get_component_stats(c, last_n_minutes) for c in components}


def flush_to_db() -> bool:
    """
    Write buffered timing data to pipeline_metrics table.
    Clears entries older than 2 hours from memory.
    Returns True on success.
    """
    global _last_flush
    try:
        from db.connection import db_cursor
        cutoff_keep = time.monotonic() - 7200  # keep last 2 hours in memory

        with _lock:
            snapshot = {c: list(entries) for c, entries in _timings.items()}
            # Prune old entries from memory
            for c in _timings:
                _timings[c] = [e for e in _timings[c] if e["ts"] >= cutoff_keep]

        with db_cursor() as cur:
            for component, entries in snapshot.items():
                for e in entries:
                    cur.execute(
                        """
                        INSERT INTO pipeline_metrics
                            (trace_id, component, symbol, duration_ms, status)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            e["trace_id"], component, e.get("symbol"),
                            e["duration_ms"], e["status"],
                        ),
                    )

        _last_flush = time.monotonic()
        return True

    except Exception as e:
        import logging
        logging.getLogger("metrics").warning(f"[METRICS] flush_to_db failed: {e}")
        return False


def _try_flush() -> None:
    """Attempt a DB flush in a background thread (non-blocking)."""
    t = threading.Thread(target=flush_to_db, daemon=True)
    t.start()
