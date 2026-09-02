import os
from broker.base import BaseBroker
from utils.logger import setup_logger

logger = setup_logger(__name__)


def get_broker() -> BaseBroker:
    """
    Return the correct broker for the current BROKER_MODE.
    
    For US paper trading, defaults to AlpacaPaperBroker.
    Kite broker remains available but is not the default.
    
    Falls back to AlpacaPaperBroker if credentials are missing or init fails.
    """
    from broker.alpaca_paper_broker import AlpacaPaperBroker

    mode = os.getenv("BROKER_MODE", "paper").lower()

    if mode not in ("paper", "live", "kite_live"):
        logger.warning(
            f"[BROKER] Unrecognised BROKER_MODE='{mode}' — defaulting to Alpaca paper trading"
        )
        return AlpacaPaperBroker()

    if mode == "paper":
        return AlpacaPaperBroker()

    # Legacy Kite live mode (for reference, not default)
    if mode == "kite_live":
        api_key = os.getenv("KITE_API_KEY")
        access_token = os.getenv("KITE_ACCESS_TOKEN")
        
        if not access_token:
            try:
                from auth.kite_token_refresh import get_active_token
                access_token = get_active_token()
            except Exception:
                pass

        if not api_key or not access_token:
            logger.critical(
                "[BROKER] Kite live mode requested but credentials missing — "
                "falling back to Alpaca paper trading"
            )
            return AlpacaPaperBroker()

        try:
            from broker.kite_broker import KiteBroker
            return KiteBroker()
        except Exception as e:
            logger.critical(
                f"[BROKER] KiteBroker init failed ({e}) — falling back to Alpaca paper trading"
            )
            return AlpacaPaperBroker()

    # mode == "live" — reserved for future Alpaca live (not implemented)
    logger.warning(
        "[BROKER] Live Alpaca trading not implemented — using paper mode"
    )
    return AlpacaPaperBroker()
