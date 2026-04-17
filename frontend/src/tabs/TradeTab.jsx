import React from 'react';
import { createTransaction } from '../services/api';
import { useStockPrices } from '../contexts/StockPriceContext';

const TradeTab = ({ portfolio, holdings, onTransaction }) => {
  const formatPEN = React.useCallback((value) => (
    new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(Number(value ?? 0))
  ), []);
  const formatUSD = React.useCallback((value) => (
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value ?? 0))
  ), []);

  const [symbol, setSymbol] = React.useState('');
  const [open, setOpen] = React.useState(false);
  const [action, setAction] = React.useState('buy');
  const [quantity, setQuantity] = React.useState(1);
  const [orderType, setOrderType] = React.useState('market');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState('');
  const [step, setStep] = React.useState(1);
  const boxRef = React.useRef(null);
  const [hasPicked, setHasPicked] = React.useState(false);

  const { stocks = [], fetchStocks } = useStockPrices();
  const requestedStocksRef = React.useRef(false);
  React.useEffect(() => {
    if (stocks.length > 0) { requestedStocksRef.current = false; return; }
    if (requestedStocksRef.current) return;
    if (typeof fetchStocks === 'function') { requestedStocksRef.current = true; fetchStocks(); }
  }, [stocks.length, fetchStocks]);

  const searchStocks = React.useCallback((q) => {
    const s = (q || '').trim().toLowerCase();
    if (!s) return [];
    return stocks.filter(x => (x.symbol || '').toLowerCase().includes(s) || (x.name || '').toLowerCase().includes(s));
  }, [stocks]);
  const findStock = React.useCallback((sym) => {
    const s = (sym || '').trim().toLowerCase();
    return stocks.find(x => (x.symbol || '').toLowerCase() === s);
  }, [stocks]);

  React.useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => { document.removeEventListener('mousedown', onDoc); };
  }, []);

  const suggestions = React.useMemo(() => searchStocks(symbol).slice(0, 5), [symbol, searchStocks]);
  const selectedStock = React.useMemo(() => findStock(symbol), [symbol, findStock]);

  const isStockHeld = React.useMemo(() => {
    if (!selectedStock || !holdings || !Array.isArray(holdings)) return false;
    return holdings.some(h => {
      if (h.stock_id === selectedStock.id || h.stock?.id === selectedStock.id) return true;
      const hSymbol = (h.stock?.symbol || '').toLowerCase();
      const selSymbol = (selectedStock.symbol || '').toLowerCase();
      return hSymbol && selSymbol && hSymbol === selSymbol;
    });
  }, [selectedStock, holdings]);

  React.useEffect(() => {
    if (!isStockHeld && action === 'sell') setAction('buy');
  }, [isStockHeld, action]);

  const storageKey = React.useMemo(() => 'recentSymbols', []);
  const [recent, setRecent] = React.useState([]);
  React.useEffect(() => {
    try {
      let raw = localStorage.getItem(storageKey);
      let list = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(list) || list.length === 0) {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith('recentSymbols:')) {
            try {
              const scopedRaw = localStorage.getItem(key);
              const scopedList = scopedRaw ? JSON.parse(scopedRaw) : [];
              if (Array.isArray(scopedList) && scopedList.length > 0) { list = scopedList; break; }
            } catch {}
          }
        }
        if (Array.isArray(list) && list.length > 0) {
          try { localStorage.setItem(storageKey, JSON.stringify(list.slice(0, 5))); } catch {}
        }
      }
      if (Array.isArray(list)) setRecent(list.slice(0, 5));
      else setRecent([]);
    } catch { setRecent([]); }
  }, [storageKey]);

  const pushRecent = React.useCallback((sym) => {
    const s = String(sym || '').trim().toUpperCase();
    if (!s) return;
    setRecent((cur) => {
      const next = [s, ...cur.filter(x => x !== s)].slice(0, 5);
      try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch {}
      return next;
    });
  }, [storageKey]);

  // Native currency — no FX conversion anywhere
  const cashPEN = Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0);
  const cashUSD = Number(portfolio?.cash_balance_usd ?? 0);
  const isUSDStock = selectedStock?.currency === 'USD';
  const availableCash = isUSDStock ? cashUSD : cashPEN;
  const formatNative = isUSDStock ? formatUSD : formatPEN;
  const nativeTotal = Number(selectedStock?.current_price || 0) * quantity;
  const cannotAfford = hasPicked && selectedStock && action === 'buy' && nativeTotal > availableCash;

  const getMaxQuantity = React.useCallback(() => {
    if (!selectedStock || !hasPicked) return 999999;
    if (action === 'sell') {
      const holding = holdings?.find(h => h.stock_id === selectedStock.id || h.stock?.id === selectedStock.id);
      return holding?.quantity || 0;
    }
    const stockPrice = Number(selectedStock.current_price || 0);
    if (stockPrice <= 0) return 999999;
    return Math.floor(availableCash / stockPrice);
  }, [selectedStock, hasPicked, action, holdings, availableCash]);

  const handleQuantityChange = (e) => {
    const value = parseInt(e.target.value) || 0;
    setQuantity(Math.max(1, Math.min(value, getMaxQuantity())));
  };
  const adjustQuantity = (delta) => {
    setQuantity(prev => Math.max(1, Math.min(prev + delta, getMaxQuantity())));
  };

  const handleSubmitOrder = async () => {
    if (!selectedStock) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      await createTransaction({
        stock: selectedStock.id,
        quantity,
        transaction_type: action.toUpperCase(),
        cash_currency: selectedStock.currency || 'PEN',
        idempotency_key: crypto.randomUUID(),
        portfolio_id: portfolio?.id,
      });
      setSuccess(`Order executed! ${action} ${quantity} shares of ${selectedStock.symbol}`);
      setStep(3);
      try { if (typeof onTransaction === 'function') await onTransaction(); } catch {}
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to execute order');
      setStep(3);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Progress bar */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <div style={{ flex: 1, height: 4, background: step >= 1 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
        <div style={{ flex: 1, height: 4, background: step >= 2 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
        <div style={{ flex: 1, height: 4, background: step >= 3 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 8, fontSize: 12 }}>
        {['1. Ingresar orden', '2. Verificar orden', '3. Orden recibida'].map((label, i) => (
          <div key={label} style={{ textAlign: 'center', color: step >= i + 1 ? 'var(--text)' : 'var(--muted)', fontWeight: step === i + 1 ? 600 : 400 }}>{label}</div>
        ))}
      </div>

      {/* Step 1: Enter Order — cash header */}
      {step === 1 && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div className="muted" style={{ marginBottom: 6 }}>Efectivo disponible</div>
          <div style={{ display: 'flex', gap: 20, alignItems: 'baseline', flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: 20, fontWeight: 700 }}>S/ {cashPEN.toFixed(2)}</span>
              <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>soles</span>
            </div>
            {cashUSD > 0 && (
              <div>
                <span style={{ fontSize: 20, fontWeight: 700 }}>$ {cashUSD.toFixed(2)}</span>
                <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>dólares</span>
              </div>
            )}
          </div>

          <div className="trade-form" style={{ marginTop: 16 }}>
            <div className="grid" style={{ gap: 10, maxWidth: 520, margin: '0 auto' }}>
              <div ref={boxRef} style={{ position: 'relative' }}>
                <div className="muted" style={{ fontSize: 12 }}>Símbolo</div>
                <input
                  className="input"
                  placeholder="Ingresa símbolo"
                  value={symbol}
                  onChange={(e) => { setSymbol(e.target.value); setOpen(true); setHasPicked(false); }}
                  onFocus={() => setOpen(true)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      const chosen = suggestions?.length > 0 ? suggestions[0]?.symbol : selectedStock?.symbol;
                      if (chosen) { setSymbol(chosen); setHasPicked(true); pushRecent(chosen); setOpen(false); }
                    }
                  }}
                  autoComplete="off"
                />
                {open && suggestions.length > 0 && (
                  <div className="card" style={{ position: 'absolute', left: 0, right: 0, top: '100%', marginTop: 6, zIndex: 20, padding: 6 }}>
                    {suggestions.map((s) => (
                      <button
                        key={s.id || s.symbol}
                        className="btn xs"
                        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}
                        onClick={() => { setSymbol(s.symbol || ''); setHasPicked(true); pushRecent(s.symbol || ''); setOpen(false); }}
                      >
                        <span style={{ fontWeight: 700 }}>{s.symbol}</span>
                        <span className="muted" style={{ marginLeft: 8 }}>{s.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {recent.length > 0 && (
                <div>
                  <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Símbolos buscados recientemente</div>
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
                    {recent.map((s) => (
                      <button key={s} className="btn xs ghost" onClick={() => { setSymbol(s); setHasPicked(true); pushRecent(s); }}>{s}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Order Details */}
      {step === 1 && selectedStock && hasPicked && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{selectedStock.name}</div>
            <div className="muted" style={{ marginBottom: 8 }}>
              {selectedStock.symbol} • Precio de mercado: {isUSDStock ? formatUSD(selectedStock.current_price || 0) : formatPEN(selectedStock.current_price || 0)}
            </div>
          </div>

          <div className="grid" style={{ gap: 16, maxWidth: 520, margin: '0 auto' }}>
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Acción</div>
              <select className="input" value={action} onChange={(e) => setAction(e.target.value)}>
                <option value="buy">Comprar</option>
                <option value="sell" disabled={!isStockHeld}>Vender</option>
              </select>
            </div>

            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Cantidad</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button className="btn xs ghost" onClick={() => adjustQuantity(-1)} disabled={quantity <= 1} style={{ width: 32, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>−</button>
                <input className="input no-spin" type="number" min="1" max={getMaxQuantity()} step="1" value={quantity} onChange={handleQuantityChange} style={{ textAlign: 'center', width: 80 }} />
                <button className="btn xs ghost" onClick={() => adjustQuantity(1)} disabled={quantity >= getMaxQuantity()} style={{ width: 32, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>+</button>
              </div>
            </div>

            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Tipo de orden</div>
              <select className="input" value={orderType} onChange={(e) => setOrderType(e.target.value)}>
                <option value="market">Mercado</option>
              </select>
            </div>
          </div>

          {/* Order Summary */}
          <div style={{ marginTop: 16, padding: 12, background: 'var(--background-subtle)', borderRadius: 8 }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Total estimado</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>{formatNative(nativeTotal)}</div>
            {action === 'buy' && (
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                Saldo disponible en {isUSDStock ? 'dólares' : 'soles'}: {formatNative(availableCash)}
              </div>
            )}
            {cannotAfford && (
              <div style={{ fontSize: 11, color: '#ef4444', marginTop: 4 }}>
                Saldo insuficiente en {isUSDStock ? 'dólares ($)' : 'soles (S/)'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 2: Verify Order */}
      {step === 2 && selectedStock && hasPicked && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 18 }}>Verificar orden</h3>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>Revisa los detalles antes de confirmar</p>
          </div>
          <div style={{ maxWidth: 400, margin: '0 auto' }}>
            {[
              { label: 'Acción:', value: <span style={{ fontWeight: 600, color: action === 'buy' ? '#10b981' : '#ef4444', textTransform: 'uppercase' }}>{action === 'buy' ? 'COMPRAR' : 'VENDER'}</span> },
              { label: 'Símbolo:', value: selectedStock.symbol },
              { label: 'Cantidad:', value: `${quantity} acciones` },
              { label: 'Precio por acción:', value: formatNative(selectedStock.current_price || 0) },
              { label: 'Total:', value: formatNative(nativeTotal), bold: true },
            ].map(({ label, value, bold }, i, arr) => (
              <div key={label} className="row" style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none', marginBottom: i === arr.length - 1 ? 20 : 0 }}>
                <span className={bold ? '' : 'muted'} style={bold ? { fontWeight: 600 } : {}}>{label}</span>
                <span style={{ fontWeight: bold ? 700 : 600, fontSize: bold ? 18 : undefined }}>{value}</span>
              </div>
            ))}
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'var(--background-subtle)', borderRadius: 8 }}>
              <span className="muted">Saldo disponible ({isUSDStock ? 'USD' : 'PEN'}):</span>
              <span style={{ fontWeight: 600 }}>{formatNative(availableCash)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Order Received / Failed */}
      {step === 3 && (
        <div className="card" style={{ padding: 32, marginTop: 16, textAlign: 'center' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{ width: 64, height: 64, borderRadius: '50%', backgroundColor: success ? '#10b981' : '#ef4444', margin: '0 auto 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, color: 'white' }}>
              {success ? '✓' : '✗'}
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 700 }}>{success ? 'Orden Recibida' : 'Orden Fallida'}</h2>
            <p className="muted" style={{ margin: 0, fontSize: 16 }}>
              {success ? 'Gracias. Hemos recibido tu orden.' : 'Lo sentimos. Tu orden no pudo ser procesada.'}
            </p>
          </div>
          {success && (
            <div style={{ padding: '16px 24px', background: 'var(--background-subtle)', borderRadius: 8, marginBottom: 24 }}>
              <div className="muted" style={{ fontSize: 14, marginBottom: 8 }}>Detalles de la orden:</div>
              <div style={{ fontWeight: 600 }}>{action === 'buy' ? 'COMPRAR' : 'VENDER'} {quantity} acciones de {selectedStock?.symbol}</div>
            </div>
          )}
          {error && (
            <div style={{ padding: '12px 16px', background: 'rgba(239,68,68,0.1)', borderRadius: 8, color: '#ef4444', marginBottom: 24, fontSize: 14 }}>
              {error}
            </div>
          )}
          <button
            className="btn primary"
            onClick={() => { setSymbol(''); setQuantity(1); setAction('buy'); setOpen(false); setHasPicked(false); setStep(1); setSuccess(''); setError(''); }}
            style={{ minWidth: 160 }}
          >
            Nueva Orden
          </button>
        </div>
      )}

      {step !== 3 && error && (
        <div className="card" style={{ padding: 12, marginTop: 16, background: 'var(--error-background)', color: 'var(--error)' }}>{error}</div>
      )}

      {step !== 3 && (
        <div className="row" style={{ gap: 10, justifyContent: 'flex-end', marginTop: 12 }}>
          {step === 2 ? (
            <>
              <button className="btn ghost" onClick={() => setStep(1)}>Volver</button>
              <button className="btn primary" disabled={submitting} onClick={handleSubmitOrder}>
                {submitting ? 'Ejecutando...' : 'Confirmar orden'}
              </button>
            </>
          ) : (
            <>
              <button className="btn ghost" onClick={() => { setSymbol(''); setHasPicked(false); setOpen(false); setStep(1); }}>Limpiar</button>
              <button
                className={`btn ${!hasPicked || !selectedStock || submitting || cannotAfford ? 'ghost' : 'primary'}`}
                disabled={!hasPicked || !selectedStock || submitting || cannotAfford}
                onClick={() => setStep(2)}
              >
                Revisar orden
              </button>
            </>
          )}
        </div>
      )}
    </>
  );
};

export default TradeTab;
