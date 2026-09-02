from utils.logger import setup_logger
from db.connection import db_cursor
from memory.memory_store import get_trade, update_trade_result, get_all_trades

logger = setup_logger(__name__)


def get_failure_patterns() -> list:
    """
    Return pattern names where wrong/total > 0.5 AND total >= 5.
    Pattern is read from features_vector->>'pattern' JSONB field.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT
                    features_vector->>'pattern'           AS pattern,
                    COUNT(*)                              AS total,
                    COUNT(*) FILTER (WHERE result = 'wrong') AS wrong_count
                FROM trades
                WHERE
                    features_vector->>'pattern' IS NOT NULL
                    AND result IN ('correct', 'wrong')
                GROUP BY features_vector->>'pattern'
                HAVING
                    COUNT(*) >= 5
                    AND COUNT(*) FILTER (WHERE result = 'wrong')::float / COUNT(*) > 0.5
                """
            )
            rows = cur.fetchall()
            patterns = [row[0] for row in rows]
        logger.info(f"[MEMORY_READER] Found failure patterns: {patterns}")
        return patterns
    except Exception as e:
        logger.error(f"[MEMORY_READER] Error getting failure patterns: {e}")
        return []


def get_success_rate(pattern: str) -> float:
    """
    Return correct/total for the given pattern, or 0.0 if fewer than 5 samples.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)                               AS total,
                    COUNT(*) FILTER (WHERE result = 'correct') AS correct_count
                FROM trades
                WHERE
                    features_vector->>'pattern' = %s
                    AND result IN ('correct', 'wrong')
                """,
                (pattern,),
            )
            row = cur.fetchone()
            total, correct = row if row else (0, 0)
            total = int(total or 0)
            correct = int(correct or 0)

        if total < 5:
            return 0.0
        rate = correct / total
        logger.info(f"[MEMORY_READER] Success rate for '{pattern}': {rate:.2f}")
        return rate
    except Exception as e:
        logger.error(f"[MEMORY_READER] Error getting success rate for {pattern}: {e}")
        return 0.0
