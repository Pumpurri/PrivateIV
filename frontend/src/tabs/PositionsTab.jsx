import React, { useMemo, useState, useEffect, useRef } from 'react';
import { formatCurrency, formatPercent } from '../utils/format';
import apiClient from '../services/axios';

const PositionsTab = ({ portfolio, holdings, transactions = [] }) => {
  const [fxRates, setFxRates] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);

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

  const costBasisMap = useMemo(() => {
    if (!Array.isArray(transactions)) return new Map();
    const sorted = [...transactions].filter(tx => tx && tx.stock_symbol && tx.transaction_type && tx.quantity)
      .sort((a, b) => {
        const aTime = new Date(a.timestamp || 0).getTime();
        const bTime = new Date(b.timestamp || 0).getTime();
        return aTime - bTime;
      });

    const map = new Map();

    sorted.forEach((tx) => {
      const type = String(tx.transaction_type || '').toUpperCase();
      if (type !== 'BUY' && type !== 'SELL') return;

      const symbol = String(tx.stock_symbol || '').toUpperCase();
      if (!symbol) return;

      const qty = Number(tx.quantity || 0);
      if (!Number.isFinite(qty) || qty <= 0) return;

      let fx = tx.fx_rate != null && tx.fx_rate !== '' ? Number(tx.fx_rate) : 1;
      if (!Number.isFinite(fx) || fx <= 0) fx = 1;
      const amountNativeVal = tx.amount != null ? Number(tx.amount) : Number(tx.executed_price || 0) * qty;
      if (!Number.isFinite(amountNativeVal)) return;
      const amountNative = amountNativeVal;
      const baseAmountRaw = amountNative * fx;
      const baseAmount = Number.isFinite(baseAmountRaw) ? baseAmountRaw : amountNative;

      const entry = map.get(symbol) || { qty: 0, cost: 0 };

      if (type === 'BUY') {
        entry.cost = (entry.cost || 0) + baseAmount;
        entry.qty = (entry.qty || 0) + qty;
      } else {
        const existingQty = entry.qty || 0;
        if (existingQty <= 0) {
          // No existing quantity tracked; skip cost adjustment but ensure quantity doesn't go wildly negative
          entry.qty = existingQty - qty;
        } else {
          const avgCost = entry.cost / existingQty;
          const sharesSold = Math.min(qty, existingQty);
          entry.cost = entry.cost - (avgCost * sharesSold);
          entry.qty = Math.max(0, existingQty - sharesSold);
          if (Math.abs(entry.cost) < 1e-4) entry.cost = 0;
          if (Math.abs(entry.qty) < 1e-4) entry.qty = 0;
        }
      }

      // Normalize to 2 decimals to avoid float drift
      entry.cost = Number.isFinite(entry.cost) ? Math.round(entry.cost * 100) / 100 : 0;
      entry.qty = Number.isFinite(entry.qty) ? entry.qty : 0;

      map.set(symbol, entry);
    });

    return map;
  }, [transactions]);

  const rows = useMemo(() => {
    const totalValue = Number(portfolio?.total_value || 0);

    return (holdings || []).map(h => {
      const qty = Number(h.quantity || 0);
      const price = Number(h.stock?.current_price ?? 0);
      const mktVal = Number(h.current_value ?? (qty * price));
      const symbol = String(h.stock?.symbol || '').toUpperCase();
      const derived = costBasisMap.get(symbol);
      const derivedMatches = derived && Number.isFinite(derived.cost) && Number.isFinite(derived.qty) &&
        Math.round(derived.qty) === qty;
      const derivedCost = derivedMatches ? derived.cost : null;
      const baseCost = h?.cost_basis != null ? Number(h.cost_basis) : null;
      const fallbackCost = Number(h.average_purchase_price || 0) * qty;

      const costBasisCandidates = [derivedCost, baseCost, fallbackCost];
      let costBasis = 0;
      for (const cand of costBasisCandidates) {
        if (cand != null && Number.isFinite(cand) && cand > 0) {
          costBasis = cand;
          break;
        }
      }
      if (!costBasis && fallbackCost) costBasis = fallbackCost;

      costBasis = Number.isFinite(costBasis) ? Math.round(costBasis * 100) / 100 : 0;

      const gl = mktVal - costBasis;
      const glPct = costBasis ? (gl / costBasis) * 100 : 0;
      const pctOfAcct = totalValue ? (mktVal / totalValue) * 100 : 0;

      // Use real price change data from backend
      const priceChg = h.stock?.price_change != null ? Number(h.stock.price_change) : null;
      const priceChgPct = h.stock?.price_change_percent != null ? Number(h.stock.price_change_percent) : null;

      // Day change: calculate based on price change applied to current market value
      const dayChg = priceChg != null && qty ? priceChg * qty : null;
      const dayChgPct = priceChgPct; // Same percentage applies to position

      return { id: h.id, sym: h.stock?.symbol, name: h.stock?.name, qty, price, mktVal, costBasis, gl, glPct, pctOfAcct, priceChg, priceChgPct, dayChg, dayChgPct };
    });
  }, [portfolio, holdings, costBasisMap]);

  const signClass = (v) => {
    const n = typeof v === 'number' ? v : Number.isFinite(v) ? Number(v) : NaN;
    if (Number.isNaN(n)) return 'muted';
    if (n > 0) return 'up';
    if (n < 0) return 'down';
    return '';
  };

  const cash = Number(portfolio?.cash_balance || 0);
  const totalCostBasis = rows.reduce((sum, r) => sum + (Number(r.costBasis) || 0), 0);
  const totalGL = rows.reduce((sum, r) => sum + (Number(r.gl) || 0), 0);
  const totalGLPct = totalCostBasis ? (totalGL / totalCostBasis) * 100 : 0;
  const rowsMktVal = rows.reduce((sum, r) => sum + (Number(r.mktVal) || 0), 0);
  const totalMktVal = rowsMktVal + cash;
  const totalDayChg = rows.reduce((sum, r) => sum + (Number(r.dayChg) || 0), 0);
  const totalDayChgPct = totalMktVal ? (totalDayChg / totalMktVal) * 100 : 0;

  const hasUsdStocks = (holdings || []).some(h => h.stock?.currency === 'USD');

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Detalles de posiciones</h3>
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
                  {/* Símbolo */}
                  <td className="sticky-col">Efectivo</td>
                  {/* Descripción */}
                  <td></td>
                  {/* Cant. */}
                  <td>-</td>
                  {/* Precio */}
                  <td></td>
                  {/* Cambio precio $ */}
                  <td></td>
                  {/* Cambio precio % */}
                  <td></td>
                  {/* Valor de mercado */}
                  <td>{formatCurrency(cash)}</td>
                  {/* Cambio del día $ */}
                  <td>{formatCurrency(0)}</td>
                  {/* Cambio del día % */}
                  <td>{formatPercent(0)}</td>
                  {/* Costo base */}
                  <td>-</td>
                  {/* Gan./Pérdida $ */}
                  <td>-</td>
                  {/* Gan./Pérdida % */}
                  <td>-</td>
                  {/* % de la cuenta */}
                  <td>{formatPercent(portfolio?.total_value ? (cash / portfolio.total_value) * 100 : 0)}</td>
                </tr>
              )}

              <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                {/* Símbolo */}
                <td className="sticky-col" style={{ fontWeight: 600 }}>Total de la cuenta</td>
                {/* Descripción */}
                <td></td>
                {/* Cant. */}
                <td></td>
                {/* Precio */}
                <td></td>
                {/* Cambio precio $ */}
                <td></td>
                {/* Cambio precio % */}
                <td></td>
                {/* Valor de mercado */}
                <td style={{ fontWeight: 600 }}>{formatCurrency(totalMktVal || portfolio?.total_value || 0)}</td>
                {/* Cambio del día $ */}
                <td className={signClass(totalDayChg)}>{formatCurrency(totalDayChg)}</td>
                {/* Cambio del día % */}
                <td className={signClass(totalDayChgPct)}>{formatPercent(totalDayChgPct)}</td>
                {/* Costo base */}
                <td>{formatCurrency(totalCostBasis)}</td>
                {/* Gan./Pérdida $ */}
                <td className={signClass(totalGL)}>{formatCurrency(totalGL)}</td>
                {/* Gan./Pérdida % */}
                <td className={signClass(totalGLPct)}>{formatPercent(totalGLPct)}</td>
                {/* % de la cuenta */}
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
