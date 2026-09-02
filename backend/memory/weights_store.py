"""
Weight persistence via PostgreSQL (append-only — full weight history is preserved).

update_weights_from_trades() runs one pass of stochastic gradient ascent on
the binary cross-entropy loss over all completed (correct/wrong) trades whose
feature vectors were recorded at decision time.

Outcome encoding (maps to "did price go up?"):
    BUY  + correct → y = 1
    BUY  + wrong   → y = 0
    SELL + correct → y = 0
    SELL + wrong   → y = 1
"""

import math
from utils.logger import setup_logger
from db.connection import db_cursor

logger = setup_logger(__name__)

# Canonical defaults — must stay in sync with decision_agent.DEFAULT_WEIGHTS
DEFAULT_WEIGHTS = {
    "w_bias":       0.1,
    "w_trend":      1.2,
    "w_sentiment":  0.8,
    "w_pattern":    1.5,
    "w_volatility": -0.5,
    "w_sr_signal":  1.0,
    "w_volume":     0.3,
}


def load_weights() -> dict:
    """Return the most recently saved weights, or defaults if table is empty."""
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT w_bias, w_trend, w_sentiment, w_pattern,
                       w_volatility, w_sr_signal, w_volume
                FROM weights
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()

        if row is None:
            logger.info("[WEIGHTS] No saved weights found — using defaults")
            return DEFAULT_WEIGHTS.copy()

        saved = {
            "w_bias":       float(row[0]),
            "w_trend":      float(row[1]),
            "w_sentiment":  float(row[2]),
            "w_pattern":    float(row[3]),
            "w_volatility": float(row[4]),
            "w_sr_signal":  float(row[5]),
            "w_volume":     float(row[6]),
        }
        # Fill any missing keys from defaults (future-proofing)
        weights = DEFAULT_WEIGHTS.copy()
        weights.update(saved)
        return weights

    except Exception as e:
        logger.error(f"[WEIGHTS] Failed to load weights: {e}")
        return DEFAULT_WEIGHTS.copy()


def save_weights(weights: dict):
    """Append a new row to the weights table (history preserved)."""
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO weights
                    (w_bias, w_trend, w_sentiment, w_pattern,
                     w_volatility, w_sr_signal, w_volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    weights.get("w_bias",       DEFAULT_WEIGHTS["w_bias"]),
                    weights.get("w_trend",      DEFAULT_WEIGHTS["w_trend"]),
                    weights.get("w_sentiment",  DEFAULT_WEIGHTS["w_sentiment"]),
                    weights.get("w_pattern",    DEFAULT_WEIGHTS["w_pattern"]),
                    weights.get("w_volatility", DEFAULT_WEIGHTS["w_volatility"]),
                    weights.get("w_sr_signal",  DEFAULT_WEIGHTS["w_sr_signal"]),
                    weights.get("w_volume",     DEFAULT_WEIGHTS["w_volume"]),
                ),
            )
        logger.info(f"[WEIGHTS] Saved: {weights}")
    except Exception as e:
        logger.error(f"[WEIGHTS] Failed to save weights: {e}")


def _sigmoid(x: float) -> float:
    x = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def update_weights_from_trades(trades: dict, learning_rate: float = 0.01) -> dict:
    """
    Gradient ascent on log-likelihood over completed trades.

    Each trade must have:
        action          : "BUY" | "SELL"
        result          : "correct" | "wrong"
        features_vector : dict (stored by action_agent at decision time)

    Returns updated weights dict (also persisted to DB).
    """
    weights = load_weights()

    eligible = [
        t for t in trades.values()
        if t.get("result") in ("correct", "wrong")
        and t.get("features_vector")
        and t.get("action") in ("BUY", "SELL")
    ]

    if not eligible:
        logger.warning("[WEIGHTS] No eligible trades found for weight update")
        return weights

    # Split into training (80%) and validation (20%) sets — temporal order preserved
    split_idx = int(len(eligible) * 0.8)
    train_set = eligible[:split_idx]
    val_set   = eligible[split_idx:]

    if not train_set:
        logger.warning("[WEIGHTS] No training trades after split — skipping update")
        return weights

    for trade in train_set:
        fv     = trade["features_vector"]
        action = trade["action"]
        result = trade["result"]

        # Ground truth: did price go up?
        y = 1.0 if (action == "BUY"  and result == "correct") or \
                   (action == "SELL" and result == "wrong")  else 0.0

        x = {
            "w_bias":       1.0,
            "w_trend":      fv.get("trend",              0.0),
            "w_sentiment":  fv.get("sentiment",          0.0),
            "w_pattern":    fv.get("pattern_direction",  0.0) * fv.get("pattern_confidence", 0.0),
            "w_volatility": fv.get("volatility_norm",    0.0),
            "w_sr_signal":  fv.get("sr_signal",          0.0),
            "w_volume":     fv.get("volume_signal",       0.0),
        }

        z = sum(weights.get(k, 0.0) * v for k, v in x.items())
        p = _sigmoid(z)
        error = y - p

        for k, xk in x.items():
            weights[k] = weights.get(k, 0.0) + learning_rate * error * xk

    if len(val_set) < 3:
        # Insufficient held-out data to validate — apply update unconditionally
        save_weights(weights)
        logger.info(
            f"[WEIGHTS] Updated from {len(train_set)} train trades (lr={learning_rate}) "
            "(skipped validation — insufficient held-out trades)"
        )
        return {**weights, "update_applied": True, "accuracy_before": None, "accuracy_after": None}

    # Compute accuracy before and after on the held-out validation set
    try:
        current_weights = load_weights()
        acc_before = _simulate_accuracy(current_weights, val_set)
        acc_after  = _simulate_accuracy(weights, val_set)

        if acc_after < acc_before - 0.05:
            logger.critical(
                f"[WEIGHTS] Update rejected: validation accuracy {acc_after:.3f} vs "
                f"current {acc_before:.3f} (delta={acc_after - acc_before:+.3f})"
            )
            return {
                **current_weights,
                "update_applied":  False,
                "accuracy_before": round(acc_before, 4),
                "accuracy_after":  round(acc_after, 4),
            }

        logger.info(
            f"[WEIGHTS] Update applied: held-out accuracy {acc_before:.3f} → {acc_after:.3f} "
            f"(train={len(train_set)}, val={len(val_set)})"
        )
    except Exception as _val_err:
        logger.warning(f"[WEIGHTS] Validation failed ({_val_err}) — applying update anyway")
        acc_before = None
        acc_after  = None

    save_weights(weights)
    logger.info(f"[WEIGHTS] Updated from {len(eligible)} trades (lr={learning_rate})")
    return {
        **weights,
        "update_applied":  True,
        "accuracy_before": round(acc_before, 4) if acc_before is not None else None,
        "accuracy_after":  round(acc_after, 4)  if acc_after  is not None else None,
    }


def _simulate_accuracy(weights: dict, eligible: list) -> float:
    """
    Compute directional accuracy of weights on the eligible trade set.
    Predicts UP if p_up > 0.5, DOWN otherwise.
    Returns fraction of correct predictions.
    """
    if not eligible:
        return 0.0

    correct = 0
    for trade in eligible:
        fv     = trade["features_vector"]
        action = trade["action"]
        result = trade["result"]

        x = {
            "w_bias":       1.0,
            "w_trend":      fv.get("trend",             0.0),
            "w_sentiment":  fv.get("sentiment",         0.0),
            "w_pattern":    fv.get("pattern_direction", 0.0) * fv.get("pattern_confidence", 0.0),
            "w_volatility": fv.get("volatility_norm",   0.0),
            "w_sr_signal":  fv.get("sr_signal",         0.0),
            "w_volume":     fv.get("volume_signal",      0.0),
        }
        z    = sum(weights.get(k, 0.0) * v for k, v in x.items())
        p_up = _sigmoid(z)
        predicted_up = p_up > 0.5

        # Ground truth: did price go up?
        actual_up = (
            (action == "BUY"  and result == "correct") or
            (action == "SELL" and result == "wrong")
        )
        if predicted_up == actual_up:
            correct += 1

    return correct / len(eligible)
