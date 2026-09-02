# InvestRight-US — US Paper Trading System

**US adaptation of [InvestRight](https://github.com/shubhook/InvestRight) for Alpaca Paper Trading.**

This repository is a private adaptation for **US equities paper trading only**. The original InvestRight system is designed for NSE/BSE (India) markets using Zerodha Kite. **Do NOT push NSE/Kite work here or US work back to the original repo.**

---

## 🚨 Important Notes

- **Paper Trading Only**: This system uses Alpaca's paper trading API. No real money is involved.
- **US Markets**: Trades US stocks during NYSE hours (09:30–16:00 ET). Not for NSE/BSE.
- **Alpaca Required**: Get free paper trading keys at [alpaca.markets](https://alpaca.markets/)
- **Original InvestRight**: For India NSE/BSE trading, see [shubhook/InvestRight](https://github.com/shubhook/InvestRight)

---

## How it works

```
yfinance / Alpaca  →  Data Agent  →  Analysis Agent  →  Pattern Engine
                                                             ↓
                                                      Decision Agent
                                                             ↓
                                                       Risk Engine (Kelly sizing)
                                                             ↓
                                               LLM Review Agent (Groq)
                                                             ↓
                                                      Action Agent  →  Alpaca Paper Broker
                                                             ↓
                                              Position Manager  ←→  PostgreSQL
                                                             ↓
                                                     Feedback Agent  →  Weights
```

Every pipeline step is traced, audited, and observable via `/observability/*` endpoints.

---

## Key Differences from Original InvestRight

| Aspect | Original (India) | This Repo (US) |
|--------|------------------|----------------|
| **Exchange** | NSE/BSE | NYSE/NASDAQ |
| **Broker** | Zerodha Kite (paper/live) | Alpaca Paper only |
| **Market Hours** | 09:15–15:30 IST | 09:30–16:00 ET |
| **Currency** | INR (₹) | USD ($) |
| **Symbols** | RELIANCE.NS, TCS.BO | AAPL, MSFT, TSLA |
| **Live Trading** | Supported via Kite | Not in v1 (paper only) |

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.9+ | |
| PostgreSQL | 14+ | Required — all state lives here |
| Redis | 6+ | Required for LTP cache and rate limiting |
| Alpaca Paper API Keys | — | Free at [alpaca.markets](https://alpaca.markets/) |
| Groq API Key | — | Optional — for LLM sentiment/review |

---

## Quick Start (Local)

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/shubhook/InvestRight-US.git
cd InvestRight-US
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

TOTAL_CAPITAL=100000          # Your paper trading capital in USD
BROKER_MODE=paper             # Always paper for this repo
```

**Alpaca Paper Trading (required for real paper orders):**

1. Sign up at [alpaca.markets](https://alpaca.markets/)
2. Navigate to Paper Trading dashboard
3. Generate API keys
4. Add to `.env`:

```env
ALPACA_API_KEY=your-alpaca-paper-api-key-here
ALPACA_SECRET_KEY=your-alpaca-paper-secret-key-here
ALPACA_PAPER=true
```

**Optional variables:**

```env
# LLM (Groq for sentiment — free tier available)
GROQ_API_KEY=your-groq-api-key

# Tunable indicator parameters (all have defaults)
ATR_PERIOD=14
SMA_FAST=20
SMA_SLOW=50
RSI_PERIOD=14
MAX_KELLY_FRACTION=0.50
MAX_LOSS_HARD_CAP=0.10
```

### 4. Initialize the database

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

## Testing Without Alpaca Credentials

The system will run without Alpaca keys, but orders will only be logged to the database (not sent to Alpaca's paper environment). For realistic simulation:

1. Get free Alpaca paper keys: [alpaca.markets](https://alpaca.markets/)
2. Add to `.env` as shown above
3. Restart backend

---

## US Trading Notes

### Symbols
- Use plain US tickers: `AAPL`, `MSFT`, `TSLA`
- No exchange suffix needed (no `.NS` or `.BO`)
- Remove any suffixes if importing watchlists

### Market Hours
- NYSE: 09:30–16:00 ET (Monday–Friday)
- Scheduler skips analysis outside market hours
- Holidays: NYSE calendar (see `backend/utils/market_hours.py`)

### Currency
- All amounts in USD ($)
- Dashboard displays `$` instead of `₹`
- TOTAL_CAPITAL is in dollars, not rupees

---

## API Reference

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
GET /analyze?symbol=AAPL
Authorization: Bearer <token>
```

**Example response:**

```json
{
  "symbol": "AAPL",
  "decision": "BUY",
  "confidence": 0.76,
  "probability_up": 0.64,
  "risk": {
    "entry": 185.50,
    "stop_loss": 182.00,
    "target": 191.50,
    "rr_ratio": 2.0,
    "max_loss_pct": 1.89,
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
    "filled_price": 185.75,
    "filled_quantity": 10
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
GET  /portfolio/summary                      # LLM narrative summary
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
  "symbol": "AAPL",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "interval": "1d",
  "initial_capital": 100000
}

# Poll for results
GET  /backtest/runs/<run_id>
GET  /backtest/runs/<run_id>/trades
GET  /backtest/runs/<run_id>/equity-curve
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
| Analysis pipeline | Every 15 min | Skipped outside NYSE hours (09:30–16:00 ET, Mon–Fri) |
| Pending trade evaluation | Every 15 min | Resolves trades missed by exit monitor |
| Daily P&L snapshot | 16:00 ET | End of market day |
| Log retention | 02:00 ET | Cleans ephemeral audit/metric rows |
| DB cleanup | 03:00 ET | VACUUM ANALYZE + stale run reset |

To configure watched symbols, add `SYMBOLS` to `backend/config.py`:

```python
class Config:
    SYMBOLS = ['AAPL', 'MSFT', 'TSLA', 'GOOGL']
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
| `decision: WAIT` always | Normal outside market hours (09:30–16:00 ET, Mon–Fri). Use `/analyze` endpoint directly to force analysis at any time. |
| Kill switch active | `POST /resume` with a valid JWT to re-enable trading |
| Orders not sent to Alpaca | Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` to `.env` and restart backend |
| Symbol format errors | Use plain US tickers (AAPL, not AAPL.NS) |

---

## Architecture

| Layer | Components |
|-------|-----------|
| **Data** | `data_agent` — yfinance OHLCV + RSS news |
| **Analysis** | Trend (SMA), Support/Resistance, ATR volatility, LLM sentiment |
| **Signals** | Double Top, Ascending Triangle, Head & Shoulders, RSI, MACD crossover |
| **Decisions** | Weighted logistic model — trainable via gradient ascent |
| **Risk** | Kelly-fraction sizing, hard 10% loss cap, per-symbol capital limits |
| **Execution** | **Alpaca Paper Broker** (paper trading only) |
| **Portfolio** | Real-time P&L, capital accounting, exit monitoring |
| **Backtesting** | Single-run and walk-forward validation — fully async |
| **LLM** | Groq (haiku/sonnet alternatives) for sentiment and review |
| **Observability** | Trace IDs, audit log, per-component latency metrics |
| **Safety** | Kill switch, idempotency, rate limiting, JWT auth |

---

## Out of Scope (v1)

- ❌ Live Alpaca trading (paper only)
- ❌ Options, shorts, crypto
- ❌ EU markets, SIP paid data
- ❌ NSE/BSE support (use [original InvestRight](https://github.com/shubhook/InvestRight))
- ❌ Fractional shares (integer shares only)
- ❌ PDT $25k logic (FINRA removed it; paper is not a margin account)

---

## License

MIT (same as original InvestRight)

---

## Credits

Original InvestRight by [Shubham Khakha](https://github.com/shubhook)  
US adaptation: InvestRight-US (this repo)
