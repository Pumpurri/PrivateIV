import React from 'react';
// Trade shows prices in USD for now
import { createTransaction, getFXRates } from '../services/api';
import { useStockPrices } from '../contexts/StockPriceContext';

const TradeTab = ({ portfolio, holdings, onTransaction }) => {
  const formatCurrency = React.useCallback((value) => (
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
  const [step, setStep] = React.useState(1); // 1: Enter Order, 2: Verify Order, 3: Order Received
  const boxRef = React.useRef(null);
  // Only show totals after a user picks a concrete ticker (not just typing)
  const [hasPicked, setHasPicked] = React.useState(false);

  const { stocks = [], fetchStocks } = useStockPrices();
  const requestedStocksRef = React.useRef(false);
  React.useEffect(() => {
    if (stocks.length > 0) {
      requestedStocksRef.current = false;
      return;
    }
    if (requestedStocksRef.current) return;
    if (typeof fetchStocks === 'function') {
      requestedStocksRef.current = true;
      fetchStocks();
    }
  }, [stocks.length, fetchStocks]);
  const searchStocks = React.useCallback((q) => {
    const s = (q || '').trim().toLowerCase();
    if (!s) return [];
    return stocks.filter(x => (
      (x.symbol || '').toLowerCase().includes(s) ||
      (x.name || '').toLowerCase().includes(s)
    ));
  }, [stocks]);
  const findStock = React.useCallback((sym) => {
    const s = (sym || '').trim().toLowerCase();
    return stocks.find(x => (x.symbol || '').toLowerCase() === s);
  }, [stocks]);

  React.useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => { document.removeEventListener('mousedown', onDoc); };
  }, []);

  const suggestions = React.useMemo(() => {
    return searchStocks(symbol).slice(0, 5);
  }, [symbol, searchStocks]);

  const selectedStock = React.useMemo(() => {
    return findStock(symbol);
  }, [symbol, findStock]);

  // Check if the selected stock is held in the portfolio
  const isStockHeld = React.useMemo(() => {
    if (!selectedStock || !holdings || !Array.isArray(holdings)) return false;
    return holdings.some(h => {
      // Check by stock ID or by symbol match
      if (h.stock_id === selectedStock.id || h.stock?.id === selectedStock.id) return true;
      const hSymbol = (h.stock?.symbol || '').toLowerCase();
      const selSymbol = (selectedStock.symbol || '').toLowerCase();
      return hSymbol && selSymbol && hSymbol === selSymbol;
    });
  }, [selectedStock, holdings]);

  // Reset action to "buy" if stock is not held and action is "sell"
  React.useEffect(() => {
    if (!isStockHeld && action === 'sell') {
      setAction('buy');
    }
  }, [isStockHeld, action]);

  // Recently searched symbols (global), newest on the left, max 5
  const storageKey = React.useMemo(() => 'recentSymbols', []);
  const [recent, setRecent] = React.useState([]);
  React.useEffect(() => {
    try {
      let raw = localStorage.getItem(storageKey);
      let list = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(list) || list.length === 0) {
        // Migrate from any old scoped keys (recentSymbols:<id>) if present
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith('recentSymbols:')) {
            try {
              const scopedRaw = localStorage.getItem(key);
              const scopedList = scopedRaw ? JSON.parse(scopedRaw) : [];
              if (Array.isArray(scopedList) && scopedList.length > 0) {
                list = scopedList;
                break;
              }
            } catch {}
          }
        }
        // Persist migrated list to global key if found
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

  const [cash, setCash] = React.useState(Number(portfolio?.cash_balance || 0));
  React.useEffect(() => { setCash(Number(portfolio?.cash_balance || 0)); }, [portfolio?.cash_balance]);

  // FX rates for USD->PEN conversion
  const [fxRates, setFxRates] = React.useState({ compra: null, venta: null, mid: null });
  const fxFetchRef = React.useRef(false);
  React.useEffect(() => {
    if (fxFetchRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getFXRates();
        if (cancelled) return;
        setFxRates({
          compra: data.compra?.rate ? parseFloat(data.compra.rate) : 3.46,
          venta: data.venta?.rate ? parseFloat(data.venta.rate) : 3.50,
          mid: data.mid?.rate ? parseFloat(data.mid.rate) : 3.48,
        });
        fxFetchRef.current = true;
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to fetch FX rates:', err);
        setFxRates({ compra: 3.46, venta: 3.50, mid: 3.48 });
        fxFetchRef.current = true;
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Get appropriate FX rate based on action (buy uses venta, sell uses compra)
  const fxRate = action === 'buy' ? fxRates.venta : fxRates.compra;

  // Get max quantity based on action and constraints
  const getMaxQuantity = React.useCallback(() => {
    if (!selectedStock || !hasPicked) return 999999;

    if (action === 'sell') {
      // For sell: max is the number of shares held
      const holding = holdings?.find(h =>
        h.stock_id === selectedStock.id || h.stock?.id === selectedStock.id
      );
      return holding?.quantity || 0;
    } else {
      // For buy: max is based on available cash
      const stockPrice = selectedStock.current_price || 0;
      if (stockPrice <= 0) return 999999;

      const totalUSD = stockPrice;
      const totalPEN = selectedStock.currency === 'USD' ? totalUSD * fxRate : totalUSD;

      if (totalPEN <= 0) return 999999;
      return Math.floor(cash / totalPEN);
    }
  }, [selectedStock, hasPicked, action, holdings, cash, fxRate]);

  const handleQuantityChange = (e) => {
    const value = parseInt(e.target.value) || 0;
    const maxQty = getMaxQuantity();
    setQuantity(Math.max(1, Math.min(value, maxQty)));
  };

  const adjustQuantity = (delta) => {
    setQuantity(prev => {
      const maxQty = getMaxQuantity();
      const newQty = prev + delta;
      return Math.max(1, Math.min(newQty, maxQty));
    });
  };

  const handleSubmitOrder = async () => {
    if (!selectedStock) return;

    setSubmitting(true);
    setError('');
    setSuccess('');

    try {
      const transaction = await createTransaction({
        stock: selectedStock.id,
        quantity: quantity,
        transaction_type: action.toUpperCase(),
        idempotency_key: crypto.randomUUID(),
        portfolio_id: portfolio?.id,
      });

      setSuccess(`Order executed! ${action} ${quantity} shares of ${selectedStock.symbol}`);
      setStep(3);

      // Notify parent to refresh portfolio/holdings/transactions (cash updates flow down via props)
      try {
        if (typeof onTransaction === 'function') {
          await onTransaction();
        }
      } catch {}

    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to execute order');
      setStep(3);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <div style={{ flex: 1, height: 4, background: step >= 1 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
        <div style={{ flex: 1, height: 4, background: step >= 2 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
        <div style={{ flex: 1, height: 4, background: step >= 3 ? 'var(--primary-600)' : 'var(--border)', borderRadius: 999 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 8, fontSize: 12 }}>
        <div style={{ textAlign: 'center', color: step >= 1 ? 'var(--text)' : 'var(--muted)', fontWeight: step === 1 ? 600 : 400 }}>1. Ingresar orden</div>
        <div style={{ textAlign: 'center', color: step >= 2 ? 'var(--text)' : 'var(--muted)', fontWeight: step === 2 ? 600 : 400 }}>2. Verificar orden</div>
        <div style={{ textAlign: 'center', color: step >= 3 ? 'var(--text)' : 'var(--muted)', fontWeight: step === 3 ? 600 : 400 }}>3. Orden recibida</div>
      </div>
      {/* Step 1: Enter Order */}
      {step === 1 && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div className="muted" style={{ marginBottom: 6 }}>Efectivo y equivalentes disponibles</div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{formatCurrency(cash)}</div>

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
                      let chosen = null;
                      if (suggestions && suggestions.length > 0) chosen = suggestions[0]?.symbol || null;
                      else if (selectedStock) chosen = selectedStock.symbol;
                      if (chosen) {
                        setSymbol(chosen);
                        setHasPicked(true);
                        pushRecent(chosen);
                        setOpen(false);
                      }
                    }
                  }}
                  autoComplete="off"
                />
                {open && suggestions.length > 0 && (
                  <div
                    className="card"
                    style={{ position: 'absolute', left: 0, right: 0, top: '100%', marginTop: 6, zIndex: 20, padding: 6 }}
                  >
                    {suggestions.map((s) => (
                      <button
                        key={s.id || s.symbol}
                        className="btn xs"
                        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 4 }}
                        onClick={() => {
                          const sym = s.symbol || '';
                          setSymbol(sym);
                          setHasPicked(true);
                          pushRecent(sym);
                          setOpen(false);
                        }}
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

      {/* Order Details - shows after selecting a symbol in step 1 */}
      {step === 1 && selectedStock && hasPicked && (
        <div className="card" style={{ padding: 16, marginTop: 16, position: 'relative' }}>
          {/* FX Rate Badge - top right corner of this card, only for USD stocks */}
          {selectedStock.currency === 'USD' && fxRate && (
            <div style={{
              position: 'absolute',
              top: 16,
              right: 16,
              fontSize: 11,
              textAlign: 'center'
            }}>
              <div className="muted" style={{ fontSize: 10, marginBottom: 2 }}>
                Tipo de cambio {action === 'buy' ? '(venta)' : '(compra)'}
              </div>
              <div style={{ fontWeight: 600 }}>
                S/. {fxRate.toFixed(3)}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
              {selectedStock.name}
            </div>
            <div className="muted" style={{ marginBottom: 8 }}>
              {selectedStock.symbol} • Precio de mercado: {selectedStock.currency === 'USD' ? formatUSD(selectedStock.current_price || 0) : formatCurrency(selectedStock.current_price || 0)}
            </div>
          </div>

          <div className="grid" style={{ gap: 16, maxWidth: 520, margin: '0 auto' }}>
            {/* Action Dropdown */}
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Acción</div>
              <select
                className="input"
                value={action}
                onChange={(e) => setAction(e.target.value)}
              >
                <option value="buy">Comprar</option>
                <option value="sell" disabled={!isStockHeld}>Vender</option>
              </select>
            </div>

            {/* Quantity with +/- controls */}
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Cantidad</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  className="btn xs ghost"
                  onClick={() => adjustQuantity(-1)}
                  disabled={quantity <= 1}
                  style={{ width: 32, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  −
                </button>
                <input
                  className="input no-spin"
                  type="number"
                  min="1"
                  max={getMaxQuantity()}
                  step="1"
                  value={quantity}
                  onChange={handleQuantityChange}
                  style={{ textAlign: 'center', width: 80 }}
                />
                <button
                  className="btn xs ghost"
                  onClick={() => adjustQuantity(1)}
                  disabled={quantity >= getMaxQuantity()}
                  style={{ width: 32, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  +
                </button>
              </div>
            </div>

            {/* Order Type Dropdown */}
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Tipo de orden</div>
              <select
                className="input"
                value={orderType}
                onChange={(e) => setOrderType(e.target.value)}
              >
                <option value="market">Mercado</option>
              </select>
            </div>
          </div>

          {/* Order Summary — only after a specific ticker is picked */}
          {hasPicked && (() => {
            const stockPrice = selectedStock.current_price || 0;
            const totalUSD = stockPrice * quantity;
            const totalPEN = selectedStock.currency === 'USD' ? totalUSD * fxRate : totalUSD;
            const isUSD = selectedStock.currency === 'USD';
            return (
              <div style={{ marginTop: 16, padding: 12, background: 'var(--background-subtle)', borderRadius: 8 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Total estimado</div>
                <div style={{ fontSize: 16, fontWeight: 600 }}>
                  {formatCurrency(totalPEN)}
                </div>
                {isUSD && fxRate && (
                  <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                    Aplicando TC
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* Step 2: Verify Order */}
      {step === 2 && selectedStock && hasPicked && (() => {
        const stockPrice = selectedStock.current_price || 0;
        const totalUSD = stockPrice * quantity;
        const totalPEN = selectedStock.currency === 'USD' ? totalUSD * fxRate : totalUSD;
        const isUSD = selectedStock.currency === 'USD';

        return (
          <div className="card" style={{ padding: 16, marginTop: 16 }}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <h3 style={{ margin: '0 0 8px', fontSize: 18 }}>Verificar orden</h3>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>Revisa los detalles antes de confirmar</p>
            </div>

            <div style={{ maxWidth: 400, margin: '0 auto' }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="muted">Acción:</span>
                <span
                  style={{
                    fontWeight: 600,
                    color: action === 'buy' ? '#10b981' : '#ef4444',
                    textTransform: 'uppercase'
                  }}
                >
                  {action === 'buy' ? 'COMPRAR' : 'VENDER'}
                </span>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="muted">Símbolo:</span>
                <span style={{ fontWeight: 600 }}>{selectedStock.symbol}</span>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="muted">Cantidad:</span>
                <span style={{ fontWeight: 600 }}>{quantity} acciones</span>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="muted">Precio por acción:</span>
                <span style={{ fontWeight: 600 }}>
                  {isUSD ? formatUSD(stockPrice) : formatCurrency(stockPrice)}
                </span>
              </div>

              {/* Show subtotal in USD for USD stocks */}
              {isUSD && (
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                  <span className="muted">Subtotal (USD):</span>
                  <span style={{ fontWeight: 600 }}>{formatUSD(totalUSD)}</span>
                </div>
              )}

              {/* Show FX rate for USD stocks */}
              {isUSD && fxRate && (
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                  <span className="muted">Tipo de cambio {action === 'buy' ? '(venta)' : '(compra)'}:</span>
                  <span style={{ fontWeight: 600 }}>S/. {fxRate.toFixed(3)}</span>
                </div>
              )}

              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, padding: '12px 0' }}>
                <span style={{ fontWeight: 600 }}>Total:</span>
                <span style={{ fontWeight: 700, fontSize: 18 }}>
                  {formatCurrency(totalPEN)}
                </span>
              </div>

              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'var(--background-subtle)', borderRadius: 8 }}>
                <span className="muted">Efectivo disponible:</span>
                <span style={{ fontWeight: 600 }}>{formatCurrency(cash)}</span>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Step 3: Order Received */}
      {step === 3 && (
        <div className="card" style={{ padding: 32, marginTop: 16, textAlign: 'center' }}>
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: '50%',
                backgroundColor: success ? '#10b981' : '#ef4444',
                margin: '0 auto 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 24,
                color: 'white'
              }}
            >
              {success ? '✓' : '✗'}
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 700 }}>
              {success ? 'Orden Recibida' : 'Orden Fallida'}
            </h2>
            <p className="muted" style={{ margin: 0, fontSize: 16 }}>
              {success
                ? 'Gracias. Hemos recibido tu orden.'
                : 'Lo sentimos. Tu orden no pudo ser procesada.'
              }
            </p>
          </div>

          {success && (
            <div style={{ padding: '16px 24px', background: 'var(--background-subtle)', borderRadius: 8, marginBottom: 24 }}>
              <div className="muted" style={{ fontSize: 14, marginBottom: 8 }}>Detalles de la orden:</div>
              <div style={{ fontWeight: 600 }}>
                {action === 'buy' ? 'COMPRAR' : 'VENDER'} {quantity} acciones de {selectedStock?.symbol}
              </div>
            </div>
          )}

          <button
            className="btn primary"
            onClick={() => {
              setSymbol('');
              setQuantity(1);
              setAction('buy');
              setOpen(false);
              setHasPicked(false);
              setStep(1);
              setSuccess('');
              setError('');
            }}
            style={{ minWidth: 160 }}
          >
            Nueva Orden
          </button>
        </div>
      )}

      {/* Error/Success Messages - only show in step 1 and 2 */}
      {step !== 3 && error && (
        <div className="card" style={{ padding: 12, marginTop: 16, background: 'var(--error-background)', color: 'var(--error)' }}>
          {error}
        </div>
      )}

      {step !== 3 && success && (
        <div className="card" style={{ padding: 12, marginTop: 16, background: 'var(--success-background)', color: 'var(--success)' }}>
          {success}
        </div>
      )}

      {/* Actions outside the card */}
      {step !== 3 && (
        <div className="row" style={{ gap: 10, justifyContent: 'flex-end', marginTop: 12 }}>
          {step === 2 ? (
            <>
              <button className="btn ghost" onClick={() => setStep(1)}>
                Volver
              </button>
              <button
                className="btn primary"
                disabled={submitting}
                onClick={handleSubmitOrder}
              >
                {submitting ? 'Ejecutando...' : 'Confirmar orden'}
              </button>
            </>
          ) : (
            <>
              <button className="btn ghost" onClick={() => { setSymbol(''); setHasPicked(false); setOpen(false); setStep(1); }}>
                Limpiar
              </button>
              <button
                className={`btn ${(() => {
                  const isDisabled = !hasPicked || !selectedStock || submitting || (() => {
                    if (!selectedStock || !hasPicked || action === 'sell') return false;
                    const stockPrice = selectedStock.current_price || 0;
                    const totalUSD = stockPrice * quantity;
                    const totalPEN = selectedStock.currency === 'USD' ? totalUSD * fxRate : totalUSD;
                    return totalPEN > cash;
                  })();
                  return isDisabled ? 'ghost' : 'primary';
                })()}`}
                disabled={!hasPicked || !selectedStock || submitting || (() => {
                  if (!selectedStock || !hasPicked || action === 'sell') return false;
                  const stockPrice = selectedStock.current_price || 0;
                  const totalUSD = stockPrice * quantity;
                  const totalPEN = selectedStock.currency === 'USD' ? totalUSD * fxRate : totalUSD;
                  return totalPEN > cash;
                })()}
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
