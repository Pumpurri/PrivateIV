import React, { useMemo, useState } from 'react';
import DatePicker from '../components/DatePicker';
import { formatCurrency, formatNumber } from '../utils/format';

const HistoryTab = ({ transactions = [] }) => {
  const [histRange, setHistRange] = useState('LAST_6M');
  const [histSymbol, setHistSymbol] = useState('');
  const [histFrom, setHistFrom] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 6); return d.toISOString().split('T')[0];
  });
  const [histTo, setHistTo] = useState(() => new Date().toISOString().split('T')[0]);
  const [histTypes, setHistTypes] = useState({ buy: false, sell: false, contribution: false, withdrawal: false });
  const toggleHistType = (key) => setHistTypes(s => ({ ...s, [key]: !s[key] }));

  const rangeLabel = useMemo(() => {
    const now = new Date();
    let fromD = null;
    let toD = null;
    switch (histRange) {
      case 'LAST_1D': {
        toD = now;
        fromD = new Date(now); fromD.setDate(now.getDate() - 1);
        break;
      }
      case 'LAST_7D': {
        toD = now;
        fromD = new Date(now); fromD.setDate(now.getDate() - 7);
        break;
      }
      case 'LAST_14D': {
        toD = now;
        fromD = new Date(now); fromD.setDate(now.getDate() - 14);
        break;
      }
      case 'CURRENT_MONTH': {
        toD = now;
        fromD = new Date(now.getFullYear(), now.getMonth(), 1);
        break;
      }
      case 'PREVIOUS_MONTH': {
        const firstPrev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const lastPrev = new Date(now.getFullYear(), now.getMonth(), 0);
        fromD = firstPrev; toD = lastPrev;
        break;
      }
      case 'LAST_6M': {
        toD = now;
        fromD = new Date(now); fromD.setMonth(now.getMonth() - 6);
        break;
      }
      case 'LAST_12M': {
        toD = now;
        fromD = new Date(now); fromD.setMonth(now.getMonth() - 12);
        break;
      }
      case 'CURRENT_YEAR': {
        toD = now;
        fromD = new Date(now.getFullYear(), 0, 1);
        break;
      }
      case 'PREVIOUS_YEAR': {
        fromD = new Date(now.getFullYear() - 1, 0, 1);
        toD = new Date(now.getFullYear() - 1, 11, 31);
        break;
      }
      case 'ALL':
        return 'Todo';
      case 'CUSTOM':
      default: {
        if (histRange === 'CUSTOM') {
          fromD = histFrom ? new Date(histFrom) : null;
          toD = histTo ? new Date(histTo) : null;
        } else {
          toD = now;
          fromD = new Date(now); fromD.setMonth(now.getMonth() - 6);
        }
      }
    }
    if (!fromD || !toD) return 'Todo';
    return `${fromD.toLocaleDateString('es-PE')} a ${toD.toLocaleDateString('es-PE')}`;
  }, [histRange, histFrom, histTo]);
  // Map backend transactions to display rows, applying client-side filters
  const filtered = useMemo(() => {
    let items = Array.isArray(transactions?.results) ? transactions.results : (transactions || []);
    // Normalize
    items = items.filter(Boolean);

    // Date range
    const now = new Date();
    let from = null;
    let to = null;
    switch (histRange) {
      case 'CUSTOM':
        from = histFrom ? new Date(histFrom) : null;
        to = histTo ? new Date(histTo) : null;
        break;
      case 'LAST_1D':
        to = now; from = new Date(now); from.setDate(now.getDate() - 1);
        break;
      case 'LAST_7D':
        to = now; from = new Date(now); from.setDate(now.getDate() - 7);
        break;
      case 'LAST_14D':
        to = now; from = new Date(now); from.setDate(now.getDate() - 14);
        break;
      case 'CURRENT_MONTH':
        to = now; from = new Date(now.getFullYear(), now.getMonth(), 1);
        break;
      case 'PREVIOUS_MONTH':
        from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        to = new Date(now.getFullYear(), now.getMonth(), 0);
        break;
      case 'LAST_6M':
        to = now; from = new Date(now); from.setMonth(now.getMonth() - 6);
        break;
      case 'LAST_12M':
        to = now; from = new Date(now); from.setMonth(now.getMonth() - 12);
        break;
      case 'CURRENT_YEAR':
        to = now; from = new Date(now.getFullYear(), 0, 1);
        break;
      case 'PREVIOUS_YEAR':
        from = new Date(now.getFullYear() - 1, 0, 1);
        to = new Date(now.getFullYear() - 1, 11, 31);
        break;
      case 'ALL':
      default:
        from = null; to = null;
    }
    // Normalize to whole-day bounds
    if (from) from.setHours(0, 0, 0, 0);
    if (to) to.setHours(23, 59, 59, 999);

    const sym = (histSymbol || '').trim().toLowerCase();
    const typeWanted = new Set([
      histTypes.buy && 'BUY',
      histTypes.sell && 'SELL',
      histTypes.contribution && 'DEPOSIT',
      histTypes.withdrawal && 'WITHDRAWAL',
    ].filter(Boolean));

    const normalizeType = (t) => {
      const raw = String(t || '').toUpperCase();
      if (raw) return raw;
      return '';
    };
    const normalizeDisplay = (d) => {
      const s = String(d || '').toLowerCase();
      if (s.includes('compra')) return 'BUY';
      if (s.includes('venta')) return 'SELL';
      if (s.includes('dep')) return 'DEPOSIT';
      if (s.includes('retiro')) return 'WITHDRAWAL';
      return '';
    };
    const passType = (t) => {
      if (typeWanted.size === 0) return true;
      // Prefer machine type, fallback to display mapping
      const code = normalizeType(t);
      if (code && typeWanted.has(code)) return true;
      return typeWanted.has(normalizeDisplay(t?.transaction_type_display));
    };

    const passDate = (ts) => {
      if (!from && !to) return true;
      const d = ts ? new Date(ts) : null;
      if (!d) return true;
      if (from && d < from) return false;
      if (to) {
        const end = new Date(to);
        end.setHours(23,59,59,999);
        if (d > end) return false;
      }
      return true;
    };

    const passSymbol = (t) => {
      if (!sym) return true;
      const a = (t.stock_symbol || '').toLowerCase();
      const b = (t.stock_name || '').toLowerCase();
      return a.includes(sym) || b.includes(sym);
    };

    return items
      .filter(t => passType(t.transaction_type || t))
      .filter(t => passDate(t.timestamp))
      .filter(t => passSymbol(t))
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [transactions, histRange, histFrom, histTo, histSymbol, histTypes]);

  const pageTotal = useMemo(() => {
    const signOf = (t) => {
      const tp = String(t.transaction_type || '').toUpperCase();
      if (tp === 'BUY') return -1;
      if (tp === 'WITHDRAWAL') return -1;
      return 1; // SELL and DEPOSIT
    };
    return filtered.reduce((acc, t) => acc + signOf(t) * Number(t.amount || 0), 0);
  }, [filtered]);

  const formatSolWithSign = (value) => {
    const num = Number(value || 0);
    const abs = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const sign = num < 0 ? '-' : '';
    return `${sign}S/. ${abs}`;
  };

  return (
    <div className="card history-card" style={{ padding: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Historial de transacciones</h3>
      </div>
      <div className="grid" style={{ gap: 12, marginBottom: 12 }}>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Rango de fechas</div>
            <select className="select" value={histRange} onChange={(e) => setHistRange(e.target.value)}>
              <option value="LAST_1D">Último día</option>
              <option value="LAST_7D">Últimos 7 días</option>
              <option value="LAST_14D">Últimos 14 días</option>
              <option value="CURRENT_MONTH">Mes actual</option>
              <option value="PREVIOUS_MONTH">Mes anterior</option>
              <option value="LAST_6M">Últimos 6 meses</option>
              <option value="LAST_12M">Últimos 12 meses</option>
              <option value="CURRENT_YEAR">Año actual</option>
              <option value="PREVIOUS_YEAR">Año anterior</option>
              <option value="ALL">Todo</option>
              <option value="CUSTOM">Personalizado</option>
            </select>
          </div>
          {histRange === 'CUSTOM' && (
            <div className="row" style={{ gap: 8, alignItems: 'center' }}>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={histFrom} onChange={setHistFrom} max={histTo} placeholder="dd/mm/aaaa" />
              </div>
              <span className="muted" style={{ fontSize: 12 }}>a</span>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={histTo} onChange={setHistTo} min={histFrom} placeholder="dd/mm/aaaa" />
              </div>
            </div>
          )}
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Símbolo (opcional)</div>
            <input className="input" placeholder="Buscar símbolo…" value={histSymbol} onChange={(e)=>setHistSymbol(e.target.value)} />
          </div>
          <div style={{ display: 'none' }}>
            <button className="btn primary">Buscar</button>
          </div>
        </div>
        <div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Filtrar por tipo de transacción</div>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <button className={`btn xs ${histTypes.buy ? 'primary' : 'ghost'}`} onClick={() => toggleHistType('buy')}>Compra</button>
            <button className={`btn xs ${histTypes.sell ? 'primary' : 'ghost'}`} onClick={() => toggleHistType('sell')}>Venta</button>
            <button className={`btn xs ${histTypes.contribution ? 'primary' : 'ghost'}`} onClick={() => toggleHistType('contribution')}>Depósito</button>
            <button className={`btn xs ${histTypes.withdrawal ? 'primary' : 'ghost'}`} onClick={() => toggleHistType('withdrawal')}>Retiro</button>
          </div>
        </div>
      </div>

      <div className="row" style={{ justifyContent: 'flex-start', alignItems: 'center', marginBottom: 8 }}>
        <div className="muted">Transacciones del {rangeLabel}</div>
      </div>

      <div className="scroll-pretty" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table className="table history-table" style={{ minWidth: 920 }}>
          <thead>
            <tr style={{ textAlign: 'left' }}>
              <th style={{ minWidth: 180 }}>Fecha</th>
              <th style={{ minWidth: 160 }}>Tipo</th>
              <th style={{ minWidth: 240 }}>Símbolo / Descripción</th>
              <th style={{ width: 95, maxWidth: 95, textAlign: 'center' }}>Cantidad</th>
              <th style={{ minWidth: 100, textAlign: 'left' }}>Precio Unitario (USD)</th>
              <th style={{ minWidth: 100, textAlign: 'left' }}>TC</th>
              <th style={{ minWidth: 120, textAlign: 'left' }}>Precio Unitario (PEN)</th>
              <th style={{ minWidth: 120 }}>Monto Total</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={8} className="muted">No se encontraron transacciones para los filtros seleccionados.</td></tr>
            ) : (
              filtered.map((t) => {
                const ts = t.timestamp ? new Date(t.timestamp) : null;
                const dateStr = ts ? ts.toLocaleDateString('en-US') : '';
                const qty = t.quantity != null ? String(t.quantity) : '';

                // Precio unitario (USD) - show USD price if available, formatted as $##.##
                const priceUSD = (() => {
                  if (t.executed_price == null) return '';
                  const price = parseFloat(t.executed_price);
                  return `$${price.toFixed(2)}`;
                })();

                // FX rate display - only show if fx_rate exists
                const fxDisplay = (() => {
                  if (!t.fx_rate) return '';
                  const rate = parseFloat(t.fx_rate).toFixed(3);
                  const type = t.fx_rate_type || '';
                  return (
                    <div>
                      <div style={{ fontWeight: 600 }}>S/. {rate}</div>
                      <div className="muted" style={{ fontSize: 10 }}>({type})</div>
                    </div>
                  );
                })();

                // Precio unitario (PEN) - calculate from USD price * FX rate
                const pricePEN = (() => {
                  if (t.executed_price == null) return '';
                  if (!t.fx_rate) return ''; // No FX conversion
                  const price = parseFloat(t.executed_price);
                  const fx = parseFloat(t.fx_rate);
                  const penPrice = price * fx;
                  return `S/. ${penPrice.toFixed(2)}`;
                })();

                // Monto total - total in PEN (after FX conversion if applicable)
                const amount = (() => {
                  const tp = String(t.transaction_type || '').toUpperCase();

                  // For non-trade transactions (DEPOSIT/WITHDRAWAL), use amount directly
                  if (tp === 'DEPOSIT' || tp === 'WITHDRAWAL') {
                    if (t.amount == null) return '';
                    const value = Number(t.amount);
                    if (tp === 'WITHDRAWAL') {
                      return `-${formatCurrency(Math.abs(value))}`;
                    }
                    return formatCurrency(value);
                  }

                  // For trades (BUY/SELL), calculate total in PEN
                  if (t.executed_price == null || t.quantity == null) return '';
                  const price = parseFloat(t.executed_price);
                  const qty = parseInt(t.quantity);
                  let total = price * qty;

                  // Apply FX conversion if available
                  if (t.fx_rate) {
                    const fx = parseFloat(t.fx_rate);
                    total = total * fx;
                  }

                  if (tp === 'BUY') {
                    return `-${formatCurrency(Math.abs(total))}`;
                  }
                  return formatCurrency(total);
                })();
                const amtClass = '';
                return (
                  <tr key={t.id} className="row-appear">
                    <td>
                      <div>{dateStr}</div>
                      {/* Potentially show time or settlement later */}
                    </td>
                    <td>{t.transaction_type_display || t.transaction_type}</td>
                    <td>
                      {t.stock_symbol && <div style={{ fontWeight: 600 }}>{t.stock_symbol}</div>}
                      <div className="muted">{t.stock_name || (t.stock_symbol ? '' : '—')}</div>
                    </td>
                    <td style={{ textAlign: 'center' }}>{qty}</td>
                    <td style={{ textAlign: 'left' }}>{priceUSD}</td>
                    <td style={{ textAlign: 'left' }}>{fxDisplay}</td>
                    <td style={{ textAlign: 'left' }}>{pricePEN}</td>
                    <td className={amtClass}>{amount || '—'}</td>
                  </tr>
                );
              })
            )}
            <tr style={{ background: 'rgba(255,255,255,.04)' }}>
              <td colSpan={7} style={{ textAlign: 'right', fontWeight: 600 }}>Total de la página:</td>
              <td>{formatSolWithSign(pageTotal)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default HistoryTab;
