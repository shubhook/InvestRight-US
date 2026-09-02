const { useState, useEffect, useRef, useCallback } = React;

// ---------------------------------------------------------------------------
// Config & Auth
// ---------------------------------------------------------------------------
// API routing: use /api for same-origin (nginx proxy in docker), or empty string for direct backend (run.sh → :5001)
const API_BASE = window.location.port === '5001' ? '' : '/api';

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
// USD formatter
// ---------------------------------------------------------------------------
function usd(n, { cents = true } = {}) {
  if (n == null || isNaN(n)) return '—';
  const formatted = Number(n).toLocaleString('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  });
  return `$${formatted}`;
}

// ---------------------------------------------------------------------------
// Login Screen
// ---------------------------------------------------------------------------
function LoginScreen({ onLogin }) {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/token`, {
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
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#0f1419' }}>
      <div className="p-8 w-full max-w-sm" style={{ background: '#171c22', border: '1px solid #2a3340', borderRadius: '10px' }}>
        <h1 className="text-2xl font-bold text-center mb-2" style={{ color: '#6366f1' }}>InvestRight-US</h1>
        <p className="text-center mb-6" style={{ fontSize: '14px', color: '#8b9aab' }}>Paper US equities · Alpaca</p>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block mb-1.5" style={{ fontSize: '12px', color: '#8b9aab' }}>API Key</label>
            <input
              type="password"
              placeholder="Your InvestRight API key"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              className="w-full px-4 py-2 rounded-lg focus:outline-none"
              style={{ background: '#0f1419', border: '1px solid #2a3340', color: '#e8eef4', fontSize: '14px' }}
            />
          </div>
          {error && <p style={{ color: '#ef4444', fontSize: '13px' }}>{error}</p>}
          <button
            type="submit"
            disabled={loading || !apiKey}
            className="w-full py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
            style={{ background: '#6366f1', color: 'white', fontSize: '14px' }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header with Clock and Paper Status
// ---------------------------------------------------------------------------
function Header({ segment, setSegment, killActive, onLogout }) {
  const [session, setSession] = useState(null);
  const [sessionError, setSessionError] = useState(false);

  useEffect(() => {
    function loadSession() {
      fetch(`${API_BASE}/session`)
        .then(r => {
          if (!r.ok) throw new Error('Session endpoint unavailable');
          return r.json();
        })
        .then(d => {
          setSession(d);
          setSessionError(false);
        })
        .catch(() => {
          setSessionError(true);
          setSession(null);
        });
    }
    loadSession();
    const timer = setInterval(loadSession, 30000);
    return () => clearInterval(timer);
  }, []);

  // If session endpoint available, use server data
  let etTime, istTime, isOpen, clockNote;
  
  if (session && !sessionError) {
    // Use server session data
    const etDate = new Date(session.et_iso);
    etTime = etDate.toLocaleTimeString('en-US', {
      timeZone: 'America/New_York',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    istTime = etDate.toLocaleTimeString('en-US', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
    isOpen = session.is_rth;
    clockNote = null;
  } else {
    // Degrade: show ET time with note, no client-side RTH computation
    const now = new Date();
    etTime = now.toLocaleTimeString('en-US', {
      timeZone: 'America/New_York',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    istTime = now.toLocaleTimeString('en-US', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
    isOpen = false; // Unknown without server
    clockNote = 'holidays on server';
  }

  return (
    <header style={{ background: '#0f1419', borderBottom: '1px solid #2a3340', height: '64px' }}>
      <div className="h-full px-6 flex items-center gap-6">
        {/* Left: Wordmark + Paper Status */}
        <div className="flex items-center gap-3">
          <span style={{ fontSize: '15px', fontWeight: '600', color: '#e8eef4' }}>InvestRight-US</span>
          <span
            className="px-2 py-1 rounded-full font-medium uppercase tracking-wide"
            style={{
              fontSize: '11px',
              background: 'rgba(217, 119, 6, 0.15)',
              color: '#fbbf24'
            }}
          >
            Alpaca Paper
          </span>
        </div>

        {/* Center/Right: Clock */}
        <div className="ml-auto flex items-center gap-4">
          <div className="text-right">
            <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: '24px', fontWeight: '600', color: '#e8eef4', lineHeight: '1' }}>
              {etTime}
            </div>
            <div style={{ fontSize: '12px', color: '#8b9aab', marginTop: '2px' }}>
              {isOpen ? 'NYSE Open' : 'NYSE Closed'} · IST {istTime}
              {clockNote && <span style={{ marginLeft: '8px', opacity: '0.6' }}>· {clockNote}</span>}
            </div>
          </div>
          {!isOpen && (
            <span
              className="px-2 py-1 rounded-full font-medium uppercase tracking-wide"
              style={{ fontSize: '11px', background: '#2a3340', color: '#8b9aab' }}
            >
              NYSE Closed
            </span>
          )}
        </div>

        {/* Far Right: Kill + Logout */}
        <div className="flex items-center gap-3">
          {killActive && (
            <span
              className="px-2 py-1 rounded-full animate-pulse"
              style={{ fontSize: '11px', background: '#7f1d1d', color: '#fca5a5' }}
            >
              KILL ON
            </span>
          )}
          <button
            onClick={onLogout}
            style={{ fontSize: '12px', color: '#8b9aab' }}
            className="hover:text-white transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Segment Control
// ---------------------------------------------------------------------------
function SegmentControl({ segment, setSegment }) {
  const segments = ['Desk', 'Trade', 'System'];
  return (
    <div style={{ background: '#0f1419', borderBottom: '1px solid #2a3340', height: '40px' }}>
      <div className="h-full px-6 flex items-center gap-1">
        {segments.map(s => (
          <button
            key={s}
            onClick={() => setSegment(s)}
            className="flex-1 h-full transition-colors"
            style={{
              fontSize: '13px',
              fontWeight: '500',
              color: segment === s ? '#e8eef4' : '#8b9aab',
              background: segment === s ? '#2a3340' : 'transparent',
              borderRadius: segment === s ? '6px' : '0'
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Desk Segment
// ---------------------------------------------------------------------------
function DeskSegment({ session }) {
  const [portfolio, setPortfolio] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    apiFetch('/portfolio').then(r => r.json()).then(d => setPortfolio(d)).catch(() => {});
    apiFetch('/portfolio/positions').then(r => r.json()).then(d => setPositions(d.positions || [])).catch(() => {});
    apiFetch('/trades?limit=5').then(r => r.json()).then(d => setTrades(d.trades || [])).catch(() => {});
  }, []);

  const isOpen = session?.is_rth || false;
  const cap = portfolio?.capital || {};
  const pnl = portfolio?.pnl || {};

  return (
    <div className="p-6 space-y-6">
      {/* Closed Banner */}
      {!isOpen && (
        <div className="px-4 py-3 rounded-lg" style={{ background: '#2a3340', border: '1px solid #3b4758', color: '#8b9aab', fontSize: '14px' }}>
          NYSE is closed. The book stays. Orders wait for the next bell.
        </div>
      )}

      {/* Money Row */}
      <div className="grid grid-cols-3 gap-6">
        <div>
          <div style={{ fontSize: '12px', color: '#8b9aab', marginBottom: '4px' }}>Total Capital</div>
          <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: '32px', fontWeight: '700', color: '#e8eef4', letterSpacing: '-0.02em' }}>
            {usd(cap.total_capital, { cents: false })}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#8b9aab', marginBottom: '4px' }}>Available</div>
          <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: '32px', fontWeight: '700', color: '#60a5fa', letterSpacing: '-0.02em' }}>
            {usd(cap.available_capital, { cents: false })}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#8b9aab', marginBottom: '4px' }}>Realised P&L</div>
          <div
            style={{
              fontFamily: 'ui-monospace, monospace',
              fontSize: '32px',
              fontWeight: '700',
              color: (pnl.total_realised_pnl || 0) >= 0 ? '#34d399' : '#f87171',
              letterSpacing: '-0.02em'
            }}
          >
            {usd(pnl.total_realised_pnl)}
          </div>
        </div>
      </div>

      {/* Positions */}
      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Positions
        </h3>
        {positions.length === 0 ? (
          <p style={{ fontSize: '14px', color: '#8b9aab', fontStyle: 'italic' }}>
            No positions yet. Add a US ticker to the book.
          </p>
        ) : (
          <div className="space-y-2">
            {positions.map(p => (
              <div key={p.symbol} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid #2a3340' }}>
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#e8eef4' }}>{p.symbol}</span>
                <span style={{ fontSize: '14px', color: (p.unrealised_pnl || 0) >= 0 ? '#34d399' : '#f87171' }}>
                  {usd(p.unrealised_pnl)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Fills */}
      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Recent Fills
        </h3>
        {trades.length === 0 ? (
          <p style={{ fontSize: '14px', color: '#8b9aab', fontStyle: 'italic' }}>
            No paper fills yet.
          </p>
        ) : (
          <div className="space-y-2">
            {trades.map(t => (
              <div key={t.trade_id} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid #2a3340' }}>
                <div>
                  <span style={{ fontSize: '14px', fontWeight: '500', color: '#e8eef4' }}>{t.symbol}</span>
                  <span style={{ fontSize: '12px', color: '#8b9aab', marginLeft: '8px' }}>
                    {t.action} {t.quantity}
                  </span>
                </div>
                <span style={{ fontSize: '14px', color: (t.realised_pnl || 0) >= 0 ? '#34d399' : '#f87171' }}>
                  {usd(t.realised_pnl)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trade Segment
// ---------------------------------------------------------------------------
function TradeSegment() {
  const [watchlist, setWatchlist] = useState([]);
  const [symbol, setSymbol] = useState('');
  const [capitalPct, setCapitalPct] = useState(10);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    loadWatchlist();
  }, []);

  function loadWatchlist() {
    apiFetch('/watchlist').then(r => r.json()).then(d => setWatchlist(d.watchlist || [])).catch(() => {});
  }

  async function handleAdd(e) {
    e.preventDefault();
    setMsg('');
    try {
      const res = await apiFetch('/watchlist', {
        method: 'POST',
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), capital_pct: capitalPct }),
      });
      const data = await res.json();
      if (res.ok) {
        setMsg(`${data.symbol} added`);
        setSymbol('');
        loadWatchlist();
      } else {
        setMsg(`Error: ${data.error}`);
      }
    } catch (err) {
      // Network error (fetch failed) or JSON parse error
      setMsg(err.message || 'Network error');
    }
  }

  async function handleRemove(sym) {
    try {
      await apiFetch(`/watchlist/${encodeURIComponent(sym)}`, { method: 'DELETE' });
      loadWatchlist();
    } catch {}
  }

  return (
    <div className="p-6 space-y-6">
      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Add Ticker
        </h3>
        <form onSubmit={handleAdd} className="space-y-4">
          <div>
            <input
              type="text"
              value={symbol}
              onChange={e => setSymbol(e.target.value.toUpperCase())}
              placeholder="AAPL"
              className="w-full px-3 py-2 rounded-lg"
              style={{ background: '#0f1419', border: '1px solid #2a3340', color: '#e8eef4', fontSize: '14px' }}
            />
            <p style={{ fontSize: '13px', color: '#8b9aab', marginTop: '4px' }}>US ticker · AAPL not AAPL.NS</p>
          </div>
          <div>
            <label style={{ fontSize: '12px', color: '#8b9aab' }}>Capital Allocation: {capitalPct}%</label>
            <input
              type="range"
              min="1"
              max="100"
              value={capitalPct}
              onChange={e => setCapitalPct(Number(e.target.value))}
              className="w-full mt-2"
            />
          </div>
          {msg && <p style={{ fontSize: '13px', color: msg.startsWith('Error') ? '#f87171' : '#34d399' }}>{msg}</p>}
          <button
            type="submit"
            disabled={!symbol.trim()}
            className="px-4 py-2 rounded-lg font-medium disabled:opacity-50"
            style={{ background: '#6366f1', color: 'white', fontSize: '14px' }}
          >
            Add to Watchlist
          </button>
        </form>
      </div>

      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Active Watchlist
        </h3>
        {watchlist.length === 0 ? (
          <p style={{ fontSize: '14px', color: '#8b9aab', fontStyle: 'italic' }}>
            Nothing on the book. Add AAPL to run the next cycle.
          </p>
        ) : (
          <div className="space-y-2">
            {watchlist.map(w => (
              <div key={w.symbol} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid #2a3340' }}>
                <span style={{ fontSize: '14px', fontWeight: '500', color: '#e8eef4' }}>{w.symbol}</span>
                <div className="flex items-center gap-3">
                  <span style={{ fontSize: '14px', color: '#8b9aab' }}>{w.capital_pct}%</span>
                  <button
                    onClick={() => handleRemove(w.symbol)}
                    style={{ fontSize: '12px', color: '#f87171' }}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// System Segment
// ---------------------------------------------------------------------------
function SystemSegment({ killActive, setKillActive }) {
  return (
    <div className="p-6 space-y-6">
      {/* Kill Switch */}
      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Kill Switch
        </h3>
        <p style={{ fontSize: '14px', color: '#8b9aab', marginBottom: '12px' }}>
          Emergency stop for all automated trading. Status: <strong style={{ color: killActive ? '#f87171' : '#34d399' }}>
            {killActive ? 'ACTIVE' : 'OFF'}
          </strong>
        </p>
        <button
          onClick={() => {
            if (confirm(killActive ? 'Deactivate kill switch?' : 'Activate kill switch? All trading will stop.')) {
              apiFetch('/kill-switch', {
                method: 'POST',
                body: JSON.stringify({ activate: !killActive })
              }).then(() => setKillActive(!killActive));
            }
          }}
          className="px-4 py-2 rounded-lg font-medium"
          style={{ background: killActive ? '#34d399' : '#7f1d1d', color: 'white', fontSize: '14px' }}
        >
          {killActive ? 'Deactivate' : 'Activate'}
        </button>
      </div>

      {/* Alpaca Keys */}
      <div style={{ background: '#171c22', borderRadius: '10px', padding: '16px', border: '1px solid #2a3340' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e8eef4', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
          Alpaca Paper Keys
        </h3>
        <p style={{ fontSize: '14px', color: '#8b9aab', marginBottom: '8px' }}>
          Set <code style={{ background: '#0f1419', padding: '2px 6px', borderRadius: '4px' }}>ALPACA_API_KEY</code> and{' '}
          <code style={{ background: '#0f1419', padding: '2px 6px', borderRadius: '4px' }}>ALPACA_SECRET_KEY</code> in environment variables.
        </p>
        <p style={{ fontSize: '13px', color: '#fbbf24' }}>
          Without keys, orders are logged locally but not sent to Alpaca.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
function App() {
  const [loggedIn, setLoggedIn] = useState(!!getToken());
  const [segment, setSegment] = useState('Desk');
  const [session, setSession] = useState(null);
  const [killActive, setKillActive] = useState(false);

  useEffect(() => {
    if (!loggedIn) return;
    function loadSession() {
      fetch(`${API_BASE}/session`).then(r => r.json()).then(d => setSession(d)).catch(() => {});
    }
    function loadHealth() {
      fetch(`${API_BASE}/health`).then(r => r.json()).then(d => setKillActive(!!d.kill_switch)).catch(() => {});
    }
    loadSession();
    loadHealth();
    const timer = setInterval(() => { loadSession(); loadHealth(); }, 30000);
    return () => clearInterval(timer);
  }, [loggedIn]);

  if (!loggedIn) {
    return <LoginScreen onLogin={() => setLoggedIn(true)} />;
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f1419', color: '#e8eef4', display: 'flex', flexDirection: 'column' }}>
      <Header segment={segment} setSegment={setSegment} killActive={killActive} onLogout={() => { clearToken(); setLoggedIn(false); }} />
      <SegmentControl segment={segment} setSegment={setSegment} />
      <main style={{ flex: 1, overflowY: 'auto' }}>
        {segment === 'Desk' && <DeskSegment session={session} />}
        {segment === 'Trade' && <TradeSegment />}
        {segment === 'System' && <SystemSegment killActive={killActive} setKillActive={setKillActive} />}
      </main>
      <footer style={{ borderTop: '1px solid #2a3340', padding: '8px 24px', textAlign: 'center', fontSize: '12px', color: '#8b9aab' }}>
        InvestRight-US · Alpaca paper · 30s refresh
      </footer>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
