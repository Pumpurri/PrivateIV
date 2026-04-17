import React, { useMemo, useState, useEffect, useRef } from 'react';
import { formatCurrency, formatPercent } from '../utils/format';
import apiClient from '../services/axios';

const PositionsTab = ({ portfolio, holdings, summary, displayCurrency, onDisplayCurrencyChange }) => {
  const [fxRates, setFxRates] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);
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
      } catch (error) {
        if (cancelled) return;
        console.error('Failed to fetch FX rates:', error);
        fxFetchRef.current = true;
      }
    };
    fetchFxRates();
    return () => { cancelled = true; };
  }, []);

  const rows = useMemo(() => {
    const totalValue = Number(summary?.total_value ?? portfolio?.total_value ?? 0);
    const fxMid = Number(fxRates?.mid?.rate) || 1;

    return (holdings || []).map(h => {
      const qty = Number(h.quantity || 0);
      const isUSD = h.stock?.currency === 'USD';
      const nativePrice = Number(h.stock?.current_price ?? 0);
      const price = Number(h.stock?.display_price ?? (isUSD ? nativePrice * fxMid : nativePrice));
      const mktVal = Number(h.current_value ?? (qty * price));
      const costBasis = Number(h.cost_basis ?? 0);
      const gl = Number(h.gain_loss ?? (mktVal - costBasis));
      const glPct = Number(h.gain_loss_percentage ?? 0);
      const pctOfAcct = totalValue ? (mktVal / totalValue) * 100 : 0;
      const priceChg = h.stock?.price_change != null ? Number(h.stock.price_change) : null;
      const priceChgPct = h.stock?.price_change_percent != null ? Number(h.stock.price_change_percent) : null;
      const dayChg = h.day_change != null ? Number(h.day_change) : null;
      const dayChgPct = h.day_change_percentage != null ? Number(h.day_change_percentage) : null;

      return { id: h.id, sym: h.stock?.symbol, name: h.stock?.name, qty, price, mktVal, costBasis, gl, glPct, pctOfAcct, priceChg, priceChgPct, dayChg, dayChgPct };
    });
  }, [portfolio, holdings, summary, fxRates]);

  const signClass = (v) => {
    const n = typeof v === 'number' ? v : Number.isFinite(v) ? Number(v) : NaN;
    if (Number.isNaN(n)) return 'muted';
    if (n > 0) return 'up';
    if (n < 0) return 'down';
    return '';
  };

  const cash = Number(summary?.cash_balance ?? portfolio?.cash_balance ?? 0);
  const totalMktVal = Number(summary?.total_value ?? (rows.reduce((s, r) => s + (Number(r.mktVal) || 0), 0) + cash));
  const totalCostBasis = Number(summary?.cost_basis ?? rows.reduce((s, r) => s + (Number(r.costBasis) || 0), 0));
  const totalGL = Number(summary?.gain_loss ?? rows.reduce((s, r) => s + (Number(r.gl) || 0), 0));
  const totalGLPct = Number(summary?.gain_loss_percentage ?? (totalCostBasis ? (totalGL / totalCostBasis) * 100 : 0));
  const totalDayChg = Number(summary?.day_change ?? rows.reduce((s, r) => s + (Number(r.dayChg) || 0), 0));
  const totalDayChgPct = Number(summary?.day_change_percentage ?? 0);

  const hasUsdStocks = (holdings || []).some(h => h.stock?.currency === 'USD');

  const activeCurrency = (summary?.summary_currency || displayCurrency || portfolio?.reporting_currency || 'PEN').toUpperCase();
  const isUSDView = activeCurrency === 'USD';

  const handleCurrencyToggle = async () => {
    if (!onDisplayCurrencyChange || switching) return;
    setSwitching(true);
    try {
      await onDisplayCurrencyChange(isUSDView ? 'PEN' : 'USD');
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Detalles de posiciones</h3>
        <button
          className="btn xs ghost"
          onClick={handleCurrencyToggle}
          disabled={switching}
          style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {switching ? 'Convirtiendo…' : isUSDView ? 'Ver en S/' : 'Ver en $'}
        </button>
      </div>

      {hasUsdStocks && fxRates && (
        <div style={{ fontSize: 11, color: '#999', marginBottom: 12, fontStyle: 'italic', position: 'relative', display: 'inline-block' }}>
          <span
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            style={{
              textDecoration: 'underline dotted',
              cursor: 'help',
              textDecorationColor: '#666'
            }}
          >
            * Usando tipo de cambio {fxRates.mid?.rate || 'N/A'} PEN/USD
          </span>
          {showTooltip && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: '0',
                marginTop: '8px',
                padding: '10px 14px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #333',
                borderRadius: '6px',
                whiteSpace: 'nowrap',
                zIndex: 1000,
                fontSize: '11px',
                fontStyle: 'normal',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
              }}
            >
              <div style={{ marginBottom: '6px', color: '#aaa', fontWeight: 600 }}>Tipos de cambio actuales (PEN/USD):</div>
              <div style={{ color: '#fff', marginBottom: '2px' }}>Compra: {fxRates.compra?.rate || 'N/A'}</div>
              <div style={{ color: '#fff', marginBottom: '2px' }}>Venta: {fxRates.venta?.rate || 'N/A'}</div>
              <div style={{ color: '#4ade80', fontWeight: 600 }}>Promedio: {fxRates.mid?.rate || 'N/A'}</div>
              <div
                style={{
                  position: 'absolute',
                  top: '-6px',
                  left: '20px',
                  width: 0,
                  height: 0,
                  borderLeft: '6px solid transparent',
                  borderRight: '6px solid transparent',
                  borderBottom: '6px solid #1a1a1a'
                }}
              />
            </div>
          )}
        </div>
      )}

      {(rows.length === 0 && cash <= 0) ? (
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
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio precio S/.</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio precio %</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Valor de mercado</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio del día S/.</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Cambio del día %</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Costo base</th>
                <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Gan./Pérdida S/.</th>
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
                  <td style={{ minWidth: 100 }}>{formatCurrency(r.price)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.priceChg)}>{r.priceChg == null ? '—' : formatCurrency(r.priceChg)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.priceChgPct)}>{r.priceChgPct == null ? '—' : formatPercent(r.priceChgPct)}</td>
                  <td style={{ minWidth: 120 }}>{formatCurrency(r.mktVal)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.dayChg)}>{r.dayChg == null ? '—' : formatCurrency(r.dayChg)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.dayChgPct)}>{r.dayChgPct == null ? '—' : formatPercent(r.dayChgPct)}</td>
                  <td style={{ minWidth: 120 }}>{formatCurrency(r.costBasis)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.gl)}>{formatCurrency(r.gl)}</td>
                  <td style={{ minWidth: 120 }} className={signClass(r.glPct)}>{formatPercent(r.glPct)}</td>
                  <td style={{ minWidth: 120 }}>{formatPercent(r.pctOfAcct)}</td>
                </tr>
              ))}

              {cash > 0 && (
                <tr>
                  <td className="sticky-col">Efectivo</td>
                  <td></td>
                  <td>-</td>
                  <td></td>
                  <td></td>
                  <td></td>
                  <td>{formatCurrency(cash)}</td>
                  <td>{formatCurrency(0)}</td>
                  <td>{formatPercent(0)}</td>
                  <td>-</td>
                  <td>-</td>
                  <td>-</td>
                  <td>{formatPercent(totalMktVal ? (cash / totalMktVal) * 100 : 0)}</td>
                </tr>
              )}

              <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                <td className="sticky-col" style={{ fontWeight: 600 }}>Total de la cuenta</td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
                <td style={{ fontWeight: 600 }}>{formatCurrency(totalMktVal)}</td>
                <td className={signClass(totalDayChg)}>{formatCurrency(totalDayChg)}</td>
                <td className={signClass(totalDayChgPct)}>{formatPercent(totalDayChgPct)}</td>
                <td>{formatCurrency(totalCostBasis)}</td>
                <td className={signClass(totalGL)}>{formatCurrency(totalGL)}</td>
                <td className={signClass(totalGLPct)}>{formatPercent(totalGLPct)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PositionsTab;
