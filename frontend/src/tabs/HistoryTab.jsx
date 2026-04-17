import React, { useMemo, useState } from 'react';
import DatePicker from '../components/DatePicker';

const fmt = (value, currency) => {
  const n = Number(value ?? 0);
  if (currency === 'USD') return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
  return new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(n);
};

const fmtSigned = (value, currency) => {
  const n = Number(value ?? 0);
  const abs = fmt(Math.abs(n), currency);
  return n < 0 ? `-${abs}` : abs;
};

const HistoryTab = ({ transactions = [] }) => {
  const [histRange, setHistRange] = useState('LAST_6M');
  const [histSymbol, setHistSymbol] = useState('');
  const [histFrom, setHistFrom] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 6); return d.toISOString().split('T')[0];
  });
  const [histTo, setHistTo] = useState(() => new Date().toISOString().split('T')[0]);
  const [histTypes, setHistTypes] = useState({ buy: false, sell: false, deposit: false, withdrawal: false, convert: false });
  const toggleHistType = (key) => setHistTypes(s => ({ ...s, [key]: !s[key] }));

  // New controls
  const [currencyFilter, setCurrencyFilter] = useState('ALL'); // 'ALL' | 'PEN' | 'USD'
  const [displayCurrency, setDisplayCurrency] = useState('NATIVE'); // 'NATIVE' | 'PEN' | 'USD'

  const rangeLabel = useMemo(() => {
    const now = new Date();
    let fromD = null, toD = null;
    switch (histRange) {
      case 'LAST_1D': toD = now; fromD = new Date(now); fromD.setDate(now.getDate() - 1); break;
      case 'LAST_7D': toD = now; fromD = new Date(now); fromD.setDate(now.getDate() - 7); break;
      case 'LAST_14D': toD = now; fromD = new Date(now); fromD.setDate(now.getDate() - 14); break;
      case 'CURRENT_MONTH': toD = now; fromD = new Date(now.getFullYear(), now.getMonth(), 1); break;
      case 'PREVIOUS_MONTH': fromD = new Date(now.getFullYear(), now.getMonth() - 1, 1); toD = new Date(now.getFullYear(), now.getMonth(), 0); break;
      case 'LAST_6M': toD = now; fromD = new Date(now); fromD.setMonth(now.getMonth() - 6); break;
      case 'LAST_12M': toD = now; fromD = new Date(now); fromD.setMonth(now.getMonth() - 12); break;
      case 'CURRENT_YEAR': toD = now; fromD = new Date(now.getFullYear(), 0, 1); break;
      case 'PREVIOUS_YEAR': fromD = new Date(now.getFullYear() - 1, 0, 1); toD = new Date(now.getFullYear() - 1, 11, 31); break;
      case 'ALL': return 'Todo';
      case 'CUSTOM':
      default:
        if (histRange === 'CUSTOM') { fromD = histFrom ? new Date(histFrom) : null; toD = histTo ? new Date(histTo) : null; }
        else { toD = now; fromD = new Date(now); fromD.setMonth(now.getMonth() - 6); }
    }
    if (!fromD || !toD) return 'Todo';
    return `${fromD.toLocaleDateString('es-PE')} a ${toD.toLocaleDateString('es-PE')}`;
  }, [histRange, histFrom, histTo]);

  const filtered = useMemo(() => {
    let items = Array.isArray(transactions?.results) ? transactions.results : (transactions || []);
    items = items.filter(Boolean);

    const now = new Date();
    let from = null, to = null;
    switch (histRange) {
      case 'CUSTOM': from = histFrom ? new Date(histFrom) : null; to = histTo ? new Date(histTo) : null; break;
      case 'LAST_1D': to = now; from = new Date(now); from.setDate(now.getDate() - 1); break;
      case 'LAST_7D': to = now; from = new Date(now); from.setDate(now.getDate() - 7); break;
      case 'LAST_14D': to = now; from = new Date(now); from.setDate(now.getDate() - 14); break;
      case 'CURRENT_MONTH': to = now; from = new Date(now.getFullYear(), now.getMonth(), 1); break;
      case 'PREVIOUS_MONTH': from = new Date(now.getFullYear(), now.getMonth() - 1, 1); to = new Date(now.getFullYear(), now.getMonth(), 0); break;
      case 'LAST_6M': to = now; from = new Date(now); from.setMonth(now.getMonth() - 6); break;
      case 'LAST_12M': to = now; from = new Date(now); from.setMonth(now.getMonth() - 12); break;
      case 'CURRENT_YEAR': to = now; from = new Date(now.getFullYear(), 0, 1); break;
      case 'PREVIOUS_YEAR': from = new Date(now.getFullYear() - 1, 0, 1); to = new Date(now.getFullYear() - 1, 11, 31); break;
      default: from = null; to = null;
    }
    if (from) from.setHours(0, 0, 0, 0);
    if (to) to.setHours(23, 59, 59, 999);

    const sym = (histSymbol || '').trim().toLowerCase();
    const typeWanted = new Set([
      histTypes.buy && 'BUY',
      histTypes.sell && 'SELL',
      histTypes.deposit && 'DEPOSIT',
      histTypes.withdrawal && 'WITHDRAWAL',
      histTypes.convert && 'CONVERT',
    ].filter(Boolean));

    return items
      .filter(t => {
        if (typeWanted.size === 0) return true;
        return typeWanted.has(String(t.transaction_type || '').toUpperCase());
      })
      .filter(t => {
        if (!from && !to) return true;
        const d = t.timestamp ? new Date(t.timestamp) : null;
        if (!d) return true;
        if (from && d < from) return false;
        if (to && d > to) return false;
        return true;
      })
      .filter(t => {
        if (!sym) return true;
        return (t.stock_symbol || '').toLowerCase().includes(sym) || (t.stock_name || '').toLowerCase().includes(sym);
      })
      .filter(t => {
        if (currencyFilter === 'ALL') return true;
        return (t.cash_currency || 'PEN').toUpperCase() === currencyFilter;
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [transactions, histRange, histFrom, histTo, histSymbol, histTypes, currencyFilter]);

  // Returns signed display amount and currency for a transaction given displayCurrency mode
  const getRowAmount = (t, mode) => {
    const tp = String(t.transaction_type || '').toUpperCase();
    const cashCur = (t.cash_currency || 'PEN').toUpperCase();
    const rawAmount = Number(t.amount || 0);
    const fxRate = Number(t.fx_rate || 1);

    // CONVERT: show the side that belongs to the display currency
    if (tp === 'CONVERT') {
      const counterCur = (t.counter_currency || '').toUpperCase();
      const counterAmount = Number(t.counter_amount || 0);
      if (mode === 'NATIVE') return { amount: -rawAmount, currency: cashCur };
      // Display currency matches the received (credit) side
      if (mode === counterCur) return { amount: counterAmount, currency: counterCur };
      // Display currency matches the debited side
      if (mode === cashCur) return { amount: -rawAmount, currency: cashCur };
      // Neither side matches — convert the debit to target currency
      if (cashCur === 'PEN' && mode === 'USD') return { amount: fxRate > 0 ? -rawAmount / fxRate : -rawAmount, currency: 'USD' };
      if (cashCur === 'USD' && mode === 'PEN') return { amount: -rawAmount * fxRate, currency: 'PEN' };
      return { amount: -rawAmount, currency: cashCur };
    }

    const isDebit = tp === 'BUY' || tp === 'WITHDRAWAL';
    const signed = isDebit ? -rawAmount : rawAmount;
    if (mode === 'NATIVE') return { amount: signed, currency: cashCur };
    if (mode === 'PEN') {
      if (cashCur === 'PEN') return { amount: signed, currency: 'PEN' };
      return { amount: signed * fxRate, currency: 'PEN' };
    }
    if (mode === 'USD') {
      if (cashCur === 'USD') return { amount: signed, currency: 'USD' };
      return { amount: fxRate > 0 ? signed / fxRate : signed, currency: 'USD' };
    }
    return { amount: signed, currency: cashCur };
  };

  // Returns display price per unit (for BUY/SELL) in the display currency
  const getUnitPrice = (t, mode) => {
    if (t.executed_price == null) return null;
    const cashCur = (t.cash_currency || 'PEN').toUpperCase();
    const price = Number(t.executed_price);
    const fxRate = Number(t.fx_rate || 1);
    if (mode === 'NATIVE') return { price, currency: cashCur };
    if (mode === 'PEN') {
      if (cashCur === 'PEN') return { price, currency: 'PEN' };
      return { price: price * fxRate, currency: 'PEN' };
    }
    if (mode === 'USD') {
      if (cashCur === 'USD') return { price, currency: 'USD' };
      return { price: fxRate > 0 ? price / fxRate : price, currency: 'USD' };
    }
    return { price, currency: cashCur };
  };

  // Page totals
  const pageTotals = useMemo(() => {
    const isNativeNoFilter = displayCurrency === 'NATIVE' && currencyFilter === 'ALL';

    if (isNativeNoFilter) {
      // Dual totals: PEN and USD tracked separately
      let pen = 0, usd = 0;
      filtered.forEach(t => {
        const tp = String(t.transaction_type || '').toUpperCase();
        const cashCur = (t.cash_currency || 'PEN').toUpperCase();
        const { amount } = getRowAmount(t, 'NATIVE');
        if (cashCur === 'USD') usd += Number.isFinite(amount) ? amount : 0;
        else pen += Number.isFinite(amount) ? amount : 0;

        // CONVERT: also credit the counter side
        if (tp === 'CONVERT' && t.counter_currency && t.counter_amount != null) {
          const counterCur = String(t.counter_currency).toUpperCase();
          const counterAmt = Number(t.counter_amount);
          if (counterCur === 'USD') usd += counterAmt;
          else pen += counterAmt;
        }
      });
      return { type: 'dual', pen, usd };
    }

    // Single total in target currency
    const total = filtered.reduce((acc, t) => {
      const { amount } = getRowAmount(t, displayCurrency === 'NATIVE' ? 'NATIVE' : displayCurrency);
      return acc + (Number.isFinite(amount) ? amount : 0);
    }, 0);
    const currency = displayCurrency !== 'NATIVE' ? displayCurrency : currencyFilter;
    return { type: 'single', value: total, currency };
  }, [filtered, displayCurrency, currencyFilter]);

  const displayToggleLabel = displayCurrency === 'NATIVE'
    ? 'Ver en S/'
    : displayCurrency === 'PEN'
      ? 'Ver en $'
      : 'Ver en original';
  const nextDisplayCurrency = displayCurrency === 'NATIVE' ? 'PEN' : displayCurrency === 'PEN' ? 'USD' : 'NATIVE';

  return (
    <div className="card history-card" style={{ padding: 16 }}>
      {/* Header */}
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>Historial de transacciones</h3>
        <button
          className="btn xs ghost"
          onClick={() => setDisplayCurrency(nextDisplayCurrency)}
          style={{ fontSize: 12 }}
        >
          {displayToggleLabel}
        </button>
      </div>

      {/* Filters */}
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
            <input className="input" placeholder="Buscar símbolo…" value={histSymbol} onChange={(e) => setHistSymbol(e.target.value)} />
          </div>
        </div>

        {/* Type filter */}
        <div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Tipo de transacción</div>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {[
              { key: 'buy', label: 'Compra' },
              { key: 'sell', label: 'Venta' },
              { key: 'deposit', label: 'Depósito' },
              { key: 'withdrawal', label: 'Retiro' },
              { key: 'convert', label: 'Cambio S/↔$' },
            ].map(({ key, label }) => (
              <button key={key} className={`btn xs ${histTypes[key] ? 'primary' : 'ghost'}`} onClick={() => toggleHistType(key)}>{label}</button>
            ))}
          </div>
        </div>

        {/* Currency filter */}
        <div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Moneda de transacción</div>
          <div className="row" style={{ gap: 6 }}>
            {[
              { id: 'ALL', label: 'Todas' },
              { id: 'PEN', label: 'Soles (S/)' },
              { id: 'USD', label: 'Dólares ($)' },
            ].map(({ id, label }) => (
              <button key={id} className={`btn xs ${currencyFilter === id ? 'primary' : 'ghost'}`} onClick={() => setCurrencyFilter(id)}>{label}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div className="muted">Transacciones del {rangeLabel}</div>
        <div className="muted" style={{ fontSize: 11 }}>
          Mostrando en: <strong>{displayCurrency === 'NATIVE' ? 'moneda original' : displayCurrency === 'PEN' ? 'soles (S/)' : 'dólares ($)'}</strong>
          {currencyFilter !== 'ALL' && <> · Filtrado: <strong>{currencyFilter === 'PEN' ? 'S/ soles' : '$ dólares'}</strong></>}
        </div>
      </div>

      <div className="scroll-pretty" style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table className="table history-table" style={{ minWidth: 800 }}>
          <thead>
            <tr style={{ textAlign: 'left' }}>
              <th style={{ minWidth: 160 }}>Fecha</th>
              <th style={{ minWidth: 160 }}>Tipo</th>
              <th style={{ minWidth: 220 }}>Símbolo / Descripción</th>
              <th style={{ width: 80, maxWidth: 80, textAlign: 'center' }}>Cant.</th>
              <th style={{ minWidth: 120, textAlign: 'left' }}>Precio unitario</th>
              {displayCurrency === 'NATIVE' && <th style={{ minWidth: 90, textAlign: 'left' }}>TC</th>}
              <th style={{ minWidth: 130 }}>Monto total</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={displayCurrency === 'NATIVE' ? 7 : 6} className="muted">No se encontraron transacciones para los filtros seleccionados.</td></tr>
            ) : (
              filtered.map((t) => {
                const tp = String(t.transaction_type || '').toUpperCase();
                const ts = t.timestamp ? new Date(t.timestamp) : null;
                const dateStr = ts ? ts.toLocaleDateString('es-PE') : '';
                const timeStr = ts ? ts.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' }) : '';

                const unitPriceInfo = getUnitPrice(t, displayCurrency);
                const unitPriceDisplay = unitPriceInfo
                  ? fmt(unitPriceInfo.price, unitPriceInfo.currency)
                  : '—';

                const fxDisplay = t.fx_rate
                  ? `S/ ${Number(t.fx_rate).toFixed(3)}${t.fx_rate_type ? ` (${t.fx_rate_type})` : ''}`
                  : '—';

                // Amount total display
                let amountDisplay;
                let amountColor = '';
                if (tp === 'CONVERT' && displayCurrency === 'NATIVE') {
                  const cashCur = (t.cash_currency || 'PEN').toUpperCase();
                  const counterCur = (t.counter_currency || '').toUpperCase();
                  const debit = fmt(Number(t.amount || 0), cashCur);
                  const credit = t.counter_amount != null ? fmt(Number(t.counter_amount), counterCur) : null;
                  amountDisplay = <span>-{debit}{credit ? <><br /><span style={{ color: '#4ade80' }}>+{credit}</span></> : null}</span>;
                } else {
                  const { amount, currency } = getRowAmount(t, displayCurrency === 'NATIVE' ? 'NATIVE' : displayCurrency);
                  amountColor = amount < 0 ? 'down' : amount > 0 ? 'up' : '';
                  amountDisplay = fmtSigned(amount, currency);
                }

                return (
                  <tr key={t.id} className="row-appear">
                    <td>
                      <div>{dateStr}</div>
                      <div className="muted" style={{ fontSize: 10 }}>{timeStr}</div>
                    </td>
                    <td>{t.transaction_type_display || tp}</td>
                    <td>
                      {t.stock_symbol && <div style={{ fontWeight: 600 }}>{t.stock_symbol}</div>}
                      <div className="muted">{t.stock_name || (t.stock_symbol ? '' : '—')}</div>
                    </td>
                    <td style={{ textAlign: 'center' }}>{t.quantity != null ? t.quantity : '—'}</td>
                    <td style={{ textAlign: 'left' }}>{unitPriceDisplay}</td>
                    {displayCurrency === 'NATIVE' && <td style={{ textAlign: 'left', fontSize: 11 }}>{fxDisplay}</td>}
                    <td className={amountColor}>{amountDisplay}</td>
                  </tr>
                );
              })
            )}

            {/* Totals row */}
            <tr style={{ background: 'rgba(255,255,255,.04)' }}>
              <td colSpan={displayCurrency === 'NATIVE' ? 6 : 5} style={{ textAlign: 'right', fontWeight: 600 }}>Total de la página:</td>
              <td style={{ fontWeight: 600 }}>
                {pageTotals.type === 'dual' ? (
                  <span>
                    <span className={pageTotals.pen < 0 ? 'down' : pageTotals.pen > 0 ? 'up' : ''}>{fmtSigned(pageTotals.pen, 'PEN')}</span>
                    {pageTotals.usd !== 0 && (
                      <><br /><span className={pageTotals.usd < 0 ? 'down' : 'up'}>{fmtSigned(pageTotals.usd, 'USD')}</span></>
                    )}
                  </span>
                ) : (
                  <span className={pageTotals.value < 0 ? 'down' : pageTotals.value > 0 ? 'up' : ''}>
                    {fmtSigned(pageTotals.value, pageTotals.currency)}
                  </span>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default HistoryTab;
