import os
from broker.base import BaseBroker
from utils.logger import setup_logger

logger = setup_logger(__name__)


def get_broker() -> BaseBroker:
    """
    Return AlpacaPaperBroker for US paper trading.
    
    This system only supports Alpaca paper trading.
    Any BROKER_MODE value returns AlpacaPaperBroker.
    """
    from broker.alpaca_paper_broker import AlpacaPaperBroker

    mode = os.getenv("BROKER_MODE", "paper").lower()

    if mode != "paper":
        logger.warning(
            f"[BROKER] BROKER_MODE='{mode}' not supported — using Alpaca paper trading"
        )

    return AlpacaPaperBroker()
