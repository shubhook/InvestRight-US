"""
Model performance monitor.
Tracks prediction accuracy and detects model degradation over rolling windows.
Uses the trades table directly — no separate prediction store required.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from db.connection import db_cursor

_logger = logging.getLogger("model_monitor")

_MIN_SAMPLE = 10   # Minimum trades needed to assess health


def record_prediction(
    trade_id: str,
    probability_up: float,
    action: str,
) -> bool:
    """
    Store the probability_up prediction alongside a trade.
    In practice the trades table already carries features_vector with this
    information; this function is a no-op hook kept for API consistency.
    The actual prediction is read directly from the trades table in
    compute_accuracy_window().

    Returns True always (fail-open).
    """
    return True


def record_outcome(
    trade_id: str,
    result: str,
) -> bool:
    """
    Record that a trade's outcome is now known.
    The result is already written to the trades table by feedback_agent;
    this function logs the event and triggers a health snapshot.

    Returns True on success, False on error.
    """
    if result not in ("correct", "wrong"):
        return True  # pending — nothing to record yet
    try:
        _maybe_snapshot()
        return True
    except Exception as e:
        _logger.warning(f"[MODEL_MONITOR] record_outcome error: {e}")
        return False


def compute_accuracy_window(last_n_trades: int = 30) -> dict:
    """
    Compute accuracy metrics over the most recent N completed trades.

    Returns:
        {
            "window_trades":     int,
            "completed_trades":  int,
            "correct":           int,
            "wrong":             int,
            "accuracy":          float,
            "brier_score":       float,
            "avg_confidence":    float,
            "calibration_error": float,
            "is_healthy":        bool,
            "computed_at":       str (ISO),
        }
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT action, result, features_vector
                FROM trades
                WHERE result IN ('correct', 'wrong')
                  AND features_vector IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (last_n_trades,),
            )
            rows = cur.fetchall()

        if not rows:
            return _empty_window(last_n_trades)

        correct    = 0
        wrong      = 0
        brier_sum  = 0.0
        conf_sum   = 0.0
        cal_sum    = 0.0

        for action, result, fv in rows:
            try:
                if isinstance(fv, str):
                    import json
                    fv = json.loads(fv)
                if not isinstance(fv, dict):
                    fv = {}

                # Estimate probability_up from features — use pattern_confidence
                # as a confidence proxy (available in features_vector)
                prob_up    = float(fv.get("probability_up", 0.5)) if "probability_up" in fv else 0.5
                confidence = abs(prob_up - 0.5) * 2   # distance from 0.5, normalised [0,1]

                # Was price prediction directionally correct?
                actual_up = _is_up(action, result)   # 1 if price went up, 0 if went down

                if actual_up is not None:
                    if result == "correct":
                        correct += 1
                    else:
                        wrong += 1

                    brier_sum += (prob_up - actual_up) ** 2
                    conf_sum  += confidence
                    cal_sum   += abs(confidence - int(result == "correct"))
            except Exception:
                continue  # skip malformed rows, never crash health check

        completed = correct + wrong
        if completed == 0:
            return _empty_window(last_n_trades)

        accuracy          = correct / completed
        brier_score       = brier_sum / completed
        avg_confidence    = conf_sum / completed
        calibration_error = cal_sum  / completed

        healthy = (
            accuracy >= 0.40
            if completed >= _MIN_SAMPLE
            else True   # insufficient data
        )

        return {
            "window_trades":     last_n_trades,
            "completed_trades":  completed,
            "correct":           correct,
            "wrong":             wrong,
            "accuracy":          round(accuracy, 4),
            "brier_score":       round(brier_score, 6),
            "avg_confidence":    round(avg_confidence, 4),
            "calibration_error": round(calibration_error, 6),
            "is_healthy":        healthy,
            "computed_at":       datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        _logger.error(f"[MODEL_MONITOR] compute_accuracy_window error: {e}")
        return _empty_window(last_n_trades)


def is_model_healthy(threshold: float = 0.40) -> bool:
    """
    Return False if model accuracy is below threshold over last 30 trades.
    Returns True if fewer than MIN_SAMPLE completed trades exist.
    """
    stats = compute_accuracy_window(30)
    if stats["completed_trades"] < _MIN_SAMPLE:
        return True
    return stats["accuracy"] >= threshold


def compute_brier_score(last_n_trades: int = 30) -> float:
    """
    Mean squared error between predicted probability and actual outcome.
    Lower is better. Random = 0.25. Perfect = 0.0.
    """
    stats = compute_accuracy_window(last_n_trades)
    return stats.get("brier_score", 0.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_up(action: str, result: str) -> Optional[int]:
    """
    Determine if price went up (1) or down (0) from the trade direction + outcome.

    BUY  + correct → price went up   → 1
    BUY  + wrong   → price went down → 0
    SELL + correct → price went down → 0
    SELL + wrong   → price went up   → 1
    """
    if action == "BUY":
        return 1 if result == "correct" else 0
    if action == "SELL":
        return 0 if result == "correct" else 1
    return None


def _empty_window(window_trades: int) -> dict:
    return {
        "window_trades":     window_trades,
        "completed_trades":  0,
        "correct":           0,
        "wrong":             0,
        "accuracy":          0.0,
        "brier_score":       0.0,
        "avg_confidence":    0.0,
        "calibration_error": 0.0,
        "is_healthy":        True,
        "computed_at":       datetime.now(timezone.utc).isoformat(),
    }


def _maybe_snapshot() -> None:
    """Persist a model_performance row if enough time has elapsed."""
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT created_at FROM model_performance ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()

        # Only snapshot every ~15 minutes
        if row:
            from datetime import timedelta
            last_ts = row[0]
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - last_ts).total_seconds() < 900:
                return

        stats = compute_accuracy_window(30)
        from memory.weights_store import load_weights
        import json

        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO model_performance
                    (window_start, window_end, total_predictions,
                     correct_predictions, accuracy, brier_score,
                     avg_confidence, calibration_error, weights_snapshot)
                VALUES (
                    NOW() - INTERVAL '15 minutes', NOW(),
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    stats["completed_trades"],
                    stats["correct"],
                    stats.get("accuracy"),
                    stats.get("brier_score"),
                    stats.get("avg_confidence"),
                    stats.get("calibration_error"),
                    json.dumps(load_weights()),
                ),
            )
    except Exception as e:
        _logger.warning(f"[MODEL_MONITOR] _maybe_snapshot error: {e}")
