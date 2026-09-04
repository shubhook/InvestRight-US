import uuid
from datetime import datetime, timezone
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

from broker.base import BaseBroker
from cache.redis_client import get_ltp as _redis_get_ltp, set_ltp as _redis_set_ltp
from db.connection import db_cursor
from utils.logger import setup_logger
import os

logger = setup_logger(__name__)

_BROKER_MODE = "alpaca_paper"


class AlpacaPaperBroker(BaseBroker):
    """
    Alpaca Paper Trading broker — simulated trading with Alpaca's paper environment.
    Uses Alpaca Paper Trading API (paper-api.alpaca.markets).
    Orders are placed with Alpaca's paper trading system for realistic simulation.
    """

    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        
        if not self.api_key or not self.secret_key:
            logger.critical(
                "[ALPACA] API credentials (ALPACA_API_KEY, ALPACA_SECRET_KEY) not set. "
                "Paper orders will FAIL. Set credentials to place real Alpaca paper orders."
            )
            self.trading_client = None
            self.data_client = None
        else:
            try:
                self.trading_client = TradingClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                    paper=True  # Always use paper for this broker
                )
                self.data_client = StockHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.secret_key
                )
                logger.info("[ALPACA] Paper trading client initialized (paper-api.alpaca.markets)")
            except Exception as e:
                logger.error(f"[ALPACA] Failed to initialize trading client: {e}")
                self.trading_client = None
                self.data_client = None

    def place_order(self, order_params: dict) -> dict:
        action = order_params.get("action")
        quantity = order_params.get("quantity", 0)
        symbol = order_params.get("symbol", "")
        trade_id = order_params.get("trade_id")
        order_type = order_params.get("order_type", "MARKET")

        if quantity <= 0:
            return self._failed("Quantity must be greater than zero", order_params)

        if action not in ("BUY", "SELL"):
            return self._failed("Invalid action", order_params)

        order_id = str(uuid.uuid4())

        # Require Alpaca credentials for real paper orders
        if not self.trading_client:
            return self._failed(
                "Alpaca API credentials not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY.",
                order_params,
                order_id=order_id
            )

        try:
            # Convert symbol to US format (remove any .NS/.BO suffixes)
            clean_symbol = symbol.split('.')[0].upper()
            
            # Ensure quantity is integer for Alpaca
            quantity = int(quantity)
            if quantity <= 0:
                return self._failed("Quantity must be at least 1 share", order_params, order_id=order_id)
            
            side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
            
            # Place order with Alpaca paper-api
            if order_type == "LIMIT":
                limit_price = order_params.get("price") or order_params.get("entry")
                if not limit_price:
                    return self._failed("Limit order requires a price", order_params, order_id=order_id)
                
                order_request = LimitOrderRequest(
                    symbol=clean_symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=float(limit_price)
                )
            else:
                order_request = MarketOrderRequest(
                    symbol=clean_symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            
            # Submit to Alpaca paper-api.alpaca.markets
            alpaca_order = self.trading_client.submit_order(order_request)
            
            logger.info(
                f"[ALPACA] Order submitted to paper-api: {action} {quantity}x {clean_symbol}, "
                f"alpaca_id={alpaca_order.id}, status={alpaca_order.status}"
            )
            
            # Map Alpaca status to our internal status
            alpaca_status = str(alpaca_order.status).lower()
            if alpaca_status in ["filled", "partially_filled"]:
                status = "FILLED"
            elif alpaca_status in ["rejected", "canceled", "cancelled"]:
                status = "FAILED"
            else:
                status = "PENDING"
            
            filled_qty = int(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0
            
            # Get fill price
            fill_price = None
            if alpaca_order.filled_avg_price:
                fill_price = float(alpaca_order.filled_avg_price)
            elif order_type == "LIMIT" and hasattr(order_request, 'limit_price'):
                fill_price = float(order_request.limit_price)
            
            now = datetime.now(timezone.utc)
            with db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id, trade_id, symbol, action, order_type,
                        quantity, price, status, filled_quantity, filled_price,
                        broker_order_id, broker_mode, placed_at, filled_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, 'alpaca_paper', %s, %s, %s
                    )
                    """,
                    (
                        order_id, trade_id, clean_symbol, action, order_type,
                        quantity, fill_price, status, filled_qty, fill_price,
                        str(alpaca_order.id), now, now if status == "FILLED" else None, now,
                    ),
                )
            
            logger.info(
                f"[ALPACA] Real paper order {status}: {action} {quantity}x {clean_symbol}, "
                f"alpaca_id={alpaca_order.id}, order_id={order_id}"
            )
            
            return {
                "order_id": order_id,
                "broker_order_id": str(alpaca_order.id),
                "status": status,
                "filled_price": fill_price,
                "filled_quantity": filled_qty,
                "failure_reason": None,
            }
            
        except Exception as e:
            logger.error(f"[ALPACA] Failed to place order: {e}")
            return self._failed(f"Alpaca API error: {e}", order_params, order_id=order_id)

    def get_order_status(self, broker_order_id: str) -> dict:
        # Try to fetch live status from Alpaca first
        if self.trading_client:
            try:
                alpaca_order = self.trading_client.get_order_by_id(broker_order_id)
                alpaca_status = str(alpaca_order.status).lower()
                
                if alpaca_status in ["filled", "partially_filled"]:
                    status = "FILLED"
                elif alpaca_status in ["rejected", "canceled", "cancelled"]:
                    status = "CANCELLED"
                else:
                    status = "PENDING"
                
                return {
                    "broker_order_id": broker_order_id,
                    "status": status,
                    "filled_quantity": int(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0,
                    "filled_price": float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
                    "failure_reason": None,
                }
            except Exception as e:
                logger.warning(f"[ALPACA] Live status fetch failed, falling back to DB: {e}")
        
        # Fallback to DB
        try:
            with db_cursor() as cur:
                cur.execute(
                    "SELECT status, filled_quantity, filled_price FROM orders "
                    "WHERE broker_order_id = %s OR order_id = %s",
                    (broker_order_id, broker_order_id),
                )
                row = cur.fetchone()
            
            if row is None:
                return {
                    "broker_order_id": broker_order_id,
                    "status": "FAILED",
                    "filled_quantity": 0,
                    "filled_price": None,
                    "failure_reason": "Order not found",
                }
            
            return {
                "broker_order_id": broker_order_id,
                "status": row[0],
                "filled_quantity": row[1] or 0,
                "filled_price": float(row[2]) if row[2] else None,
                "failure_reason": None,
            }
        except Exception as e:
            logger.error(f"[ALPACA] get_order_status failed: {e}")
            return {
                "broker_order_id": broker_order_id,
                "status": "FAILED",
                "filled_quantity": 0,
                "filled_price": None,
                "failure_reason": str(e),
            }

    def cancel_order(self, broker_order_id: str) -> bool:
        if not self.trading_client:
            logger.error("[ALPACA] Cannot cancel — no trading client initialized")
            return False
        
        try:
            # Cancel via Alpaca API
            self.trading_client.cancel_order_by_id(broker_order_id)
            logger.info(f"[ALPACA] Cancelled order {broker_order_id} via paper-api")
            
            # Update DB
            with db_cursor() as cur:
                cur.execute(
                    "UPDATE orders SET status='CANCELLED', cancelled_at=%s, updated_at=%s "
                    "WHERE broker_order_id=%s OR order_id=%s",
                    (datetime.now(timezone.utc), datetime.now(timezone.utc), 
                     broker_order_id, broker_order_id),
                )
            return True
        except Exception as e:
            logger.error(f"[ALPACA] cancel_order failed: {e}")
            return False

    def get_ltp(self, symbol: str) -> Optional[float]:
        # Remove any exchange suffixes
        clean_symbol = symbol.split('.')[0].upper()
        
        # Check Redis cache first
        cached = _redis_get_ltp(clean_symbol)
        if cached is not None:
            return cached
        
        if self.data_client:
            try:
                request = StockLatestQuoteRequest(symbol_or_symbols=clean_symbol)
                quotes = self.data_client.get_stock_latest_quote(request)
                if clean_symbol in quotes:
                    quote = quotes[clean_symbol]
                    ltp = float(quote.ask_price + quote.bid_price) / 2.0  # Use mid price
                    _redis_set_ltp(clean_symbol, ltp, ttl_seconds=60)
                    return ltp
            except Exception as e:
                logger.warning(f"[ALPACA] Failed to get quote for {clean_symbol}: {e}")
        
        # Fall back to yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(clean_symbol)
            df = ticker.history(period="1d", interval="1m")
            if not df.empty:
                ltp = float(df["Close"].iloc[-1])
                _redis_set_ltp(clean_symbol, ltp, ttl_seconds=60)
                return ltp
        except Exception as e:
            logger.warning(f"[ALPACA] yfinance fallback failed for {clean_symbol}: {e}")
        
        return None

    def get_portfolio(self) -> dict:
        """Fetch paper portfolio from Alpaca."""
        if not self.trading_client:
            return {
                "holdings": [],
                "positions": [],
                "error": None,
                "note": "Alpaca credentials not configured — paper mode with no real positions.",
            }
        
        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()
            
            holdings = []
            for pos in positions:
                holdings.append({
                    "symbol": pos.symbol,
                    "quantity": int(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                })
            
            return {
                "holdings": holdings,
                "positions": holdings,
                "account_value": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "error": None,
            }
        except Exception as e:
            logger.error(f"[ALPACA] get_portfolio failed: {e}")
            return {
                "holdings": [],
                "positions": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _failed(self, reason: str, order_params: dict, order_id: str = None) -> dict:
        oid = order_id or str(uuid.uuid4())
        try:
            with db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id, trade_id, symbol, action, order_type,
                        quantity, broker_mode, status, failure_reason, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'alpaca_paper', 'FAILED', %s, NOW())
                    ON CONFLICT (order_id) DO NOTHING
                    """,
                    (
                        oid,
                        order_params.get("trade_id"),
                        order_params.get("symbol", "").split('.')[0].upper(),
                        order_params.get("action", ""),
                        order_params.get("order_type", "MARKET"),
                        max(order_params.get("quantity", 0), 0),
                        reason,
                    ),
                )
        except Exception as db_err:
            logger.error(f"[ALPACA] Could not persist FAILED order row: {db_err}")
        
        return {
            "order_id": oid,
            "broker_order_id": oid,
            "status": "FAILED",
            "filled_price": None,
            "filled_quantity": 0,
            "failure_reason": reason,
        }
