import React, { useMemo, useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { formatPercent } from '../utils/format';
import apiClient from '../services/axios';

const fmtPEN = (v) => `S/. ${Number(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtUSD = (v) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(v ?? 0));
const fmtAmt = (v, currency) => (currency === 'USD' ? fmtUSD(v) : fmtPEN(v));

const PositionsTab = ({ portfolio, holdings, summary, displayCurrency, onDisplayCurrencyChange }) => {
  const [fxRates, setFxRates] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const [totalTooltip, setTotalTooltip] = useState(null);
  const [switching, setSwitching] = useState(false);

  const fxFetchRef = useRef(false);
  useEffect(() => {
    if (fxFetchRef.current) return;
    let cancelled = false;
    const fetchFxRates = async () => {
      try {
        const response = await apiClient.get('/fx-rates/');
        if (cancelled) return;
        setFxRates(response.data);
        fxFetchRef.current = true;
      } catch {
        if (cancelled) return;
        fxFetchRef.current = true;
      }
    };
    fetchFxRates();
    return () => { cancelled = true; };
  }, []);

  const fxMid = Number(fxRates?.mid?.rate) || 1;
  const displayMode = (displayCurrency || 'NATIVE').toUpperCase(); // 'NATIVE' | 'PEN' | 'USD'
  const isNative = displayMode === 'NATIVE';

  const cashPEN = Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0);
  const cashUSD = Number(portfolio?.cash_balance_usd ?? 0);
  const hasCash = cashPEN > 0 || cashUSD > 0;

  const rows = useMemo(() => {
    return (holdings || []).map(h => {
      const qty = Number(h.quantity || 0);
      const stockCurrency = (h.stock?.currency || 'PEN').toUpperCase();
      const displayCur = isNative ? stockCurrency : displayMode;

      const price = Number(h.stock?.current_price ?? 0);
      const mktVal = Number(h.current_value ?? 0);
      const costBasis = Number(h.cost_basis ?? 0);
      const gl = Number(h.gain_loss ?? 0);
      const glPct = Number(h.gain_loss_percentage ?? 0);
      const priceChg = h.stock?.price_change != null ? Number(h.stock.price_change) : null;
      const priceChgPct = h.stock?.price_change_percent != null ? Number(h.stock.price_change_percent) : null;
      const dayChg = h.day_change != null ? Number(h.day_change) : null;
      const dayChgPct = h.day_change_percentage != null ? Number(h.day_change_percentage) : null;

      return { id: h.id, sym: h.stock?.symbol, name: h.stock?.name, qty, price, mktVal, costBasis, gl, glPct, priceChg, priceChgPct, dayChg, dayChgPct, displayCur, stockCurrency };
    });
  }, [holdings, isNative, displayMode]);

  // Full portfolio value in PEN and USD — computed client-side using fx mid rate
  const totalPEN = useMemo(() => {
    const posSum = rows.reduce((s, r) => s + (r.stockCurrency === 'USD' ? r.mktVal * fxMid : r.mktVal), 0);
    return posSum + cashPEN + cashUSD * fxMid;
  }, [rows, cashPEN, cashUSD, fxMid]);

  const totalUSD = useMemo(() => {
    const posSum = rows.reduce((s, r) => s + (r.stockCurrency === 'USD' ? r.mktVal : (fxMid > 0 ? r.mktVal / fxMid : 0)), 0);
    return posSum + cashUSD + (fxMid > 0 ? cashPEN / fxMid : 0);
  }, [rows, cashPEN, cashUSD, fxMid]);

  // Non-native: use backend-computed summary values
  const totalMktVal = isNative ? totalPEN : Number(summary?.total_value ?? (rows.reduce((s, r) => s + r.mktVal, 0) + (displayMode === 'USD' ? cashUSD : cashPEN)));
  const totalCostBasis = Number(summary?.cost_basis ?? rows.reduce((s, r) => s + r.costBasis, 0));
  const totalGL = Number(summary?.gain_loss ?? rows.reduce((s, r) => s + r.gl, 0));
  const totalGLPct = Number(summary?.gain_loss_percentage ?? (totalCostBasis ? (totalGL / totalCostBasis) * 100 : 0));
  const totalDayChg = Number(summary?.day_change ?? rows.reduce((s, r) => s + (r.dayChg || 0), 0));
  const totalDayChgPct = Number(summary?.day_change_percentage ?? 0);

  // Cash in display currency (for non-native Efectivo row and % calculations)
  const cashInDisplay = displayMode === 'USD' ? cashUSD + (fxMid > 0 ? cashPEN / fxMid : 0) : cashPEN + cashUSD * fxMid;

  const getRowPct = (r) => {
    if (isNative) {
      const valInPEN = r.stockCurrency === 'USD' ? r.mktVal * fxMid : r.mktVal;
      return totalPEN > 0 ? (valInPEN / totalPEN) * 100 : 0;
    }
    return totalMktVal > 0 ? (r.mktVal / totalMktVal) * 100 : 0;
  };

  const signClass = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return 'muted';
    if (n > 0) return 'up';
    if (n < 0) return 'down';
    return '';
  };

  const hasUsdStocks = (holdings || []).some(h => h.stock?.currency === 'USD');

  // 3-way toggle: NATIVE → PEN → USD → NATIVE
  const nextMode = displayMode === 'NATIVE' ? 'PEN' : displayMode === 'PEN' ? 'USD' : 'NATIVE';
  const toggleLabel = switching ? 'Convirtiendo…' : displayMode === 'NATIVE' ? 'Ver en S/' : displayMode === 'PEN' ? 'Ver en $' : 'Ver original';

  const handleToggle = async () => {
    if (!onDisplayCurrencyChange || switching) return;
    setSwitching(true);
    try {
      await onDisplayCurrencyChange(nextMode);
    } finally {
      setSwitching(false);
    }
  };

  const showTotalTooltip = (event, text) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTotalTooltip({
      text,
      top: rect.bottom + 8,
      left: rect.left,
    });
  };

  const hideTotalTooltip = () => setTotalTooltip(null);

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Detalles de posiciones</h3>
        <button
          className="btn xs ghost"
          onClick={handleToggle}
          disabled={switching}
          style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {toggleLabel}
        </button>
      </div>

      {hasUsdStocks && fxRates && (
        <div style={{ fontSize: 11, color: '#999', marginBottom: 12, fontStyle: 'italic', position: 'relative', display: 'inline-block' }}>
          <span
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            style={{ textDecoration: 'underline dotted', cursor: 'help', textDecorationColor: '#666' }}
          >
            * Usando tipo de cambio {fxRates.mid?.rate || 'N/A'} PEN/USD
          </span>
          {showTooltip && (
            <div style={{
              position: 'absolute', top: '100%', left: '0', marginTop: '8px', padding: '10px 14px',
              backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '6px',
              whiteSpace: 'nowrap', zIndex: 1000, fontSize: '11px', fontStyle: 'normal',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
            }}>
              <div style={{ marginBottom: '6px', color: '#aaa', fontWeight: 600 }}>Tipos de cambio actuales (PEN/USD):</div>
              <div style={{ color: '#fff', marginBottom: '2px' }}>Compra: {fxRates.compra?.rate || 'N/A'}</div>
              <div style={{ color: '#fff', marginBottom: '2px' }}>Venta: {fxRates.venta?.rate || 'N/A'}</div>
              <div style={{ color: '#4ade80', fontWeight: 600 }}>Promedio: {fxRates.mid?.rate || 'N/A'}</div>
              <div style={{ position: 'absolute', top: '-6px', left: '20px', width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderBottom: '6px solid #1a1a1a' }} />
            </div>
          )}
        </div>
      )}

      {(rows.length === 0 && !hasCash) ? (
        <p className="muted" style={{ fontSize: 11 }}>No hay posiciones activas.</p>
      ) : (
        <div className="scroll-pretty" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', fontSize: 11, lineHeight: 1.25 }}>
          <table className="table positions-table" style={{ minWidth: 1600, fontSize: 11 }}>
            <thead>
              <tr style={{ textAlign: 'left' }}>
                <th className="sticky-col" style={{ whiteSpace: 'nowrap', minWidth: 90 }}>Símbolo</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 380 }}>Descripción</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 70 }}>Cant.</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 100 }}>Precio</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio precio</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio precio %</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Valor de mercado</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio del día</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio del día %</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Costo base</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Gan./Pérdida</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Gan./Pérdida %</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>% de la cuenta</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td className="sticky-col" style={{ minWidth: 90 }}>{r.sym}</td>
                  <td style={{ minWidth: 380 }}>{r.name}</td>
                  <td style={{ minWidth: 70 }}>{r.qty}</td>
                  <td style={{ minWidth: 100 }}>{fmtAmt(r.price, r.displayCur)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.priceChg)}>
                    {r.priceChg == null ? '—' : fmtAmt(r.priceChg, r.displayCur)}
                  </td>
                  <td style={{ minWidth: 120 }} className={signClass(r.priceChgPct)}>
                    {r.priceChgPct == null ? '—' : formatPercent(r.priceChgPct)}
                  </td>
                  <td style={{ minWidth: 120 }}>{fmtAmt(r.mktVal, r.displayCur)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.dayChg)}>
                    {r.dayChg == null ? '—' : fmtAmt(r.dayChg, r.displayCur)}
                  </td>
                  <td style={{ minWidth: 120 }} className={signClass(r.dayChgPct)}>
                    {r.dayChgPct == null ? '—' : formatPercent(r.dayChgPct)}
                  </td>
                  <td style={{ minWidth: 120 }}>{fmtAmt(r.costBasis, r.displayCur)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.gl)}>{fmtAmt(r.gl, r.displayCur)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.glPct)}>{formatPercent(r.glPct)}</td>
                  <td style={{ minWidth: 120 }}>{formatPercent(getRowPct(r))}</td>
                </tr>
              ))}

              {/* Efectivo — single row, stacked values in native mode */}
              {hasCash && (
                <tr>
                  <td className="sticky-col">Efectivo</td>
                  <td></td>
                  <td>-</td>
                  <td></td>
                  <td></td>
                  <td></td>
                  <td>
                    {isNative ? (
                      <div style={{ lineHeight: 1.7 }}>
                        {cashPEN > 0 && <div>{fmtPEN(cashPEN)}</div>}
                        {cashUSD > 0 && <div>{fmtUSD(cashUSD)}</div>}
                        {cashPEN === 0 && cashUSD === 0 && <div>{fmtPEN(0)}</div>}
                      </div>
                    ) : (
                      fmtAmt(cashInDisplay, displayMode)
                    )}
                  </td>
                  <td>—</td>
                  <td>—</td>
                  <td>-</td>
                  <td>-</td>
                  <td>-</td>
                  <td>{isNative ? '—' : formatPercent(totalMktVal > 0 ? (cashInDisplay / totalMktVal) * 100 : 0)}</td>
                </tr>
              )}

              {/* Total row(s) */}
              {isNative ? (
                <>
                  <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <td className="sticky-col" style={{ fontWeight: 600 }}>
                      <span
                        onMouseEnter={(event) => showTotalTooltip(event, 'Total de la cuenta (convertido a S/)')}
                        onMouseLeave={hideTotalTooltip}
                        style={{ textDecoration: 'underline dotted', cursor: 'help', textDecorationColor: '#666' }}
                      >
                        Total de la cuenta (convertido a S/)
                      </span>
                    </td>
                    <td></td><td></td><td></td><td></td><td></td>
                    <td style={{ fontWeight: 600 }}>{fmtPEN(totalPEN)}</td>
                    <td></td><td></td><td></td><td></td><td></td><td></td>
                  </tr>
                  <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <td className="sticky-col" style={{ fontWeight: 600 }}>
                      <span
                        onMouseEnter={(event) => showTotalTooltip(event, 'Total de la cuenta (convertido a $)')}
                        onMouseLeave={hideTotalTooltip}
                        style={{ textDecoration: 'underline dotted', cursor: 'help', textDecorationColor: '#666' }}
                      >
                        Total de la cuenta (convertido a $)
                      </span>
                    </td>
                    <td></td><td></td><td></td><td></td><td></td>
                    <td style={{ fontWeight: 600 }}>{fmtUSD(totalUSD)}</td>
                    <td></td><td></td><td></td><td></td><td></td><td></td>
                  </tr>
                </>
              ) : (
                <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <td className="sticky-col" style={{ fontWeight: 600 }}>Total de la cuenta</td>
                  <td></td><td></td><td></td><td></td><td></td>
                  <td style={{ fontWeight: 600 }}>{fmtAmt(totalMktVal, displayMode)}</td>
                  <td className={signClass(totalDayChg)}>{fmtAmt(totalDayChg, displayMode)}</td>
                  <td className={signClass(totalDayChgPct)}>{formatPercent(totalDayChgPct)}</td>
                  <td>{fmtAmt(totalCostBasis, displayMode)}</td>
                  <td className={signClass(totalGL)}>{fmtAmt(totalGL, displayMode)}</td>
                  <td className={signClass(totalGLPct)}>{formatPercent(totalGLPct)}</td>
                  <td></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {totalTooltip && createPortal(
        <div style={{
          position: 'fixed',
          top: totalTooltip.top,
          left: totalTooltip.left,
          padding: '10px 14px',
          backgroundColor: '#1a1a1a',
          border: '1px solid #333',
          borderRadius: '6px',
          whiteSpace: 'nowrap',
          zIndex: 2000,
          fontSize: '11px',
          fontStyle: 'normal',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)',
          pointerEvents: 'none',
        }}>
          {totalTooltip.text}
          <div style={{
            position: 'absolute',
            top: '-6px',
            left: '20px',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            borderBottom: '6px solid #1a1a1a',
          }} />
        </div>,
        document.body
      )}
    </div>
  );
};

export default PositionsTab;
