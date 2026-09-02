# InvestRight — AI Trading System

An end-to-end, multi-agent AI trading system for Indian equities (NSE/BSE).
Combines chart-pattern detection, LLM-assisted sentiment and review, Kelly-fraction position sizing, paper/live broker execution (Kite Connect), full backtesting, and a self-improving feedback loop — all exposed via a REST API and React dashboard.

---

## How it works

```
yfinance / Kite  →  Data Agent  →  Analysis Agent  →  Pattern Engine
                                                             ↓
                                                      Decision Agent
                                                             ↓
                                                       Risk Engine (Kelly sizing)
                                                             ↓
                                               LLM Review Agent (claude-sonnet)
                                                             ↓
                                                      Action Agent  →  Broker
                                                             ↓
                                              Position Manager  ←→  PostgreSQL
                                                             ↓
                                                     Feedback Agent  →  Weights
```

Every pipeline step is traced, audited, and observable via `/observability/*` endpoints.

---

## Architecture at a glance

| Layer | Components |
|-------|-----------|
| **Data** | `data_agent` — yfinance OHLCV + Google Finance RSS news |
| **Analysis** | Trend (SMA), Support/Resistance, ATR volatility, LLM sentiment |
| **Signals** | Double Top, Ascending Triangle, Head & Shoulders, RSI, MACD crossover |
| **Decisions** | Weighted logistic model — trainable via gradient ascent |
| **Risk** | Kelly-fraction sizing, hard 10% loss cap, per-symbol capital limits |
| **Execution** | Paper broker (default) or Kite Connect (live) |
| **Portfolio** | Real-time P&L, capital accounting, exit monitoring |
| **Backtesting** | Single-run and walk-forward validation — fully async |
| **LLM** | Sentiment (haiku), Pre-trade review (sonnet), Explanation (haiku), Portfolio summary (sonnet) |
| **Observability** | Trace IDs, audit log, per-component latency metrics |
| **Safety** | Kill switch, idempotency, rate limiting, JWT auth |

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.9+ | |
| PostgreSQL | 14+ | Required — all state lives here |
| Redis | 6+ | Required for LTP cache and rate limiting |
| Anthropic API key | — | Optional — LLM features fail-open without it |
| Kite Connect key | — | Optional — only needed for live broker mode |

---

## Quick start (local)

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/shubhook/InvestRight.git
cd InvestRight/project
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Set up PostgreSQL and Redis

```bash
# macOS (Homebrew)
brew install postgresql@14 redis
brew services start postgresql@14
brew services start redis

# Ubuntu
sudo apt install postgresql redis-server
sudo systemctl start postgresql redis
```

Create the database:

```bash
psql -U postgres -c "CREATE DATABASE investright;"
```

### 3. Configure environment variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

**Required variables:**

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/investright
REDIS_URL=redis://localhost:6379/0

JWT_SECRET=change-this-to-a-long-random-string
API_KEY=your-api-key-for-the-rest-api

TOTAL_CAPITAL=100000          # Your trading capital in INR
BROKER_MODE=paper             # paper | live
```

**Optional variables:**

```env
# LLM (fails open if not set — LLM features are skipped gracefully)
ANTHROPIC_API_KEY=sk-ant-...

# Live broker (only needed when BROKER_MODE=live)
KITE_API_KEY=...
KITE_ACCESS_TOKEN=...
KITE_PRODUCT=MIS              # MIS | CNC

# Backtest
BACKTEST_DEFAULT_CAPITAL=100000

# Tunable indicator parameters (all have defaults)
ATR_PERIOD=14
SMA_FAST=20
SMA_SLOW=50
RSI_PERIOD=14
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
MAX_KELLY_FRACTION=0.50
MAX_LOSS_HARD_CAP=0.10

# Flask
FLASK_DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### 4. Initialise the database

```bash
cd backend
python db/init_db.py
```

### 5. Start everything

**Option A — one command:**

```bash
./run.sh           # starts backend (5001) + frontend (8080)
```

**Option B — separately:**

```bash
# Terminal 1 — Backend API
cd backend
python main.py

# Terminal 2 — Frontend (React SPA)
cd frontend
python -m http.server 8080
```

**Option C — Docker:**

```bash
docker-compose up --build
```

---

## Docker

```bash
docker-compose up --build
```

Services started:
- `backend` → http://localhost:5001
- `frontend` → http://localhost:8080
- `postgres` → localhost:5432
- `redis` → localhost:6379

---

## API reference

All protected endpoints require a JWT in the `Authorization: Bearer <token>` header.

### Authentication

```bash
# Get a JWT
POST /token
{ "api_key": "your-api-key" }
```

### Core pipeline

```bash
# Run full analysis + execution for a symbol
GET /analyze?symbol=RELIANCE.NS
Authorization: Bearer <token>
```

**Example response:**

```json
{
  "symbol": "RELIANCE.NS",
  "decision": "BUY",
  "confidence": 0.76,
  "probability_up": 0.64,
  "risk": {
    "entry": 2847.50,
    "stop_loss": 2790.00,
    "target": 2962.50,
    "rr_ratio": 2.0,
    "max_loss_pct": 2.02,
    "position_size_fraction": 0.18
  },
  "pattern_detected": {
    "pattern": "ascending_triangle",
    "confidence": 0.81,
    "direction": "bullish"
  },
  "execution": {
    "executed": true,
    "trade_id": "550e8400-...",
    "filled_price": 2848.00,
    "filled_quantity": 6
  }
}
```

### Portfolio

```bash
GET  /portfolio                              # Full summary
GET  /portfolio/positions                    # Open positions
GET  /portfolio/positions/<id>               # Single position P&L
POST /portfolio/positions/<id>/close         # Manual close
GET  /portfolio/pnl                          # P&L breakdown
GET  /portfolio/pnl/daily                    # Today's P&L
GET  /portfolio/summary                      # LLM narrative summary
GET  /portfolio/daily-brief                  # LLM daily brief
```

### Orders

```bash
GET  /orders                                 # All orders
GET  /orders/<order_id>                      # Single order
POST /orders/<order_id>/cancel               # Cancel
```

### Backtesting

```bash
# Launch async backtest (returns run_id immediately)
POST /backtest/run
{
  "symbol": "RELIANCE.NS",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "interval": "1d",
  "initial_capital": 100000
}

# Launch async walk-forward validation
POST /backtest/walk-forward
{
  "symbol": "RELIANCE.NS",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "n_splits": 5
}

# Poll for results
GET  /backtest/runs/<run_id>
GET  /backtest/runs/<run_id>/trades
GET  /backtest/runs/<run_id>/equity-curve
GET  /backtest/runs                          # List all runs
POST /backtest/compare                       # Compare multiple runs
```

### Observability

```bash
GET /observability/trace/<trace_id>          # Full event sequence for a pipeline run
GET /observability/metrics?minutes=60        # Per-component latency stats
GET /observability/audit                     # Structured audit log
```

### Safety controls

```bash
POST /halt      { "reason": "...", "activated_by": "..." }
POST /resume
GET  /health
POST /update-weights                         # Trigger gradient-ascent weight update
GET  /broker/status
```

---

## Scheduler

The scheduler runs automated jobs against configured symbols:

```bash
cd backend
python scheduler.py
```

| Job | Frequency | Notes |
|-----|-----------|-------|
| Model degradation check | Every 15 min | Auto-activates kill switch if accuracy drops |
| Exit monitor | Every 15 min | Checks stop loss / target hits on all open positions |
| Analysis pipeline | Every 15 min | Skipped outside NSE/BSE hours (09:15–15:30 IST, Mon–Fri) |
| Pending trade evaluation | Every 15 min | Resolves trades missed by exit monitor |
| Daily P&L snapshot | 15:30 IST | |
| Log retention | 02:00 IST | Cleans ephemeral audit/metric rows |
| DB cleanup | 03:00 IST | VACUUM ANALYZE + stale run reset |

To configure watched symbols, add `SYMBOLS` to `backend/config.py`:

```python
class Config:
    SYMBOLS = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
```

---

## Project structure

```
InvestRight/project/
├── backend/
│   ├── agents/                  # Pipeline agents
│   │   ├── data_agent.py        # OHLCV + news fetcher
│   │   ├── analysis_agent.py    # Trend, S/R, ATR, sentiment
│   │   ├── decision_agent.py    # Weighted signal → BUY/SELL/WAIT
│   │   ├── action_agent.py      # Idempotency, order placement, fill handling
│   │   └── feedback_agent.py    # Outcome evaluation
│   │
│   ├── llm/                     # Anthropic LLM agents (all fail-open)
│   │   ├── llm_client.py        # Shared Anthropic client + retry
│   │   ├── sentiment_agent.py   # Headline sentiment (haiku)
│   │   ├── review_agent.py      # Pre-trade safety review (sonnet)
│   │   ├── explanation_agent.py # Human-readable trade explanation (haiku)
│   │   └── summary_agent.py     # Portfolio narrative (sonnet)
│   │
│   ├── broker/                  # Execution layer
│   │   ├── paper_broker.py      # Simulated fills at LTP
│   │   ├── kite_broker.py       # Zerodha Kite Connect (live)
│   │   ├── order_manager.py     # Retry logic, status polling, fill handling
│   │   └── broker_factory.py    # BROKER_MODE env var routing
│   │
│   ├── portfolio/               # Position and capital tracking
│   │   ├── position_manager.py  # Open/close positions, P&L
│   │   ├── capital_account.py   # Deploy/release capital
│   │   ├── pnl_calculator.py    # Realised/unrealised P&L, snapshots
│   │   └── exit_monitor.py      # Stop loss / target monitoring
│   │
│   ├── backtest/                # Historical simulation
│   │   ├── backtest_engine.py   # Bar-by-bar simulation (reuses live pipeline)
│   │   ├── walk_forward.py      # K-fold walk-forward validation
│   │   ├── data_loader.py       # Historical OHLCV loading
│   │   ├── performance.py       # Metrics: Sharpe, drawdown, win rate
│   │   └── report_generator.py  # DB-backed report queries
│   │
│   ├── memory/                  # Model state
│   │   ├── memory_store.py      # Trade CRUD (PostgreSQL)
│   │   ├── memory_reader.py     # Pattern success rates
│   │   └── weights_store.py     # Gradient-ascent weight updates
│   │
│   ├── safety/                  # Guard rails
│   │   ├── kill_switch.py       # Emergency halt / resume
│   │   ├── capital_limits.py    # Per-symbol exposure tracking
│   │   └── idempotency.py       # 15-min duplicate signal guard
│   │
│   ├── observability/           # Tracing and metrics
│   │   ├── trace.py             # TraceContext, span IDs
│   │   ├── audit_log.py         # Structured pipeline event log
│   │   └── metrics.py           # Per-component latency tracking
│   │
│   ├── utils/
│   │   ├── risk_engine.py       # Kelly sizing, stop loss, capital check
│   │   ├── pattern_engine.py    # Chart pattern + RSI/MACD detection
│   │   ├── market_hours.py      # NSE/BSE trading hours guard
│   │   ├── logger.py            # Structured logger + audit bridge
│   │   └── rate_limiter.py      # Per-IP sliding window rate limiting
│   │
│   ├── auth/
│   │   ├── jwt_handler.py       # Token generation and validation
│   │   ├── middleware.py        # @require_auth decorator
│   │   └── kite_token_refresh.py# Kite access token management
│   │
│   ├── cache/
│   │   └── redis_client.py      # Shared Redis pool (OHLCV + LTP cache)
│   │
│   ├── db/
│   │   ├── connection.py        # psycopg2 connection pool
│   │   └── init_db.py           # Schema initialisation
│   │
│   ├── services/
│   │   ├── stock_service.py     # yfinance wrapper
│   │   └── news_service.py      # RSS news fetcher
│   │
│   ├── feedback/
│   │   └── model_monitor.py     # Accuracy / Brier score tracking
│   │
│   ├── maintenance/
│   │   ├── log_retention.py     # Scheduled log pruning
│   │   └── db_cleanup.py        # VACUUM + stale run cleanup
│   │
│   ├── config.py                # All env vars + tunable parameters
│   ├── main.py                  # Flask app + programmatic run()
│   ├── scheduler.py             # Automated job runner
│   └── requirements.txt
│
├── database/
│   └── schema.sql               # Idempotent schema (safe to run multiple times)
│
├── frontend/
│   ├── index.html               # React SPA entry point
│   └── app.js                   # Dashboard: signals, portfolio, backtests
│
├── docker-compose.yml
├── Dockerfile.backend
├── run.sh                       # Local dev startup script
└── .env.example
```

---

## Signals and decision logic

### Patterns detected

| Pattern | Direction | Method |
|---------|-----------|--------|
| Double Top | Bearish | Two peaks within ±2%, valley ≥ 3% below |
| Head & Shoulders | Bearish | Three peaks, middle highest, shoulders within 5% symmetry |
| Ascending Triangle | Bullish | Flat resistance + rising support trendline |
| RSI Oversold (<30) | Bullish | Confidence scales from threshold outward |
| RSI Overbought (>70) | Bearish | Confidence scales from threshold outward |
| MACD Bullish Crossover | Bullish | MACD crosses above signal in last 3 candles |
| MACD Bearish Crossover | Bearish | MACD crosses below signal in last 3 candles |

### Position sizing

Positions are sized using the **Kelly criterion** (binary bet form):

```
K = P(win) − P(loss) / RR_ratio
position_size = min(K, MAX_KELLY_FRACTION)
```

A negative Kelly fraction (negative EV) rejects the trade outright.
`MAX_KELLY_FRACTION` defaults to 0.50 and is overridable via env var.

### Risk rules

- Hard cap: reject if stop-loss implies > `MAX_LOSS_HARD_CAP` (default 10%) loss
- Capital limit: per-symbol exposure tracked in `capital_limits` table
- 2:1 minimum reward-to-risk enforced by `risk_engine`

---

## Model learning

The decision model uses a weighted logistic function over 7 features: bias, trend, sentiment, pattern direction × confidence, volatility, support/resistance signal, volume signal.

Weights are updated via gradient ascent on completed trades:

```bash
POST /update-weights
{ "learning_rate": 0.01 }
```

Validation uses an 80/20 temporal split — the update is rejected if held-out accuracy drops by more than 5 percentage points.

---

## Broker modes

| Mode | Description | Config |
|------|-------------|--------|
| `paper` | Fills immediately at LTP via yfinance | `BROKER_MODE=paper` (default) |
| `live` | Real orders via Zerodha Kite Connect | `BROKER_MODE=live` + Kite credentials |

To switch to live trading, set `BROKER_MODE=live` and store a valid Kite access token:

```bash
POST /broker/kite/token
{ "access_token": "...", "request_token": "..." }
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `EnvironmentError: Required environment variables not set` | Copy `.env.example` to `.env` and set `JWT_SECRET`, `API_KEY`, `TOTAL_CAPITAL` |
| `could not connect to server` (PostgreSQL) | Ensure PostgreSQL is running: `brew services start postgresql@14` |
| `ConnectionRefusedError` (Redis) | Ensure Redis is running: `brew services start redis` |
| `ModuleNotFoundError` | Activate venv: `source .venv/bin/activate`, then `pip install -r backend/requirements.txt` |
| Port 5001 in use | `lsof -ti:5001 \| xargs kill -9` |
| Port 8080 in use | `lsof -ti:8080 \| xargs kill -9` |
| `decision: WAIT` always | Normal outside market hours (09:15–15:30 IST, Mon–Fri). Use `/analyze` endpoint directly to force analysis at any time. |
| Kill switch active | `POST /resume` with a valid JWT to re-enable trading |
| LLM features not working | Set `ANTHROPIC_API_KEY` in `.env` — all LLM agents fail-open (system works without it) |

---

## License

MIT
