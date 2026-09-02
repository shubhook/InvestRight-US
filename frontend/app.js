// InvestRight Dashboard — React 18 SPA (CDN, no build step)
// All JSX is transpiled in-browser by Babel standalone.

const { useState, useEffect, useRef, useCallback } = React;

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_BASE = 'http://localhost:5001';

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------
function getToken() { return localStorage.getItem('ir_token'); }
function setToken(t) { localStorage.setItem('ir_token', t); }
function clearToken() { localStorage.removeItem('ir_token'); }

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  if (res.status === 401) { clearToken(); window.location.reload(); throw new Error('Session expired'); }
  return res;
}

// ---------------------------------------------------------------------------
// LoginScreen
// ---------------------------------------------------------------------------
function LoginScreen({ onLogin }) {
  const [apiKey, setApiKey] = useState('');
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res  = await fetch(`${API_BASE}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.message || 'Login failed'); return; }
      setToken(data.token);
      onLogin();
    } catch (err) {
      setError('Network error — is the backend running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-sm shadow-2xl">
        <h1 className="text-2xl font-bold text-center mb-2 text-brand">InvestRight-US</h1>
        <p className="text-gray-400 text-sm text-center mb-6">US Paper Trading Dashboard (Alpaca)</p>
        <form onSubmit={handleLogin} className="space-y-4">
          <input
            type="password"
            placeholder="API Key"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-brand"
          />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading || !apiKey}
            className="w-full bg-brand hover:bg-brand-dark disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NavBar with Session Clock
// ---------------------------------------------------------------------------
const TABS = ['Overview', 'Trade Setup', 'Market Sentiment', 'Portfolio', 'Trades', 'Backtest', 'Observability', 'Settings'];

function SessionClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Convert to ET and IST
  const etTime = time.toLocaleTimeString('en-US', { 
    timeZone: 'America/New_York', 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
  
  const istTime = time.toLocaleTimeString('en-US', { 
    timeZone: 'Asia/Kolkata', 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false
  });

  // Determine market status (rough client-side check)
  const etHour = parseInt(time.toLocaleTimeString('en-US', { 
    timeZone: 'America/New_York', 
    hour: '2-digit',
    hour12: false
  }));
  const etMinute = parseInt(time.toLocaleTimeString('en-US', { 
    timeZone: 'America/New_York', 
    minute: '2-digit'
  }));
  const etDay = time.toLocaleDateString('en-US', { timeZone: 'America/New_York', weekday: 'short' });
  
  const isWeekday = !['Sat', 'Sun'].includes(etDay);
  const inSessionHours = (etHour === 9 && etMinute >= 30) || (etHour > 9 && etHour < 16) || (etHour === 16 && etMinute === 0);
  const marketOpen = isWeekday && inSessionHours;

  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${marketOpen ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
        <div>
          <div className="text-white font-medium">ET {etTime}</div>
          <div className="text-gray-500">{marketOpen ? 'NYSE Open' : 'NYSE Closed'} · IST {istTime}</div>
        </div>
      </div>
    </div>
  );
}

function NavBar({ activeTab, setActiveTab, killActive, onLogout }) {
  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-4 py-2 flex items-center gap-4 flex-wrap">
      <span className="font-bold text-brand mr-2 text-lg">InvestRight-US</span>
      {TABS.map(t => (
        <button
          key={t}
          onClick={() => setActiveTab(t)}
          className={`text-sm px-3 py-1 rounded-lg transition-colors ${
            activeTab === t
              ? 'bg-brand text-white'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          {t}
        </button>
      ))}
      <div className="ml-auto flex items-center gap-4">
        <span className="text-xs bg-blue-900 text-blue-300 px-3 py-1 rounded-full font-medium">
          ALPACA PAPER
        </span>
        <SessionClock />
        {killActive && (
          <span className="text-xs bg-red-900 text-red-300 px-2 py-1 rounded-full animate-pulse">
            KILL SWITCH ON
          </span>
        )}
        <button
          onClick={onLogout}
          className="text-xs text-gray-500 hover:text-white transition-colors"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Shared card / stat components
// ---------------------------------------------------------------------------
function Card({ title, children, className = '' }) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl p-4 ${className}`}>
      {title && <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h3>}
      {children}
    </div>
  );
}

function Stat({ label, value, sub, color = 'text-white' }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  );
}

function Badge({ status }) {
  const map = {
    BUY:    'bg-green-900 text-green-300',
    SELL:   'bg-red-900  text-red-300',
    WAIT:   'bg-gray-800 text-gray-400',
    open:   'bg-blue-900 text-blue-300',
    closed: 'bg-gray-800 text-gray-400',
    FILLED: 'bg-green-900 text-green-300',
    FAILED: 'bg-red-900  text-red-300',
    PLACED: 'bg-yellow-900 text-yellow-300',
    PENDING:'bg-gray-800 text-gray-400',
    running:   'bg-yellow-900 text-yellow-300',
    completed: 'bg-green-900 text-green-300',
    failed:    'bg-red-900  text-red-300',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || 'bg-gray-800 text-gray-400'}`}>
      {status}
    </span>
  );
}

function Spinner() {
  return <div className="inline-block w-4 h-4 border-2 border-brand border-t-transparent rounded-full animate-spin" />;
}

// ---------------------------------------------------------------------------
// EquityChart (Chart.js)
// ---------------------------------------------------------------------------
function EquityChart({ data }) {
  const canvasRef = useRef(null);
  const chartRef  = useRef(null);

  useEffect(() => {
    if (!data || !data.length) return;
    const ctx = canvasRef.current.getContext('2d');
    if (chartRef.current) chartRef.current.destroy();
    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(p => p.bar_time ? new Date(p.bar_time).toLocaleDateString() : p.bar_index),
        datasets: [{
          label: 'Equity',
          data: data.map(p => p.equity),
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99,102,241,0.08)',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#6b7280', maxTicksLimit: 6 }, grid: { color: '#1f2937' } },
          y: { ticks: { color: '#6b7280' }, grid: { color: '#1f2937' } },
        },
      },
    });
    return () => { if (chartRef.current) chartRef.current.destroy(); };
  }, [data]);

  return <canvas ref={canvasRef} className="w-full h-48" />;
}

// ---------------------------------------------------------------------------
// KillSwitchModal
// ---------------------------------------------------------------------------
function KillSwitchModal({ isActive, onConfirm, onCancel }) {
  const [reason, setReason] = useState('');
  const action = isActive ? 'Resume Trading' : 'Halt Trading';

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <h2 className={`text-lg font-bold mb-2 ${isActive ? 'text-green-400' : 'text-red-400'}`}>
          {action}
        </h2>
        {!isActive && (
          <>
            <p className="text-sm text-gray-400 mb-3">
              This will immediately block all new trades. Open positions are NOT affected.
            </p>
            <input
              type="text"
              placeholder="Reason (optional)"
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:border-red-500"
            />
          </>
        )}
        {isActive && (
          <p className="text-sm text-gray-400 mb-4">
            Resume the trading pipeline? The system will restart analysis on the next scheduler cycle.
          </p>
        )}
        <div className="flex gap-3">
          <button
            onClick={() => onConfirm(reason)}
            className={`flex-1 py-2 rounded-lg text-sm font-medium ${
              isActive ? 'bg-green-700 hover:bg-green-600' : 'bg-red-700 hover:bg-red-600'
            } text-white transition-colors`}
          >
            {action}
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg text-sm font-medium bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------
function OverviewTab({ health, portfolio, killActive, setKillActive, showModal, setShowModal }) {
  const cap   = portfolio?.capital    || {};
  const pnl   = portfolio?.pnl        || {};
  const stats = portfolio?.trade_stats || {};

  async function handleKillConfirm(reason) {
    try {
      const path   = killActive ? '/resume' : '/halt';
      const body   = killActive ? {} : { reason: reason || 'Dashboard toggle', activated_by: 'dashboard' };
      const res    = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
      const data   = await res.json();
      if (res.ok) setKillActive(!killActive);
    } catch (err) { /* ignore */ }
    setShowModal(false);
  }

  return (
    <div className="p-4 space-y-4">
      {showModal && (
        <KillSwitchModal
          isActive={killActive}
          onConfirm={handleKillConfirm}
          onCancel={() => setShowModal(false)}
        />
      )}

      {/* Status row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <Stat label="DB" value={health?.db || '—'} color={health?.db === 'connected' ? 'text-green-400' : 'text-red-400'} />
        </Card>
        <Card>
          <Stat label="Redis" value={health?.redis || '—'} color={health?.redis === 'connected' ? 'text-green-400' : 'text-red-400'} />
        </Card>
        <Card>
          <Stat label="Kill Switch" value={killActive ? 'ACTIVE' : 'OFF'} color={killActive ? 'text-red-400' : 'text-green-400'} />
        </Card>
        <Card>
          <Stat
            label="Model Accuracy"
            value={health?.model_health?.accuracy != null ? `${(health.model_health.accuracy * 100).toFixed(1)}%` : '—'}
            sub={`n=${health?.model_health?.sample_size ?? 0}`}
            color={health?.model_health?.is_healthy ? 'text-green-400' : 'text-red-400'}
          />
        </Card>
      </div>

      {/* Capital */}
      <Card title="Capital (USD)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Total" value={cap.total_capital != null ? `$${Number(cap.total_capital).toLocaleString()}` : '—'} />
          <Stat label="Available" value={cap.available_capital != null ? `$${Number(cap.available_capital).toLocaleString()}` : '—'} color="text-blue-300" />
          <Stat label="Deployed" value={cap.deployed_capital != null ? `$${Number(cap.deployed_capital).toLocaleString()}` : '—'} color="text-yellow-300" />
          <Stat
            label="Realised P&L"
            value={pnl.total_realised_pnl != null ? `$${Number(pnl.total_realised_pnl).toLocaleString()}` : '—'}
            color={pnl.total_realised_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
          />
        </div>
      </Card>

      {/* Trade stats */}
      <Card title="Trade Statistics">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Total Trades" value={stats.total_trades ?? '—'} />
          <Stat label="Win Rate" value={stats.win_rate != null ? `${(stats.win_rate * 100).toFixed(1)}%` : '—'} color="text-green-400" />
          <Stat label="Avg Win" value={stats.avg_win != null ? `$${Number(stats.avg_win).toFixed(0)}` : '—'} color="text-green-400" />
          <Stat label="Avg Loss" value={stats.avg_loss != null ? `$${Number(stats.avg_loss).toFixed(0)}` : '—'} color="text-red-400" />
        </div>
      </Card>

      {/* Kill switch toggle */}
      <Card title="Trading Control">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowModal(true)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              killActive
                ? 'bg-green-700 hover:bg-green-600 text-white'
                : 'bg-red-700 hover:bg-red-600 text-white'
            }`}
          >
            {killActive ? 'Resume Trading' : 'Halt Trading'}
          </button>
          <span className="text-sm text-gray-400">
            {killActive ? 'Trading is currently HALTED. No new positions will be opened.' : 'Trading is active. Kill switch is OFF.'}
          </span>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Portfolio
// ---------------------------------------------------------------------------
function PortfolioTab() {
  const [positions, setPositions] = useState(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    apiFetch('/portfolio/positions')
      .then(r => r.json())
      .then(d => setPositions(d))
      .catch(() => setPositions({ positions: [], error: 'Failed to load' }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 flex justify-center"><Spinner /></div>;

  const pos = positions?.positions || [];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-gray-300">Open Positions ({pos.length})</h2>
        <span className="text-xs text-gray-500">
          Unrealised P&L: {positions?.total_unrealised_pnl != null ? `$${Number(positions.total_unrealised_pnl).toFixed(2)}` : '—'}
        </span>
      </div>
      {pos.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No open positions.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 pr-4">Symbol</th>
                <th className="text-left py-2 pr-4">Side</th>
                <th className="text-right py-2 pr-4">Qty</th>
                <th className="text-right py-2 pr-4">Entry</th>
                <th className="text-right py-2 pr-4">SL</th>
                <th className="text-right py-2 pr-4">Target</th>
                <th className="text-right py-2 pr-4">Unrealised P&L</th>
                <th className="text-left py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {pos.map(p => (
                <tr key={p.position_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 pr-4 font-medium">{p.symbol}</td>
                  <td className="py-2 pr-4"><Badge status={p.action} /></td>
                  <td className="py-2 pr-4 text-right">{p.quantity}</td>
                  <td className="py-2 pr-4 text-right">{p.entry_price}</td>
                  <td className="py-2 pr-4 text-right text-red-400">{p.stop_loss}</td>
                  <td className="py-2 pr-4 text-right text-green-400">{p.target}</td>
                  <td className={`py-2 pr-4 text-right ${Number(p.unrealised_pnl) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${Number(p.unrealised_pnl || 0).toFixed(2)}
                  </td>
                  <td className="py-2"><Badge status={p.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Trades
// ---------------------------------------------------------------------------
function TradesTab() {
  const [orders, setOrders] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/orders')
      .then(r => r.json())
      .then(d => setOrders(d))
      .catch(() => setOrders({ orders: [] }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 flex justify-center"><Spinner /></div>;
  const list = orders?.orders || [];

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Orders ({list.length})</h2>
      {list.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No orders yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 pr-4">Symbol</th>
                <th className="text-left py-2 pr-4">Action</th>
                <th className="text-right py-2 pr-4">Qty</th>
                <th className="text-right py-2 pr-4">Fill Price</th>
                <th className="text-left py-2 pr-4">Mode</th>
                <th className="text-left py-2 pr-4">Status</th>
                <th className="text-left py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {list.map(o => (
                <tr key={o.order_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 pr-4 font-medium">{o.symbol}</td>
                  <td className="py-2 pr-4"><Badge status={o.action} /></td>
                  <td className="py-2 pr-4 text-right">{o.quantity}</td>
                  <td className="py-2 pr-4 text-right">{o.filled_price ?? '—'}</td>
                  <td className="py-2 pr-4 text-xs text-gray-400">{o.broker_mode}</td>
                  <td className="py-2 pr-4"><Badge status={o.status} /></td>
                  <td className="py-2 text-xs text-gray-500">
                    {o.placed_at ? new Date(o.placed_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Backtest
// ---------------------------------------------------------------------------
function BacktestTab() {
  const [runs, setRuns]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState(null);
  const [equityCurve, setEq]    = useState(null);

  // Form state
  const [symbol, setSymbol]   = useState('AAPL');
  const [start, setStart]     = useState('2023-01-01');
  const [end, setEnd]         = useState('2024-01-01');
  const [capital, setCapital] = useState('100000');
  const [submitting, setSubmitting] = useState(false);

  function loadRuns() {
    apiFetch('/backtest/runs')
      .then(r => r.json())
      .then(d => setRuns(d.runs || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadRuns(); }, []);

  async function launchBacktest(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res  = await apiFetch('/backtest/run', {
        method: 'POST',
        body: JSON.stringify({ symbol, start_date: start, end_date: end, initial_capital: parseFloat(capital) }),
      });
      const data = await res.json();
      if (res.ok) { setTimeout(loadRuns, 1000); }
    } finally {
      setSubmitting(false);
    }
  }

  async function selectRun(run) {
    setSelected(run);
    setEq(null);
    const res  = await apiFetch(`/backtest/runs/${run.run_id}/equity-curve`);
    const data = await res.json();
    setEq(data.equity_curve || []);
  }

  return (
    <div className="p-4 space-y-4">
      {/* Launch form */}
      <Card title="New Backtest">
        <form onSubmit={launchBacktest} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Symbol</label>
            <input value={symbol} onChange={e => setSymbol(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm w-36 focus:outline-none focus:border-brand" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Start Date</label>
            <input type="date" value={start} onChange={e => setStart(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-brand" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">End Date</label>
            <input type="date" value={end} onChange={e => setEnd(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-brand" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Capital (USD)</label>
            <input value={capital} onChange={e => setCapital(e.target.value)}
              placeholder="100000"
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm w-28 focus:outline-none focus:border-brand" />
          </div>
          <button type="submit" disabled={submitting}
            className="bg-brand hover:bg-brand-dark disabled:opacity-50 text-white px-4 py-1.5 rounded text-sm font-medium transition-colors">
            {submitting ? 'Launching…' : 'Run Backtest'}
          </button>
          <button type="button" onClick={loadRuns}
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded text-sm transition-colors">
            Refresh
          </button>
        </form>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Runs list */}
        <Card title="Backtest Runs">
          {loading ? <Spinner /> : runs.length === 0 ? (
            <p className="text-sm text-gray-500 italic">No runs yet.</p>
          ) : (
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {runs.map(r => (
                <div key={r.run_id}
                  onClick={() => selectRun(r)}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
                    selected?.run_id === r.run_id ? 'bg-brand/20 border border-brand/40' : 'hover:bg-gray-800'
                  }`}>
                  <span className="font-medium">{r.symbol}</span>
                  <span className="text-xs text-gray-400">{r.start_date} → {r.end_date}</span>
                  <Badge status={r.status} />
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Selected run details */}
        {selected && (
          <Card title={`Results — ${selected.symbol}`}>
            {selected.status === 'running' ? (
              <div className="flex items-center gap-2 text-sm text-yellow-300"><Spinner /> Running…</div>
            ) : selected.metrics ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Stat label="Total Return" value={`${((selected.metrics.total_return_pct || 0)).toFixed(2)}%`}
                    color={selected.metrics.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
                  <Stat label="Win Rate" value={`${((selected.metrics.win_rate || 0) * 100).toFixed(1)}%`} color="text-green-400" />
                  <Stat label="Sharpe" value={(selected.metrics.sharpe_ratio || 0).toFixed(2)} />
                  <Stat label="Max Drawdown" value={`${((selected.metrics.max_drawdown_pct || 0)).toFixed(2)}%`} color="text-red-400" />
                  <Stat label="Total Trades" value={selected.metrics.total_trades ?? '—'} />
                  <Stat label="Profit Factor" value={(selected.metrics.profit_factor || 0).toFixed(2)} />
                </div>
                {equityCurve && equityCurve.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500 mb-1">Equity Curve</p>
                    <EquityChart data={equityCurve} />
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No metrics available.</p>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Observability
// ---------------------------------------------------------------------------
function ObservabilityTab() {
  const [metrics, setMetrics] = useState(null);
  const [audit, setAudit]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/observability/metrics?minutes=60').then(r => r.json()),
      apiFetch('/observability/audit?limit=50').then(r => r.json()),
    ]).then(([m, a]) => {
      setMetrics(m);
      setAudit(a);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 flex justify-center"><Spinner /></div>;

  const components = metrics?.components || {};
  const events     = audit?.events || [];

  const severityColor = s => ({
    ERROR: 'text-red-400', CRITICAL: 'text-red-400',
    WARNING: 'text-yellow-400', INFO: 'text-gray-300', DEBUG: 'text-gray-500',
  })[s] || 'text-gray-400';

  return (
    <div className="p-4 space-y-4">
      <Card title="Component Latency (last 60 min)">
        {Object.keys(components).length === 0 ? (
          <p className="text-sm text-gray-500 italic">No metrics yet.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(components).map(([name, s]) => (
              <div key={name} className="bg-gray-800 rounded-lg p-3">
                <p className="text-xs text-gray-400 mb-1 truncate">{name}</p>
                <p className="text-sm font-medium">{s.avg_ms ?? '—'}ms avg</p>
                <p className="text-xs text-gray-500">p95: {s.p95_ms ?? '—'}ms</p>
                <p className="text-xs text-gray-500">
                  {s.success_count ?? 0}/{(s.success_count ?? 0) + (s.failure_count ?? 0)} ok
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Recent Audit Events">
        <div className="space-y-1 max-h-96 overflow-y-auto text-xs font-mono">
          {events.length === 0 ? (
            <p className="text-gray-500 italic">No events.</p>
          ) : events.map((e, i) => (
            <div key={i} className="flex gap-3 py-0.5 border-b border-gray-800/40">
              <span className="text-gray-600 w-20 flex-shrink-0">
                {e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}
              </span>
              <span className={`w-16 flex-shrink-0 ${severityColor(e.severity)}`}>{e.severity}</span>
              <span className="text-gray-400 w-24 flex-shrink-0 truncate">{e.component}</span>
              <span className="text-gray-300 truncate">{e.message}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Trade Setup
// ---------------------------------------------------------------------------
function TradeSetupTab() {
  const [watchlist,    setWatchlist]    = useState([]);

  // form state
  const [symbol,     setSymbol]     = useState('');
  const [capitalPct, setCapitalPct] = useState(10);
  const [formMsg,    setFormMsg]    = useState('');
  const [saving,     setSaving]     = useState(false);

  // total capital from portfolio (for $ display)
  const [totalCapital, setTotalCapital] = useState(0);

  async function loadWatchlist() {
    try {
      const res  = await apiFetch('/watchlist');
      const data = await res.json();
      if (res.ok) setWatchlist(data.watchlist || []);
    } catch { /* ignore */ }
  }

  async function loadPortfolioCapital() {
    try {
      const res  = await apiFetch('/portfolio');
      const data = await res.json();
      setTotalCapital(data?.capital?.total_capital || 0);
    } catch { /* ignore */ }
  }

  useEffect(() => {
    loadWatchlist();
    loadPortfolioCapital();
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setSaving(true);
    setFormMsg('');
    try {
      const res  = await apiFetch('/watchlist', {
        method: 'POST',
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), capital_pct: capitalPct }),
      });
      const data = await res.json();
      if (res.ok) {
        setFormMsg(`${data.symbol} added (${data.capital_pct}% capital)`);
        setSymbol('');
        setCapitalPct(10);
        await loadWatchlist();
      } else {
        setFormMsg(`Error: ${data.error}`);
      }
    } catch {
      setFormMsg('Network error');
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(sym) {
    try {
      const res = await apiFetch(`/watchlist/${encodeURIComponent(sym)}`, { method: 'DELETE' });
      if (res.ok) await loadWatchlist();
    } catch { /* ignore */ }
  }

  const dollarAmt = totalCapital > 0
    ? `≈ $${Math.round(totalCapital * capitalPct / 100).toLocaleString('en-US')}`
    : '';

  const allocatedPct = watchlist.filter(w => w.is_active).reduce((s, w) => s + w.capital_pct, 0);

  return (
    <div className="p-4 space-y-4 max-w-3xl">

      {/* Add Stock Form */}
      <Card title="Add Stock to Today's Trading">
        <form onSubmit={handleAdd} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. AAPL, MSFT, TSLA"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-brand"
            />
            <p className="text-xs text-gray-600 mt-1">Enter US ticker symbols (no exchange suffix needed)</p>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs text-gray-500">Capital Allocation</label>
              <span className="text-sm font-bold text-white">
                {capitalPct}% {dollarAmt && <span className="text-gray-400 font-normal text-xs">{dollarAmt}</span>}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              value={capitalPct}
              onChange={e => setCapitalPct(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-0.5">
              <span>1%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {formMsg && (
            <p className={`text-xs ${formMsg.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
              {formMsg}
            </p>
          )}

          <button
            type="submit"
            disabled={saving || !symbol.trim()}
            className="bg-brand hover:bg-brand-dark disabled:opacity-50 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
          >
            {saving ? 'Adding…' : 'Add to Watchlist'}
          </button>
        </form>
      </Card>

      {/* Current Watchlist */}
      <Card title={`Active Watchlist (${watchlist.filter(w => w.is_active).length} stocks)`}>
        {allocatedPct > 0 && (
          <div className="mb-3 flex items-center gap-2">
            <div className="flex-1 bg-gray-800 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${allocatedPct > 100 ? 'bg-red-500' : 'bg-brand'}`}
                style={{ width: `${Math.min(allocatedPct, 100)}%` }}
              />
            </div>
            <span className={`text-xs font-medium ${allocatedPct > 100 ? 'text-red-400' : 'text-gray-400'}`}>
              {allocatedPct.toFixed(1)}% allocated
              {allocatedPct > 100 && ' — exceeds 100%!'}
            </span>
          </div>
        )}

        {watchlist.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No stocks in watchlist. Add stocks above — the scheduler will start trading them on the next 15-min cycle.
          </p>
        ) : (
          <div className="space-y-2">
            {watchlist.map(w => (
              <div key={w.symbol} className="flex items-center justify-between py-2 border-b border-gray-800/50">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${w.is_active ? 'bg-green-400' : 'bg-gray-600'}`} />
                  <span className="font-medium text-white text-sm">{w.symbol}</span>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-sm font-bold text-indigo-400">{w.capital_pct}%</span>
                    {totalCapital > 0 && (
                      <span className="text-xs text-gray-500 ml-1">
                        ${Math.round(totalCapital * w.capital_pct / 100).toLocaleString('en-US')}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemove(w.symbol)}
                    className="text-red-500 hover:text-red-400 text-xs transition-colors"
                    title="Remove from watchlist"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Market Sentiment (Bullish vs Bearish)
// ---------------------------------------------------------------------------

function classifyStock(result) {
  const p = result.probability_up ?? 0.5;
  if (p > 0.55) return 'bullish';
  if (p < 0.45) return 'bearish';
  return 'neutral';
}

function SentimentSignalRow({ result }) {
  const summary  = result.analysis_summary  || {};
  const pattern  = result.pattern_detected  || {};
  const pct      = Math.round((result.probability_up ?? 0.5) * 100);

  const trendCls = t => t === 'uptrend'  ? 'bg-green-900 text-green-300'
                      : t === 'downtrend' ? 'bg-red-900 text-red-300'
                      : 'bg-gray-800 text-gray-400';
  const sentCls  = s => s === 'positive' ? 'bg-green-900 text-green-300'
                      : s === 'negative'  ? 'bg-red-900 text-red-300'
                      : 'bg-gray-800 text-gray-400';
  const volCls   = v => v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : 'text-gray-400';
  const barCls   = p => p > 55 ? 'bg-green-500' : p < 45 ? 'bg-red-500' : 'bg-gray-500';

  return (
    <div className="mt-2 space-y-2 text-xs">
      {/* Signal badges */}
      <div className="flex flex-wrap gap-1">
        {summary.trend && (
          <span className={`px-2 py-0.5 rounded-full font-medium ${trendCls(summary.trend)}`}>
            {summary.trend}
          </span>
        )}
        {summary.sentiment && (
          <span className={`px-2 py-0.5 rounded-full font-medium ${sentCls(summary.sentiment)}`}>
            {summary.sentiment}
          </span>
        )}
        {pattern.pattern && pattern.pattern !== 'none' && (
          <span className="px-2 py-0.5 rounded-full font-medium bg-indigo-900 text-indigo-300">
            {pattern.pattern.replace(/_/g, ' ')} {Math.round((pattern.confidence ?? 0) * 100)}%
          </span>
        )}
        {summary.volume_signal != null && (
          <span className={`font-medium ${volCls(summary.volume_signal)}`}>
            vol {summary.volume_signal > 0 ? '+' : ''}{Number(summary.volume_signal).toFixed(1)}
          </span>
        )}
      </div>
      {/* Probability bar */}
      <div>
        <div className="flex justify-between text-gray-400 mb-0.5">
          <span>P(up)</span><span>{pct}%</span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-1.5">
          <div className={`h-1.5 rounded-full ${barCls(pct)}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      {/* Reason */}
      {result.reason && (
        <p className="text-gray-400 italic leading-snug">{result.reason}</p>
      )}
    </div>
  );
}

function StockSentimentCard({ result }) {
  const STATUS_MAP = { BUY: 'buy', SELL: 'sell', WAIT: 'wait' };
  if (result.error) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <p className="font-bold text-white">{result.symbol}</p>
        <p className="text-red-400 text-xs mt-1">{result.error}</p>
      </div>
    );
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between">
        <p className="font-bold text-white">{result.symbol}</p>
        <Badge status={STATUS_MAP[result.decision] || 'wait'}>{result.decision || 'WAIT'}</Badge>
      </div>
      <SentimentSignalRow result={result} />
    </div>
  );
}

function MarketSentimentTab() {
  // This tab intentionally does not check the kill switch —
  // reading market signals is always safe even when trading is halted.
  const [results,     setResults]     = React.useState([]);
  const [loading,     setLoading]     = React.useState(true);
  const [error,       setError]       = React.useState('');
  const [lastUpdated, setLastUpdated] = React.useState(null);

  function load() {
    setLoading(true);
    setError('');
    apiFetch('/sentiment')
      .then(r => r.json())
      .then(d => {
        setResults(d.results || []);
        setLastUpdated(new Date());
      })
      .catch(() => setError('Failed to load sentiment data.'))
      .finally(() => setLoading(false));
  }

  React.useEffect(() => { load(); }, []);

  const bullish = results.filter(r => !r.error && classifyStock(r) === 'bullish');
  const bearish = results.filter(r => !r.error && classifyStock(r) === 'bearish');
  const neutral = results.filter(r => !r.error && classifyStock(r) === 'neutral');

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Market Sentiment</h2>
          {lastUpdated && (
            <p className="text-xs text-gray-400 mt-0.5">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm rounded-lg"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {/* States */}
      {loading && <div className="flex justify-center py-12"><Spinner /></div>}
      {!loading && error && <p className="text-red-400">{error}</p>}
      {!loading && !error && results.length === 0 && (
        <p className="text-gray-400 text-sm">
          No active symbols in your watchlist. Add stocks in the Trade Setup tab.
        </p>
      )}

      {/* Bullish / Bearish columns */}
      {!loading && !error && results.length > 0 && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Bullish column */}
          <div>
            <p className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-3">
              Bullish ({bullish.length})
            </p>
            {bullish.length === 0 ? (
              <p className="text-gray-500 text-sm">None</p>
            ) : (
              <div className="space-y-3">
                {bullish.map(r => <StockSentimentCard key={r.symbol} result={r} />)}
              </div>
            )}
          </div>
          {/* Bearish column */}
          <div>
            <p className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3">
              Bearish ({bearish.length})
            </p>
            {bearish.length === 0 ? (
              <p className="text-gray-500 text-sm">None</p>
            ) : (
              <div className="space-y-3">
                {bearish.map(r => <StockSentimentCard key={r.symbol} result={r} />)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Neutral row */}
      {!loading && !error && neutral.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Neutral ({neutral.length})
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {neutral.map(r => <StockSentimentCard key={r.symbol} result={r} />)}
          </div>
        </div>
      )}

      {/* Error cards (fetch failures per symbol) */}
      {!loading && results.some(r => r.error) && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Failed to fetch
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {results.filter(r => r.error).map(r => <StockSentimentCard key={r.symbol} result={r} />)}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Settings
// ---------------------------------------------------------------------------
function SettingsTab({ health }) {
  return (
    <div className="p-4 space-y-4 max-w-lg">
      <Card title="Alpaca Paper Trading">
        <div className="space-y-3 text-sm text-gray-300">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex items-center justify-center w-12 h-12 rounded-full bg-gray-800">
              <span className="text-2xl">📄</span>
            </div>
            <div>
              <p className="font-medium text-white">Paper Trading Mode</p>
              <p className="text-xs text-gray-500">Simulated trades — no real money</p>
            </div>
          </div>
          
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
            <p className="font-medium text-white mb-2">Current Status</p>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">Mode:</span>
                <span className="text-white font-medium">Paper Only</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Broker:</span>
                <span className="text-white">Alpaca Paper API</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Live Trading:</span>
                <span className="text-red-400">Not Available (v1)</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
            <p className="font-medium text-white mb-1">Setup Instructions</p>
            <ol className="list-decimal ml-4 space-y-1 text-xs text-gray-400">
              <li>Sign up for free at <a href="https://alpaca.markets/" target="_blank" rel="noopener noreferrer" className="text-brand underline">alpaca.markets</a></li>
              <li>Navigate to Paper Trading dashboard</li>
              <li>Generate API keys (Key ID + Secret Key)</li>
              <li>Add to <code className="bg-gray-900 px-1 rounded">ALPACA_API_KEY</code> and <code className="bg-gray-900 px-1 rounded">ALPACA_SECRET_KEY</code> environment variables</li>
              <li>Restart backend to activate</li>
            </ol>
          </div>
          
          <p className="text-yellow-400 text-xs">
            <strong>Note:</strong> Without Alpaca credentials, orders are logged locally but not sent to Alpaca.
            For realistic simulation with fills and portfolio tracking, add your paper trading keys.
          </p>
        </div>
      </Card>

      <Card title="System Information">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Market:</span>
            <span className="text-white">US Equities (NYSE/NASDAQ)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Trading Hours:</span>
            <span className="text-white">09:30–16:00 ET</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Currency:</span>
            <span className="text-white">USD ($)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Model Status:</span>
            <span className={health?.model_health?.is_healthy ? 'text-green-400' : 'text-red-400'}>
              {health?.model_health?.is_healthy ? 'Healthy' : 'Degraded'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Kill Switch:</span>
            <span className={health?.kill_switch ? 'text-red-400' : 'text-green-400'}>
              {health?.kill_switch ? 'ACTIVE' : 'OFF'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------
function App() {
  const [loggedIn, setLoggedIn]     = useState(!!getToken());
  const [activeTab, setActiveTab]   = useState('Overview');
  const [health, setHealth]         = useState(null);
  const [portfolio, setPortfolio]   = useState(null);
  const [killActive, setKillActive] = useState(false);
  const [showModal, setShowModal]   = useState(false);

  const refreshData = useCallback(() => {
    if (!getToken()) return;
    fetch(`${API_BASE}/health`)
      .then(r => r.json())
      .then(d => { setHealth(d); setKillActive(!!d.kill_switch); })
      .catch(() => {});
    apiFetch('/portfolio')
      .then(r => r.json())
      .then(d => setPortfolio(d))
      .catch(() => {});
  }, []);

  // Initial load + auto-refresh every 30 seconds
  useEffect(() => {
    if (!loggedIn) return;
    refreshData();
    const id = setInterval(refreshData, 30000);
    return () => clearInterval(id);
  }, [loggedIn, refreshData]);

  if (!loggedIn) {
    return <LoginScreen onLogin={() => { setLoggedIn(true); }} />;
  }

  function handleLogout() {
    clearToken();
    setLoggedIn(false);
  }

  return (
    <div className="min-h-screen flex flex-col">
      <NavBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        killActive={killActive}
        onLogout={handleLogout}
      />
      <main className="flex-1 overflow-auto">
        {activeTab === 'Overview'       && <OverviewTab health={health} portfolio={portfolio} killActive={killActive} setKillActive={setKillActive} showModal={showModal} setShowModal={setShowModal} />}
        {activeTab === 'Trade Setup'      && <TradeSetupTab />}
        {activeTab === 'Market Sentiment' && <MarketSentimentTab />}
        {activeTab === 'Portfolio'        && <PortfolioTab />}
        {activeTab === 'Trades'         && <TradesTab />}
        {activeTab === 'Backtest'       && <BacktestTab />}
        {activeTab === 'Observability'  && <ObservabilityTab />}
        {activeTab === 'Settings'       && <SettingsTab health={health} />}
      </main>
      <footer className="text-center text-xs text-gray-700 py-2">
        InvestRight · Auto-refreshes every 30s
      </footer>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
