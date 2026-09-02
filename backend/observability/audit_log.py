"""
Structured audit log — writes to stdout (JSON) AND the audit_log DB table.

Design rules:
  - Stdout writes are synchronous (immediate).
  - DB writes are fire-and-forget via a background thread queue.
  - DB failure NEVER crashes the application.
  - Queue capped at 1000 items; oldest dropped on overflow.
  - Never import utils/logger to avoid circular deps.
"""
import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

# Module-level constants — event type strings
PIPELINE_START     = "pipeline_start"
PIPELINE_END       = "pipeline_end"
DATA_FETCH         = "data_fetch"
ANALYSIS_COMPLETE  = "analysis_complete"
PATTERN_DETECTED   = "pattern_detected"
DECISION_MADE      = "decision_made"
RISK_APPLIED       = "risk_applied"
ORDER_PLACED       = "order_placed"
ORDER_FILLED       = "order_filled"
POSITION_OPENED    = "position_opened"
POSITION_CLOSED    = "position_closed"
KILL_SWITCH_ACTIVE = "kill_switch_active"
DUPLICATE_SIGNAL   = "duplicate_signal"
CAPITAL_LIMIT_HIT  = "capital_limit_hit"
LLM_CALL           = "llm_call"
WEIGHT_UPDATE      = "weight_update"
MODEL_DEGRADATION  = "model_degradation"

_QUEUE_MAX = 1000
_db_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
_dropped_count = 0
_db_worker_started = False
_worker_lock = threading.Lock()
_stdout_logger = logging.getLogger("audit_log")


def _ensure_worker() -> None:
    """Start the background DB-writer thread once."""
    global _db_worker_started
    with _worker_lock:
        if _db_worker_started:
            return
        t = threading.Thread(target=_db_writer_loop, daemon=True)
        t.start()
        _db_worker_started = True


def _db_writer_loop() -> None:
    """Drain the queue and write audit_log rows to Postgres."""
    while True:
        try:
            row = _db_queue.get(timeout=2)
        except queue.Empty:
            continue
        try:
            from db.connection import db_cursor
            with db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log
                        (trace_id, event_type, component, symbol, trade_id,
                         severity, message, metadata, duration_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row["trace_id"], row["event_type"], row["component"],
                        row.get("symbol"), row.get("trade_id"),
                        row["severity"], row["message"],
                        json.dumps(row["metadata"]) if row.get("metadata") else None,
                        row.get("duration_ms"),
                    ),
                )
        except Exception as e:
            _stdout_logger.warning(f"[AUDIT_LOG] DB write failed: {e}")
        finally:
            _db_queue.task_done()


_MAX_METADATA_CHARS = 4000   # guard against oversized JSONB inserts


def _safe_metadata(metadata: Optional[dict]) -> Optional[dict]:
    """Ensure metadata is JSON-serialisable; convert problematic values to str."""
    if metadata is None:
        return None
    safe = {}
    for k, v in metadata.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    try:
        serialized = json.dumps(safe)
        if len(serialized) > _MAX_METADATA_CHARS:
            return {"_truncated": True, "_original_size": len(serialized)}
    except Exception:
        return {"_error": "metadata_unserializable"}
    return safe


def log_event(
    trace_id: Optional[str],
    event_type: str,
    component: str,
    message: str,
    severity: str = "INFO",
    symbol: Optional[str] = None,
    trade_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """
    Log a pipeline event to stdout (JSON) and the audit_log DB table.

    Args:
        trace_id:    Pipeline trace UUID (use "no-trace" if None).
        event_type:  One of the module-level event type constants.
        component:   Module/agent name (e.g. "analysis_agent").
        message:     Human-readable description.
        severity:    DEBUG | INFO | WARNING | ERROR | CRITICAL.
        symbol:      Stock symbol if applicable.
        trade_id:    Trade UUID if applicable.
        metadata:    Arbitrary additional context (JSON-serialisable).
        duration_ms: Component execution time in milliseconds.
    """
    _ensure_worker()
    effective_trace = trace_id or str(uuid.uuid4())
    safe_meta = _safe_metadata(metadata)

    # --- Synchronous stdout write ---
    log_line = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "trace_id":    effective_trace,
        "severity":    severity,
        "event_type":  event_type,
        "component":   component,
        "message":     message,
    }
    if symbol:
        log_line["symbol"] = symbol
    if trade_id:
        log_line["trade_id"] = trade_id
    if duration_ms is not None:
        log_line["duration_ms"] = duration_ms
    if safe_meta:
        log_line["metadata"] = safe_meta

    try:
        print(json.dumps(log_line), flush=True)
    except Exception:
        pass

    # --- Async DB write ---
    global _dropped_count
    row = {
        "trace_id":   effective_trace,
        "event_type": event_type,
        "component":  component,
        "symbol":     symbol,
        "trade_id":   trade_id,
        "severity":   severity,
        "message":    message,
        "metadata":   safe_meta,
        "duration_ms": duration_ms,
    }
    try:
        _db_queue.put_nowait(row)
    except queue.Full:
        # Drop the oldest item and enqueue the new one
        try:
            _db_queue.get_nowait()
            _db_queue.task_done()
        except queue.Empty:
            pass
        _dropped_count += 1
        try:
            _db_queue.put_nowait(row)
        except queue.Full:
            pass
        if _dropped_count % 10 == 1:
            print(
                json.dumps({
                    "severity": "WARNING",
                    "component": "audit_log",
                    "message": f"[AUDIT_LOG] Queue overflow — {_dropped_count} events dropped",
                }),
                flush=True,
            )


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def log_pipeline_start(trace: "TraceContext") -> None:  # type: ignore[name-defined]
    log_event(
        trace_id=trace.trace_id,
        event_type=PIPELINE_START,
        component="pipeline",
        message=f"Pipeline started for {trace.symbol}",
        symbol=trace.symbol,
    )


def log_pipeline_end(trace: "TraceContext", result: str) -> None:  # type: ignore[name-defined]
    log_event(
        trace_id=trace.trace_id,
        event_type=PIPELINE_END,
        component="pipeline",
        message=f"Pipeline completed for {trace.symbol}: {result}",
        symbol=trace.symbol,
        duration_ms=trace.elapsed_ms(),
        metadata={"final_action": result},
    )


def log_component_timing(
    trace: "TraceContext",  # type: ignore[name-defined]
    component: str,
    duration_ms: int,
    status: str,
) -> None:
    log_event(
        trace_id=trace.trace_id,
        event_type="component_timing",
        component=component,
        message=f"{component} completed in {duration_ms}ms ({status})",
        symbol=trace.symbol,
        duration_ms=duration_ms,
        metadata={"status": status},
    )
