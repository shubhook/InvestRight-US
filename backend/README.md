# InvestRight — Backend

Flask REST API and automated scheduler for the InvestRight AI trading system.

For full setup instructions, see the [root README](../README.md).

---

## Pipeline overview

```
data_agent → analysis_agent → pattern_engine → decision_agent
                                                      ↓
                                               risk_engine  (Kelly sizing)
                                                      ↓
                                             review_agent  (LLM, fail-open)
                                                      ↓
                                              action_agent  → broker
                                                      ↓
                                            position_manager → PostgreSQL
                                                      ↓
                                             feedback_agent → weights_store
```

---

## Module reference

### `agents/`

| File | Responsibility |
|------|---------------|
| `data_agent.py` | Fetches OHLCV data (yfinance) and news headlines (RSS). Packages into a `data` dict for the pipeline. |
| `analysis_agent.py` | Computes trend (SMA), support/resistance levels, ATR volatility, and sentiment. Accepts `skip_llm_sentiment=True` for backtests. |
| `decision_agent.py` | Runs the weighted logistic model over 7 features. Loads weights from DB; falls back to defaults. |
| `action_agent.py` | Idempotency check → store trade → LLM review → quantity calc → broker order → fill poll → open position. |
| `feedback_agent.py` | `evaluate()`: price-vs-SL/target check. `record_outcome()`: exit-event-driven outcome recording. |

### `llm/`

All LLM agents are **fail-open** — the pipeline continues with a safe default if the API is unavailable or the key is not set.

| File | Model | Purpose |
|------|-------|---------|
| `llm_client.py` | — | Shared Anthropic client. Handles retries, token counting, and prompt truncation. |
| `sentiment_agent.py` | `claude-haiku-4-5-20251001` | Classifies news headlines as positive/negative/neutral with confidence score. |
| `review_agent.py` | `claude-sonnet-4-6` | Pre-trade safety review. Blocks trades with logically inconsistent parameters. |
| `explanation_agent.py` | `claude-haiku-4-5-20251001` | Generates a human-readable explanation for BUY/SELL decisions. |
| `summary_agent.py` | `claude-sonnet-4-6` | Generates portfolio narrative and daily brief on demand. |

### `broker/`

| File | Responsibility |
|------|---------------|
| `base.py` | Abstract base class defining the broker interface. |
| `paper_broker.py` | Fills orders immediately at LTP. Uses shared Redis pool for LTP caching. |
| `kite_broker.py` | Live Zerodha Kite Connect execution. Handles token expiry by activating kill switch. |
| `order_manager.py` | `submit_order()` with 3-attempt exponential backoff. `poll_order_status()` for fill confirmation. |
| `broker_factory.py` | Returns the correct broker based on `BROKER_MODE` env var. |

### `portfolio/`

| File | Responsibility |
|------|---------------|
| `position_manager.py` | `open_position()` — deploys capital and inserts position row atomically. `close_position()` — calculates P&L, releases capital, resets exposure. |
| `capital_account.py` | Single source of truth for deployed/available capital. `deploy_capital()` and `release_capital()`. |
| `pnl_calculator.py` | Portfolio summary, per-position P&L, daily P&L, and daily snapshot. |
| `exit_monitor.py` | Polls all open positions, fetches LTP, closes at stop loss or target. |

### `backtest/`

| File | Responsibility |
|------|---------------|
| `backtest_engine.py` | Bar-by-bar simulation reusing the exact live pipeline. Writes only to `backtest_*` tables. LLM sentiment is skipped (`skip_llm_sentiment=True`). |
| `walk_forward.py` | K-fold walk-forward validation. Each fold trains on earlier data, tests on later. |
| `data_loader.py` | Historical OHLCV download via yfinance with Redis caching. |
| `performance.py` | Computes Sharpe ratio, max drawdown, win rate, profit factor, expectancy. |
| `report_generator.py` | Queries `backtest_*` tables for run summaries, trade breakdowns, and equity curves. |

### `memory/`

| File | Responsibility |
|------|---------------|
| `memory_store.py` | `store_trade()`, `get_trade()`, `update_trade_result()`, `get_all_trades()` — all PostgreSQL backed. |
| `memory_reader.py` | `get_failure_patterns()`, `get_success_rate()` — pattern-level win/loss aggregations via SQL. |
| `weights_store.py` | `update_weights_from_trades()` — gradient ascent on completed trades with 80/20 temporal train/val split. |

### `safety/`

| File | Responsibility |
|------|---------------|
| `kill_switch.py` | `is_trading_halted()`, `activate_kill_switch()`, `deactivate_kill_switch()`. State persisted in `kill_switch` DB table. |
| `capital_limits.py` | `check_limit()` — ensures per-symbol exposure stays under `max_capital_pct`. `update_exposure()` / `reset_exposure()`. |
| `idempotency.py` | 15-minute duplicate-signal window. `generate_key()`, `is_duplicate()`, `record_key()`. |

### `observability/`

| File | Responsibility |
|------|---------------|
| `trace.py` | `TraceContext` — holds `trace_id` and `symbol` for a pipeline run. `elapsed_ms()` helper. |
| `audit_log.py` | `log_event()` — writes structured events to `audit_log` table. Named event type constants. |
| `metrics.py` | Per-component latency tracking. In-memory accumulation flushed to `pipeline_metrics` every 5 min. |

### `utils/`

| File | Responsibility |
|------|---------------|
| `risk_engine.py` | `apply_risk()` — computes stop loss, target, Kelly fraction, checks capital limits. |
| `pattern_engine.py` | `detect_pattern()` — runs geometric + momentum detectors, returns highest-confidence match. |
| `market_hours.py` | `is_market_open()` — NSE/BSE hours guard (09:15–15:30 IST, Mon–Fri). |
| `logger.py` | `setup_logger()` — stdout handler + audit log bridge (`WARNING+` only, with recursion guard). |
| `rate_limiter.py` | Sliding-window rate limiting backed by Redis. Per-IP per-endpoint. |

### `auth/`

| File | Responsibility |
|------|---------------|
| `jwt_handler.py` | `generate_token()`, `verify_token()` — HS256 JWT with configurable expiry. |
| `middleware.py` | `@require_auth` decorator — validates `Authorization: Bearer <token>` header. |
| `kite_token_refresh.py` | Stores and retrieves Kite access tokens from DB. `is_token_valid()`, `get_token_expiry()`. |

### `cache/`

| File | Responsibility |
|------|---------------|
| `redis_client.py` | Shared connection pool. `get_ohlcv()` / `set_ohlcv()` (15-min TTL). `get_ltp()` / `set_ltp()` (60-sec TTL). |

### `db/`

| File | Responsibility |
|------|---------------|
| `connection.py` | `db_cursor()` context manager using a psycopg2 connection pool. |
| `init_db.py` | Runs `database/schema.sql` — safe to execute multiple times (`CREATE TABLE IF NOT EXISTS` throughout, no destructive DROP statements). |

### `services/`

| File | Responsibility |
|------|---------------|
| `stock_service.py` | yfinance wrapper. `get_ohlcv()` with Redis caching layer. |
| `news_service.py` | Google Finance RSS fetcher. Returns list of headline strings. |

### `feedback/`

| File | Responsibility |
|------|---------------|
| `model_monitor.py` | `compute_accuracy_window()` — accuracy and Brier score over a rolling window. `record_prediction()` / `record_outcome()`. |

### `maintenance/`

| File | Responsibility |
|------|---------------|
| `log_retention.py` | Deletes rows older than retention thresholds from `audit_log`, `pipeline_metrics`, `llm_calls`, `rate_limit_log`. |
| `db_cleanup.py` | `VACUUM ANALYZE` on key tables. Resets stuck `running` backtest runs. Purges expired idempotency keys. |

---

## Configuration

All parameters are in `config.py` and overridable via environment variables.

### Required at startup

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | Secret for JWT signing |
| `API_KEY` | Secret for the `/token` endpoint |
| `TOTAL_CAPITAL` | Total trading capital in INR |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `BROKER_MODE` | `paper` | `paper` or `live` |
| `ANTHROPIC_API_KEY` | — | LLM features fail-open without it |
| `KITE_API_KEY` | — | Required for live mode |
| `KITE_ACCESS_TOKEN` | — | Required for live mode |
| `BACKTEST_DEFAULT_CAPITAL` | `100000` | Default capital for backtests |
| `ATR_PERIOD` | `14` | ATR lookback period |
| `SMA_FAST` | `20` | Fast SMA window |
| `SMA_SLOW` | `50` | Slow SMA window |
| `RSI_PERIOD` | `14` | RSI period |
| `MACD_FAST` | `12` | MACD fast EMA |
| `MACD_SLOW` | `26` | MACD slow EMA |
| `MACD_SIGNAL` | `9` | MACD signal EMA |
| `PATTERN_CONFIDENCE_FLOOR` | `0.5` | Minimum confidence to report a pattern |
| `MAX_KELLY_FRACTION` | `0.50` | Kelly fraction cap |
| `MAX_LOSS_HARD_CAP` | `0.10` | Max stop-loss distance as fraction of entry |
| `SR_WINDOW` | `10` | Support/resistance rolling window |
| `MIN_CANDLES` | `30` | Minimum bars required for pattern detection |

---

## Database tables

| Table | Purpose |
|-------|---------|
| `trades` | All trade decisions (pending / correct / wrong) |
| `positions` | Open and closed positions |
| `orders` | Order state machine (PENDING → FILLED / CANCELLED / FAILED) |
| `capital_account` | Single source of truth for deployed/available capital |
| `capital_limits` | Per-symbol exposure tracking |
| `weights` | Append-only model weight history |
| `signals` | Archived analysis signals |
| `kill_switch` | Kill switch activation state |
| `idempotency_log` | 15-minute duplicate-signal keys |
| `pnl_snapshots` | Daily portfolio valuation history |
| `backtest_runs` | Backtest run metadata and metrics |
| `backtest_trades` | Per-bar trades from backtest |
| `backtest_equity_curve` | Bar-by-bar equity for backtest |
| `audit_log` | Structured pipeline event trace |
| `pipeline_metrics` | Per-component latency |
| `model_performance` | Accuracy / Brier score windows |
| `llm_calls` | Anthropic API call log |
| `rate_limit_log` | Per-IP request counts |
| `kite_tokens` | Kite access token storage |

---

## Extending the system

### Add a new chart pattern

1. Add a `_detect_<name>()` function in `utils/pattern_engine.py` following the existing signature:
   ```python
   def _detect_<name>(close, high, low, volume) -> dict:
       # returns {"pattern": str, "confidence": float, "direction": str}
   ```
2. Register it in `detect_pattern()` under the geometric or momentum candidates block.

### Add a new analysis signal

1. Add the computation to `analyze_data()` in `agents/analysis_agent.py`.
2. Include it in the returned dict.
3. Add the corresponding feature to `decision_agent.py`'s feature vector and `weights_store.py`'s weight keys.

### Add a new broker

1. Subclass `broker/base.py`'s `BaseBroker`.
2. Implement `place_order()`, `get_order_status()`, `cancel_order()`, `get_ltp()`.
3. Register it in `broker/broker_factory.py`.

### Adjust risk rules

Override via environment variables (no code changes needed for standard parameters).
For structural changes, edit `utils/risk_engine.py`'s `apply_risk()`.
