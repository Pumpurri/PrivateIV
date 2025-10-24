import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { formatCurrency, formatPercent } from '../utils/format';
import { getPortfolioRealized } from '../services/api';

const toNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

const startOfMonth = (dateObj) => new Date(dateObj.getFullYear(), dateObj.getMonth(), 1);

const subtractMonths = (dateObj, count) => {
  const base = startOfMonth(dateObj);
  base.setMonth(base.getMonth() - count);
  return base;
};

const RealizedTab = ({ portfolio }) => {
  const portfolioId = portfolio?.id;
  const [realizedView, setRealizedView] = useState('summary'); // 'summary' | 'analyzer'
  const [realizedRange, setRealizedRange] = useState('CURRENT_YEAR');
  const [symbolFilter, setSymbolFilter] = useState('');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [realizedData, setRealizedData] = useState(null);

  const today = useMemo(() => new Date(), []);
  const rangeMap = useMemo(() => {
    const formatDateISO = (dateObj) => {
      const yyyy = dateObj.getFullYear();
      const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
      const dd = String(dateObj.getDate()).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    };
    const startCurrentYear = new Date(today.getFullYear(), 0, 1);
    const startCurrentMonth = startOfMonth(today);
    const startLast3M = subtractMonths(today, 2);
    const startLast6M = subtractMonths(today, 5);
    const prevYearStart = new Date(today.getFullYear() - 1, 0, 1);
    const prevYearEnd = new Date(today.getFullYear() - 1, 11, 31);
    return {
      CURRENT_YEAR: { from: formatDateISO(startCurrentYear), to: formatDateISO(today) },
      TODAY: { from: formatDateISO(today), to: formatDateISO(today) },
      CURRENT_MONTH: { from: formatDateISO(startCurrentMonth), to: formatDateISO(today) },
      LAST_3M: { from: formatDateISO(startLast3M), to: formatDateISO(today) },
      LAST_6M: { from: formatDateISO(startLast6M), to: formatDateISO(today) },
      PREV_YEAR: { from: formatDateISO(prevYearStart), to: formatDateISO(prevYearEnd) },
    };
  }, [today]);

  const formatDateLabel = useCallback((iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleDateString('es-PE');
  }, []);

  const resolvedPeriod = useMemo(() => {
    if (realizedData?.period) {
      const { from, to } = realizedData.period;
      const fromLabel = formatDateLabel(from);
      const toLabel = formatDateLabel(to);
      if (fromLabel && toLabel) return `${fromLabel} al ${toLabel}`;
      return fromLabel || toLabel;
    }

    if (realizedRange === 'CUSTOM') {
      const fromLabel = formatDateLabel(customFrom);
      const toLabel = formatDateLabel(customTo);
      if (fromLabel && toLabel) return `${fromLabel} al ${toLabel}`;
      if (fromLabel || toLabel) return fromLabel || toLabel;
      return 'Selecciona un rango personalizado';
    }

    const fallback = rangeMap[realizedRange];
    if (fallback) {
      const fromLabel = formatDateLabel(fallback.from);
      const toLabel = formatDateLabel(fallback.to);
      if (fromLabel && toLabel) return `${fromLabel} al ${toLabel}`;
      return fromLabel || toLabel || 'Sin rango';
    }

    return 'Sin rango';
  }, [realizedData?.period, realizedRange, customFrom, customTo, rangeMap, formatDateLabel]);

  const buildParams = useCallback(() => {
    const params = {};
    const symbol = symbolFilter.trim();
    if (symbol) params.symbol = symbol;
    if (realizedRange === 'CUSTOM') {
      if (customFrom) params.from = customFrom;
      if (customTo) params.to = customTo;
    } else {
      const { from, to } = rangeMap[realizedRange] || {};
      if (from) params.from = from;
      if (to) params.to = to;
    }
    return params;
  }, [symbolFilter, realizedRange, customFrom, customTo, rangeMap]);

  const loadRealized = useCallback(async (params = {}) => {
    if (!portfolioId) return;
    setLoading(true);
    setError('');
    try {
      const data = await getPortfolioRealized(portfolioId, params);
      setRealizedData(data);
    } catch (err) {
      console.error(err);
      setRealizedData(null);
      setError('No se pudieron cargar las ganancias realizadas. Intenta nuevamente.');
    } finally {
      setLoading(false);
    }
  }, [portfolioId]);

  useEffect(() => {
    if (!portfolioId) return;
    loadRealized();
  }, [portfolioId, loadRealized]);

  const detailRows = useMemo(() => {
    if (!Array.isArray(realizedData?.details)) return [];
    return realizedData.details.map((item) => ({
      symbol: item.symbol || '--',
      description: item.description || '',
      closed: item.closed_date || '',
      qty: toNumber(item.quantity),
      price: toNumber(item.closing_price),
      cbMethod: item.cost_basis_method || 'FIFO',
      proceeds: toNumber(item.proceeds),
      costBasis: toNumber(item.cost_basis),
      total: toNumber(item.total),
      longTerm: toNumber(item.long_term),
      shortTerm: toNumber(item.short_term),
    }));
  }, [realizedData?.details]);

  const detailSums = useMemo(() => detailRows.reduce((acc, row) => {
    acc.proceeds += row.proceeds;
    acc.costBasis += row.costBasis;
    acc.total += row.total;
    acc.longTerm += row.longTerm;
    acc.shortTerm += row.shortTerm;
    return acc;
  }, { proceeds: 0, costBasis: 0, total: 0, longTerm: 0, shortTerm: 0 }), [detailRows]);

  const totals = useMemo(() => {
    const proceeds = toNumber(realizedData?.totals?.proceeds);
    const costBasis = toNumber(realizedData?.totals?.cost_basis);
    const netGain = toNumber(realizedData?.totals?.net_gain);
    const gainPct = toNumber(realizedData?.totals?.gain_pct);
    const longTerm = toNumber(realizedData?.long_short?.long_term);
    const shortTerm = toNumber(realizedData?.long_short?.short_term);
    return { proceeds, costBasis, netGain, gainPct, longTerm, shortTerm };
  }, [realizedData]);

  const totalsDisplay = useMemo(() => {
    const fallback = detailSums;
    const proceeds = totals.proceeds || fallback.proceeds;
    const costBasis = totals.costBasis || fallback.costBasis;
    const netGain = totals.netGain || fallback.total;
    const gainPct = totals.gainPct;
    const longTerm = totals.longTerm || fallback.longTerm;
    const shortTerm = totals.shortTerm || fallback.shortTerm || netGain;
    return { proceeds, costBasis, netGain, gainPct, longTerm, shortTerm };
  }, [totals, detailSums]);

  const breakdown = useMemo(() => {
    let gains = 0;
    let losses = 0;
    detailRows.forEach(({ total }) => {
      if (total >= 0) gains += total;
      else losses += total;
    });
    return { gains, losses };
  }, [detailRows]);

  const gainRate = useMemo(() => {
    const gains = breakdown.gains;
    const lossesAbs = Math.abs(breakdown.losses);
    const denom = gains + lossesAbs;
    if (!denom) return 0;
    return gains / denom;
  }, [breakdown]);

  const counts = useMemo(() => ({
    gain: toNumber(realizedData?.counts?.gain),
    loss: toNumber(realizedData?.counts?.loss),
  }), [realizedData]);

  const averages = useMemo(() => ({
    gainPct: toNumber(realizedData?.averages?.gain_pct),
    lossPct: toNumber(realizedData?.averages?.loss_pct),
  }), [realizedData]);

  const chartSeries = useMemo(() => {
    if (!Array.isArray(realizedData?.chart)) return [];
    return realizedData.chart
      .map((point) => ({
        date: point.date,
        value: toNumber(point.net),
      }))
      .filter((point) => Number.isFinite(point.value));
  }, [realizedData?.chart]);

  const hasDetails = detailRows.length > 0;

  const onSearch = async (e) => {
    e?.preventDefault?.();
    if (!portfolioId) return;
    await loadRealized(buildParams());
  };

  const handleRangeChange = async (nextRange) => {
    setRealizedRange(nextRange);
    if (nextRange !== 'CUSTOM') {
      setCustomFrom('');
      setCustomTo('');
      if (portfolioId) {
        const preset = rangeMap[nextRange];
        if (preset) {
          await loadRealized({
            ...(symbolFilter.trim() ? { symbol: symbolFilter.trim() } : {}),
            from: preset.from,
            to: preset.to,
          });
        } else {
          await loadRealized();
        }
      }
    }
  };

  const gainsAbs = Math.max(0, breakdown.gains);
  const lossesAbs = Math.abs(breakdown.losses);

  const PiePlaceholder = ({ label, gainRateValue, gains, losses }) => {
    // If no data (both gains and losses are 0), show neutral state
    const hasData = gains !== 0 || losses !== 0;
    const safeRate = hasData ? Math.max(0, Math.min(1, Number.isFinite(gainRateValue) ? gainRateValue : 0)) : 0.5;
    const gainPct = Math.round(safeRate * 100);

    // Semicircle gauge: 180 degrees total
    // Start at -90 degrees (left), end at 90 degrees (right)
    const radius = 15.915;
    const circumference = 2 * Math.PI * radius;
    const halfCircle = circumference / 2; // 50 units for 180 degrees
    const gainLength = (safeRate * halfCircle); // Length of green arc
    const lossLength = halfCircle - gainLength; // Length of red arc

    return (
      <div>
        <div className="tile-title" style={{ marginBottom: 12 }}>{label}</div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          {/* Semicircle gauge */}
          <svg viewBox="0 0 42 26" width={200} height={120} style={{ overflow: 'visible' }}>
            {/* Background track (light gray semicircle) */}
            <path
              d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
              fill="transparent"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="6"
              strokeLinecap="round"
            />
            {hasData ? (
              <>
                {/* Loss arc (red) - draws from right to the dividing point */}
                <path
                  d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                  fill="transparent"
                  stroke="#ef4444"
                  strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={`${lossLength} ${gainLength}`}
                  strokeDashoffset="0"
                />
                {/* Gain arc (green) - draws from left to the dividing point */}
                <path
                  d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                  fill="transparent"
                  stroke="#22c55e"
                  strokeWidth="6"
                  strokeLinecap="round"
                  strokeDasharray={`${gainLength} ${lossLength}`}
                  strokeDashoffset="0"
                />
              </>
            ) : (
              /* Neutral gray arc when no data */
              <path
                d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                fill="transparent"
                stroke="rgba(157,176,208,0.25)"
                strokeWidth="6"
                strokeLinecap="round"
              />
            )}
            {/* Center text */}
            <text x="21" y="18" textAnchor="middle" fill="var(--text)" fontSize="6" fontWeight="700">
              {hasData ? `${gainPct}%` : '—'}
            </text>
            <text x="21" y="23" textAnchor="middle" fill="var(--muted)" fontSize="3">
              {hasData ? 'ganancia' : 'sin datos'}
            </text>
          </svg>
        </div>
      </div>
    );
  };

  return (
    <div className="grid" style={{ gap: 12 }}>
      <div className="muted" style={{ fontSize: 12 }}>
        Para las transacciones de hoy, la información de ganancias/pérdidas realizadas puede demorar.
      </div>
      {error && (
        <div
          className="card"
          style={{
            background: 'rgba(239,68,68,0.08)',
            color: 'var(--danger)',
            padding: 12,
            fontSize: 12,
          }}
        >
          {error}
        </div>
      )}
      {loading && (
        <div className="muted" style={{ fontSize: 12 }}>
          Cargando datos de ganancias realizadas…
        </div>
      )}

      <div className="card" style={{ padding: 16 }}>
        <form onSubmit={onSearch} className="row" style={{ gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Rango de fechas</div>
            <select className="select" value={realizedRange} onChange={e => handleRangeChange(e.target.value)}>
              <option value="CURRENT_YEAR">Año en curso</option>
              <option value="TODAY">Hoy</option>
              <option value="CURRENT_MONTH">Mes en curso</option>
              <option value="LAST_3M">Últimos 3 meses</option>
              <option value="LAST_6M">Últimos 6 meses</option>
              <option value="PREV_YEAR">Año calendario anterior</option>
              <option value="CUSTOM">Rango personalizado</option>
            </select>
            {realizedRange === 'CUSTOM' && (
              <div className="row" style={{ gap: 8, marginTop: 6 }}>
                <input type="date" className="input" value={customFrom} onChange={e => setCustomFrom(e.target.value)} />
                <span className="muted" style={{ fontSize: 12 }}>a</span>
                <input type="date" className="input" value={customTo} onChange={e => setCustomTo(e.target.value)} />
              </div>
            )}
          </div>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Símbolo (opcional)</div>
            <input className="input" placeholder="ej. AAPL" value={symbolFilter} onChange={e => setSymbolFilter(e.target.value)} />
          </div>
          <div style={{ alignSelf: 'stretch', display: 'flex', alignItems: 'flex-end' }}>
            <button className="btn primary" type="submit" disabled={loading || !portfolioId}>
              {loading ? 'Buscando…' : 'Buscar'}
            </button>
          </div>
        </form>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div className="row realized-seg" style={{ gap: 0 }}>
          <button
            className={`seg ${realizedView === 'summary' ? 'active' : ''}`}
            onClick={() => setRealizedView('summary')}
          >
            Resumen de ganancias/pérdidas
          </button>
          <button
            className={`seg ${realizedView === 'analyzer' ? 'active' : ''}`}
            onClick={() => setRealizedView('analyzer')}
          >
            Analizador de transacciones
          </button>
        </div>
        <div style={{ height: 8 }} />

        {realizedView === 'summary' ? (
          <div className="anim-fade">
            <div className="realized-grid">
              <div className="realized-panel">
                <div className="tile-title">Periodo de reporte</div>
                <div className="muted" style={{ marginBottom: 12, fontSize: 14 }}>{resolvedPeriod}</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ingresos totales</span>
                    <span className="tile-value">{formatCurrency(totalsDisplay.proceeds)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Base de costo total</span>
                    <span className="tile-value">{formatCurrency(totalsDisplay.costBasis)}</span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Ganancia/Pérdida</div>
                <div className="grid" style={{ gap: 8, fontSize: 12 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="muted">Largo plazo (≥365 días)</span>
                    <span style={{ color: totalsDisplay.longTerm >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {formatCurrency(totalsDisplay.longTerm)}
                    </span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="muted">Corto plazo (&lt;365 días)</span>
                    <span style={{ color: totalsDisplay.shortTerm >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {formatCurrency(totalsDisplay.shortTerm)}
                    </span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="muted">Ganancia neta</span>
                    <span style={{ color: totalsDisplay.netGain >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {formatCurrency(totalsDisplay.netGain)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Totales</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ganancias totales</span>
                    <span className="tile-value up">{formatCurrency(gainsAbs)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Pérdidas totales</span>
                    <span className="tile-value down">{formatCurrency(lossesAbs)}</span>
                  </div>
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 4 }}>
                    <div className="row" style={{ justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>Ganancia neta</span>
                      <span className="tile-value" style={{ color: totalsDisplay.netGain >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                        {formatCurrency(totalsDisplay.netGain)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {hasDetails && (
                <div className="realized-panel">
                  <PiePlaceholder label="Distribución de resultados" gainRateValue={gainRate} gains={gainsAbs} losses={lossesAbs} />
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="anim-fade">
            <div className="realized-grid">
              <div className="realized-panel">
                <div className="tile-title">Periodo de reporte</div>
                <div className="muted" style={{ marginBottom: 12, fontSize: 14 }}>{resolvedPeriod}</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ingresos totales</span>
                    <span className="tile-value">{formatCurrency(totalsDisplay.proceeds)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Base de costo total</span>
                    <span className="tile-value">{formatCurrency(totalsDisplay.costBasis)}</span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Promedios</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ganancia promedio</span>
                    <span className="tile-value up">{formatPercent(averages.gainPct)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Pérdida promedio</span>
                    <span className="tile-value down">{formatPercent(averages.lossPct)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ganancia neta</span>
                    <span className="tile-value" style={{ color: totalsDisplay.netGain >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {formatPercent(totalsDisplay.gainPct)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Transacciones</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Con ganancia</span>
                    <span className="tile-value up">{counts.gain}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Con pérdida</span>
                    <span className="tile-value down">{counts.loss}</span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <PiePlaceholder label="Distribución de resultados" gainRateValue={gainRate} gains={gainsAbs} losses={lossesAbs} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Details card with chart and table */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Detalle de ganancias/pérdidas realizadas</div>
        {(() => {
          if (!chartSeries.length) {
            return (
              <div className="card" style={{ padding: 12, marginBottom: 12, fontSize: 12, color: 'var(--danger)' }}>
                Aún no hay movimientos realizados en el período seleccionado para graficar.
              </div>
            );
          }
          const values = chartSeries.map(p => p.value);
          const w = 100;
          const h = 40;
          const min = Math.min(...values);
          const max = Math.max(...values);
          const span = max - min || 1;
          const step = chartSeries.length > 1 ? w / (chartSeries.length - 1) : w;
          const pts = chartSeries.map((p, idx) => {
            const x = idx * step;
            const y = h - ((p.value - min) / span) * h;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
          }).join(' ');
          const formatDate = (iso) => {
            if (!iso) return '—';
            const d = new Date(iso);
            return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-PE');
          };
          return (
            <div className="card" style={{ padding: 12, marginBottom: 12 }}>
              <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 160 }}>
                <line x1="0" y1={h - 1} x2={w} y2={h - 1} stroke="#334" strokeWidth="0.6" />
                <line x1="1" y1="0" x2="1" y2={h} stroke="#334" strokeWidth="0.6" />
                <polyline fill="none" stroke="rgba(37,99,235,1)" strokeWidth="1.6" points={pts} />
              </svg>
              <div className="row" style={{ justifyContent: 'space-between', fontSize: 12, marginTop: 4 }}>
                <span className="muted">Inicio: {formatDate(chartSeries[0]?.date)}</span>
                <span className="muted">Fin: {formatDate(chartSeries[chartSeries.length - 1]?.date)}</span>
              </div>
            </div>
          );
        })()}

        {(() => {
          if (!hasDetails) {
            return (
              <div className="card" style={{ padding: 12, fontSize: 12, color: 'var(--danger)' }}>
                No se registran operaciones realizadas para el período seleccionado.
              </div>
            );
          }
          const fmtSigned = (v) => `${v >= 0 ? '+' : ''}${formatCurrency(v)}`;
          const fmtDate = (iso) => {
            if (!iso) return '—';
            const d = new Date(iso);
            return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-PE');
          };
          const formatQty = (qty) => {
            const num = Number(qty);
            if (!Number.isFinite(num)) return '0';
            return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
          };
          const totalsRow = totalsDisplay;
          return (
            <div className="scroll-pretty" style={{ width: '100%', maxWidth: '100%', overflowX: 'auto', WebkitOverflowScrolling: 'touch', fontSize: 11, lineHeight: 1.25, color: 'var(--danger)' }}>
              <table className="table positions-table realized-details-table" style={{ minWidth: 1100, fontSize: 11 }}>
                <thead>
                  <tr style={{ textAlign: 'left' }}>
                    <th className="sticky-col" style={{ whiteSpace: 'nowrap', minWidth: 90 }}>Símbolo</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 380 }}>Descripción</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Fecha de cierre</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 70 }}>Cantidad</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 100 }}>Precio de cierre</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 150 }}>Método de base de costo</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Ingresos</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Base de costo (CB)</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Total</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Largo plazo</th>
                    <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Corto plazo</th>
                  </tr>
                </thead>
                <tbody>
                  {detailRows.map((r, idx) => (
                    <tr key={`${r.symbol}-${idx}`}>
                      <td className="sticky-col" style={{ fontWeight: 600, minWidth: 90 }}>{r.symbol}</td>
                      <td style={{ minWidth: 380 }}>{r.description}</td>
                      <td style={{ minWidth: 120 }}>{fmtDate(r.closed)}</td>
                      <td style={{ minWidth: 70 }}>{formatQty(r.qty)}</td>
                      <td style={{ minWidth: 100 }}>{formatCurrency(r.price)}</td>
                      <td style={{ minWidth: 150 }}>{r.cbMethod}</td>
                      <td style={{ minWidth: 120 }}>{formatCurrency(r.proceeds)}</td>
                      <td style={{ minWidth: 120 }}>{formatCurrency(r.costBasis)}</td>
                      <td style={{ minWidth: 120 }} className={r.total >= 0 ? 'up' : 'down'}>{fmtSigned(r.total)}</td>
                      <td style={{ minWidth: 120 }} className={r.longTerm >= 0 ? 'up' : 'down'}>{formatCurrency(r.longTerm)}</td>
                      <td style={{ minWidth: 120 }} className={r.shortTerm >= 0 ? 'up' : 'down'}>{fmtSigned(r.shortTerm)}</td>
                    </tr>
                  ))}
                  <tr style={{ background: 'rgba(255,255,255,0.04)' }}>
                    <td className="sticky-col" style={{ fontWeight: 700, minWidth: 90 }}>Total de la cuenta</td>
                    <td style={{ minWidth: 380 }}>—</td>
                    <td style={{ minWidth: 120 }}>—</td>
                    <td style={{ minWidth: 70 }}>—</td>
                    <td style={{ minWidth: 100 }}>—</td>
                    <td style={{ minWidth: 150 }}>—</td>
                    <td style={{ minWidth: 120 }}>{formatCurrency(totalsRow.proceeds)}</td>
                    <td style={{ minWidth: 120 }}>{formatCurrency(totalsRow.costBasis)}</td>
                    <td style={{ minWidth: 120 }} className={totalsRow.netGain >= 0 ? 'up' : 'down'}>{fmtSigned(totalsRow.netGain)}</td>
                    <td style={{ minWidth: 120 }} className={totalsRow.longTerm >= 0 ? 'up' : 'down'}>{formatCurrency(totalsRow.longTerm)}</td>
                    <td style={{ minWidth: 120 }} className={totalsRow.shortTerm >= 0 ? 'up' : 'down'}>{fmtSigned(totalsRow.shortTerm)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          );
        })()}
      </div>
    </div>
  );
};

export default RealizedTab;
