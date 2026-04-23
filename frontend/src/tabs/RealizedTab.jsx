import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import DatePicker from '../components/DatePicker';
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

const parseDisplayDate = (iso) => {
  if (!iso) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [year, month, day] = iso.split('-').map(Number);
    return new Date(year, month - 1, day);
  }
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const formatMoney = (value, currency = 'PEN') => {
  if ((currency || 'PEN').toUpperCase() === 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value ?? 0));
  }
  return formatCurrency(value);
};

const DISPLAY_CURRENCY_NATIVE = 'NATIVE';
const PAGE_SIZE_ALL = 'ALL';
const PAGE_SIZE_OPTIONS = [25, 50, 100, PAGE_SIZE_ALL];

const NICE_TICK_FACTORS = [1, 2, 2.5, 5, 10];

const getNiceStep = (rawStep) => {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const exponent = Math.floor(Math.log10(rawStep));
  const magnitude = 10 ** exponent;
  const fraction = rawStep / magnitude;
  const chosenFactor = NICE_TICK_FACTORS.find((candidate) => fraction <= candidate) || NICE_TICK_FACTORS[NICE_TICK_FACTORS.length - 1];
  return chosenFactor * magnitude;
};

const buildNiceTicks = (minValue, maxValue, targetIntervals = 4) => {
  let min = Number.isFinite(minValue) ? minValue : 0;
  let max = Number.isFinite(maxValue) ? maxValue : 0;

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.05, 1);
    min -= pad;
    max += pad;
  }

  const range = Math.max(max - min, 1e-9);
  let step = getNiceStep(range / targetIntervals);
  let tickMin = Math.floor(min / step) * step;
  let tickMax = Math.ceil(max / step) * step;

  while (((tickMax - tickMin) / step) > targetIntervals) {
    const nextStep = getNiceStep(step * 1.5);
    if (nextStep <= step) {
      step *= 2;
    } else {
      step = nextStep;
    }
    tickMin = Math.floor(min / step) * step;
    tickMax = Math.ceil(max / step) * step;
  }

  const ticks = [];
  for (let value = tickMin; value <= tickMax + (step / 10); value += step) {
    ticks.push(Number(value.toFixed(6)));
  }

  return {
    ticks,
    min: ticks[0],
    max: ticks[ticks.length - 1],
    step,
  };
};

const RealizedTab = ({ portfolio }) => {
  const portfolioId = portfolio?.id;
  const [realizedView, setRealizedView] = useState('summary'); // 'summary' | 'analyzer'
  const [realizedRange, setRealizedRange] = useState('CURRENT_YEAR');
  const [displayCurrency, setDisplayCurrency] = useState(DISPLAY_CURRENCY_NATIVE);
  const [symbolFilter, setSymbolFilter] = useState('');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [realizedData, setRealizedData] = useState(null);
  const [chartTooltip, setChartTooltip] = useState(null);
  const [totalTooltip, setTotalTooltip] = useState(null);
  const [detailPageSize, setDetailPageSize] = useState(25);
  const [detailPage, setDetailPage] = useState(1);

  const today = useMemo(() => new Date(), []);
  const minDateISO = useMemo(() => {
    const createdAt = portfolio?.created_at;
    if (!createdAt) return undefined;
    const date = new Date(createdAt);
    if (Number.isNaN(date.getTime())) return undefined;
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }, [portfolio?.created_at]);
  const maxDateISO = useMemo(() => {
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }, [today]);
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
    const d = parseDisplayDate(iso);
    if (!d) return '';
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
    params.display_currency = displayCurrency;
    if (realizedRange === 'CUSTOM') {
      if (customFrom) params.from = customFrom;
      if (customTo) params.to = customTo;
    } else {
      const { from, to } = rangeMap[realizedRange] || {};
      if (from) params.from = from;
      if (to) params.to = to;
    }
    return params;
  }, [symbolFilter, realizedRange, customFrom, customTo, rangeMap, displayCurrency]);

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
    const params = {};
    if (displayCurrency) params.display_currency = displayCurrency;
    if (realizedRange !== 'CUSTOM') {
      const preset = rangeMap[realizedRange];
      if (preset) {
        params.from = preset.from;
        params.to = preset.to;
      }
    } else {
      if (customFrom) params.from = customFrom;
      if (customTo) params.to = customTo;
    }
    const symbol = symbolFilter.trim();
    if (symbol) params.symbol = symbol;
    loadRealized(params);
  }, [portfolioId, displayCurrency, loadRealized]);

  const detailRows = useMemo(() => {
    if (!Array.isArray(realizedData?.details)) return [];
    return realizedData.details.map((item) => ({
      symbol: item.symbol || '--',
      description: item.description || '',
      closed: item.closed_date || '',
      qty: toNumber(item.quantity),
      currency: (item.display_currency || realizedData?.summary_currency || 'PEN').toUpperCase(),
      price: toNumber(item.closing_price),
      cbMethod: item.cost_basis_method === 'Average Cost' ? 'Costo promedio' : (item.cost_basis_method || 'Costo promedio'),
      proceeds: toNumber(item.proceeds),
      costBasis: toNumber(item.cost_basis),
      total: toNumber(item.total),
      chartTotal: toNumber(item.chart_total ?? item.total),
      chartCostBasis: toNumber(item.chart_cost_basis ?? item.cost_basis),
      gainPct: toNumber(item.cost_basis) ? (toNumber(item.total) / toNumber(item.cost_basis)) * 100 : 0,
      longTerm: toNumber(item.long_term),
      shortTerm: toNumber(item.short_term),
    }));
  }, [realizedData?.details, realizedData?.summary_currency]);

  const detailSums = useMemo(() => detailRows.reduce((acc, row) => {
    acc.proceeds += row.proceeds;
    acc.costBasis += row.costBasis;
    acc.total += row.total;
    acc.longTerm += row.longTerm;
    acc.shortTerm += row.shortTerm;
    return acc;
  }, { proceeds: 0, costBasis: 0, total: 0, longTerm: 0, shortTerm: 0 }), [detailRows]);

  const termBreakdown = useMemo(() => detailRows.reduce((acc, row) => {
    if (row.longTerm !== 0) {
      acc.longTermCostBasis += row.chartCostBasis;
    }
    if (row.shortTerm !== 0) {
      acc.shortTermCostBasis += row.chartCostBasis;
    }
    return acc;
  }, {
    longTermCostBasis: 0,
    shortTermCostBasis: 0,
  }), [detailRows]);

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
    if (realizedData?.totals) {
      return totals;
    }
    return {
      proceeds: detailSums.proceeds,
      costBasis: detailSums.costBasis,
      netGain: detailSums.total,
      gainPct: totals.gainPct,
      longTerm: detailSums.longTerm,
      shortTerm: detailSums.shortTerm,
    };
  }, [realizedData?.totals, totals, detailSums]);

  const breakdown = useMemo(() => {
    let gains = 0;
    let losses = 0;
    detailRows.forEach(({ chartTotal }) => {
      if (chartTotal >= 0) gains += chartTotal;
      else losses += chartTotal;
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
  const nativeSummary = useMemo(() => {
    const source = realizedData?.native_summary || {};
    const normalizeBucket = (currency) => ({
      currency,
      proceeds: toNumber(source?.[currency]?.proceeds),
      costBasis: toNumber(source?.[currency]?.cost_basis),
      netGain: toNumber(source?.[currency]?.net_gain),
      longTerm: toNumber(source?.[currency]?.long_term),
      shortTerm: toNumber(source?.[currency]?.short_term),
      gains: toNumber(source?.[currency]?.gains),
      losses: toNumber(source?.[currency]?.losses),
    });
    return [normalizeBucket('PEN'), normalizeBucket('USD')];
  }, [realizedData?.native_summary]);

  const activeDisplayMode = (realizedData?.display_currency_mode || displayCurrency || DISPLAY_CURRENCY_NATIVE).toUpperCase();
  const summaryCurrency = (realizedData?.summary_currency || realizedData?.display_currency || 'PEN').toUpperCase();
  const currencyLabel = summaryCurrency === 'USD' ? 'USD' : 'PEN';
  const currencyToggleLabel = activeDisplayMode === DISPLAY_CURRENCY_NATIVE
    ? 'Ver en S/.'
    : activeDisplayMode === 'PEN'
      ? 'Ver en $'
      : 'Ver en original';
  const nextDisplayCurrency = activeDisplayMode === DISPLAY_CURRENCY_NATIVE
    ? 'PEN'
    : activeDisplayMode === 'PEN'
      ? 'USD'
      : DISPLAY_CURRENCY_NATIVE;

  const scatterSeries = useMemo(() => detailRows
    .map((row, idx) => {
      const closedDate = parseDisplayDate(row.closed);
      const pct = row.costBasis ? (row.total / row.costBasis) * 100 : 0;
      return {
        id: `${row.symbol}-${idx}`,
        date: closedDate,
        rawDate: row.closed,
        pct,
        total: row.total,
        chartTotal: row.chartTotal,
        symbol: row.symbol,
        qty: row.qty,
        gainPct: row.gainPct,
        currency: row.currency,
        };
    })
    .filter((point) => point.date && Number.isFinite(point.pct))
    .sort((a, b) => a.date - b.date), [detailRows]);

  const hasDetails = detailRows.length > 0;
  const totalDetailRows = detailRows.length;
  const resolvedDetailPageSize = detailPageSize === PAGE_SIZE_ALL ? totalDetailRows || 1 : detailPageSize;
  const totalDetailPages = Math.max(1, Math.ceil(totalDetailRows / resolvedDetailPageSize));

  useEffect(() => {
    setDetailPage(1);
  }, [portfolioId, realizedRange, customFrom, customTo, symbolFilter, displayCurrency, realizedData?.period?.from, realizedData?.period?.to]);

  useEffect(() => {
    if (detailPage > totalDetailPages) {
      setDetailPage(totalDetailPages);
    }
  }, [detailPage, totalDetailPages]);

  const paginatedDetailRows = useMemo(() => {
    if (detailPageSize === PAGE_SIZE_ALL) return detailRows;
    const start = (detailPage - 1) * resolvedDetailPageSize;
    return detailRows.slice(start, start + resolvedDetailPageSize);
  }, [detailRows, detailPage, detailPageSize, resolvedDetailPageSize]);

  const detailRangeStart = totalDetailRows === 0 ? 0 : ((detailPage - 1) * resolvedDetailPageSize) + 1;
  const detailRangeEnd = totalDetailRows === 0 ? 0 : Math.min(detailPage * resolvedDetailPageSize, totalDetailRows);

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
            display_currency: displayCurrency,
            ...(symbolFilter.trim() ? { symbol: symbolFilter.trim() } : {}),
            from: preset.from,
            to: preset.to,
          });
        } else {
          await loadRealized({ display_currency: displayCurrency });
        }
      }
    }
  };

  const gainsAbs = Math.max(0, breakdown.gains);
  const lossesAbs = Math.abs(breakdown.losses);
  const longTermPct = termBreakdown.longTermCostBasis ? (totalsDisplay.longTerm / termBreakdown.longTermCostBasis) * 100 : 0;
  const shortTermPct = termBreakdown.shortTermCostBasis ? (totalsDisplay.shortTerm / termBreakdown.shortTermCostBasis) * 100 : 0;
  const valueColor = (value) => {
    if (value === 0) return 'var(--text)';
    return value > 0 ? 'var(--accent)' : 'var(--danger)';
  };

  const renderPercentMeta = (value, pct) => {
    if (value === 0) return '(N/A)';
    const prefix = pct > 0 ? '+' : '';
    return `(${prefix}${formatPercent(pct)})`;
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
  const renderNativeAmountRows = (selector, { emphasizeNet = false, showLossAbs = false, forceNeutral = false } = {}) => nativeSummary.map((bucket) => {
    const value = selector(bucket);
    const displayValue = showLossAbs ? Math.abs(value) : value;
    return (
      <div className="row" style={{ justifyContent: 'space-between' }} key={`${bucket.currency}-${selector.name || 'value'}`}>
        <span style={{ fontSize: emphasizeNet ? 13 : 12, fontWeight: emphasizeNet ? 600 : 500 }}>{bucket.currency === 'USD' ? '$' : 'S/'}</span>
        <span
          className={emphasizeNet ? 'tile-value' : undefined}
          style={{ color: forceNeutral ? 'var(--text)' : valueColor(value), fontSize: emphasizeNet ? undefined : 12 }}
        >
          {formatMoney(displayValue, bucket.currency)}
        </span>
      </div>
    );
  });

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
            {hasData ? (
              <>
                {/* Base arc (red remainder) */}
                <path
                  d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                  fill="transparent"
                  stroke="#ef4444"
                  strokeWidth="6"
                  strokeLinecap="butt"
                />
                {/* Gain arc (green) overlays the left portion */}
                <path
                  d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                  fill="transparent"
                  stroke="#22c55e"
                  strokeWidth="6"
                  strokeLinecap="butt"
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
                strokeLinecap="butt"
              />
            )}
            {/* Center text */}
            <text x="21" y="18" textAnchor="middle" fill="var(--text)" fontSize="5.2" fontWeight="700">
              {hasData ? `${gainPct}%` : '—'}
            </text>
            <text x="21" y="23" textAnchor="middle" fill="var(--muted)" fontSize="3">
              {hasData ? 'ratio G/P' : 'sin datos'}
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
                <div style={{ minWidth: 140 }}>
                  <DatePicker
                    label=""
                    value={customFrom}
                    onChange={setCustomFrom}
                    min={minDateISO}
                    max={maxDateISO}
                    placeholder="dd/mm/aaaa"
                  />
                </div>
                <span className="muted" style={{ fontSize: 12 }}>a</span>
                <div style={{ minWidth: 140 }}>
                  <DatePicker
                    label=""
                    value={customTo}
                    onChange={setCustomTo}
                    min={minDateISO}
                    max={maxDateISO}
                    placeholder="dd/mm/aaaa"
                  />
                </div>
              </div>
            )}
          </div>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Símbolo (opcional)</div>
            <input className="input" placeholder="ej. AAPL" value={symbolFilter} onChange={e => setSymbolFilter(e.target.value)} />
          </div>
          <div style={{ alignSelf: 'stretch', display: 'flex', alignItems: 'flex-end' }}>
            <button className="btn primary" type="submit" disabled={!portfolioId}>
              Buscar
            </button>
          </div>
          <div style={{ marginLeft: 'auto', alignSelf: 'flex-start', display: 'flex', alignItems: 'flex-start' }}>
            <button
              type="button"
              className="btn xs ghost"
              onClick={() => setDisplayCurrency(nextDisplayCurrency)}
              style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {currencyToggleLabel}
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
                  <div>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13 }}>Ingresos totales</span>
                    </div>
                    {activeDisplayMode === DISPLAY_CURRENCY_NATIVE
                      ? renderNativeAmountRows((bucket) => bucket.proceeds, { forceNeutral: true })
                      : (
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span />
                          <span className="tile-value">{formatMoney(totalsDisplay.proceeds, summaryCurrency)}</span>
                        </div>
                      )}
                  </div>
                  <div>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13 }}>Base de costo total</span>
                    </div>
                    {activeDisplayMode === DISPLAY_CURRENCY_NATIVE
                      ? renderNativeAmountRows((bucket) => bucket.costBasis, { forceNeutral: true })
                      : (
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span />
                          <span className="tile-value">{formatMoney(totalsDisplay.costBasis, summaryCurrency)}</span>
                        </div>
                      )}
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Ganancia/Pérdida</div>
                <div className="grid" style={{ gap: 8, fontSize: 12 }}>
                  {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? (
                    <>
                      <div>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span className="muted">Largo plazo</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.longTerm)}
                      </div>
                      <div>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span className="muted">Corto plazo</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.shortTerm)}
                      </div>
                      <div>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span className="muted">Ganancia neta</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.netGain, { emphasizeNet: true })}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span className="muted">Largo plazo</span>
                        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
                          <span style={{ color: valueColor(totalsDisplay.longTerm) }}>
                            {formatMoney(totalsDisplay.longTerm, summaryCurrency)}
                          </span>
                          <span style={{ fontSize: 11, color: valueColor(totalsDisplay.longTerm) }}>
                            {renderPercentMeta(totalsDisplay.longTerm, longTermPct)}
                          </span>
                        </div>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span className="muted">Corto plazo</span>
                        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
                          <span style={{ color: valueColor(totalsDisplay.shortTerm) }}>
                            {formatMoney(totalsDisplay.shortTerm, summaryCurrency)}
                          </span>
                          <span style={{ fontSize: 11, color: valueColor(totalsDisplay.shortTerm) }}>
                            {renderPercentMeta(totalsDisplay.shortTerm, shortTermPct)}
                          </span>
                        </div>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span className="muted">Ganancia neta</span>
                        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
                          <span style={{ color: valueColor(totalsDisplay.netGain) }}>
                            {formatMoney(totalsDisplay.netGain, summaryCurrency)}
                          </span>
                          <span style={{ fontSize: 11, color: valueColor(totalsDisplay.netGain) }}>
                            {renderPercentMeta(totalsDisplay.netGain, totalsDisplay.gainPct)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Totales</div>
                <div className="grid" style={{ gap: 10 }}>
                  {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? (
                    <>
                      <div>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 13 }}>Ganancias totales</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.gains)}
                      </div>
                      <div>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 13 }}>Pérdidas totales</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.losses, { showLossAbs: true })}
                      </div>
                      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 4 }}>
                        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>Ganancia neta</span>
                        </div>
                        {renderNativeAmountRows((bucket) => bucket.netGain, { emphasizeNet: true })}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13 }}>Ganancias totales</span>
                        <span className="tile-value" style={{ color: valueColor(gainsAbs) }}>{formatMoney(gainsAbs, summaryCurrency)}</span>
                      </div>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13 }}>Pérdidas totales</span>
                        <span className="tile-value" style={{ color: valueColor(breakdown.losses) }}>{formatMoney(lossesAbs, summaryCurrency)}</span>
                      </div>
                      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 4 }}>
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>Ganancia neta</span>
                          <span className="tile-value" style={{ color: valueColor(totalsDisplay.netGain) }}>
                            {formatMoney(totalsDisplay.netGain, summaryCurrency)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
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
                  <div>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13 }}>Ingresos totales</span>
                    </div>
                    {activeDisplayMode === DISPLAY_CURRENCY_NATIVE
                      ? renderNativeAmountRows((bucket) => bucket.proceeds, { forceNeutral: true })
                      : (
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span />
                          <span className="tile-value">{formatMoney(totalsDisplay.proceeds, summaryCurrency)}</span>
                        </div>
                      )}
                  </div>
                  <div>
                    <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13 }}>Base de costo total</span>
                    </div>
                    {activeDisplayMode === DISPLAY_CURRENCY_NATIVE
                      ? renderNativeAmountRows((bucket) => bucket.costBasis, { forceNeutral: true })
                      : (
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <span />
                          <span className="tile-value">{formatMoney(totalsDisplay.costBasis, summaryCurrency)}</span>
                        </div>
                      )}
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Promedios</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Ganancia promedio</span>
                    <span className="tile-value" style={{ color: valueColor(averages.gainPct) }}>{formatPercent(averages.gainPct)}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Pérdida promedio</span>
                    <span className="tile-value" style={{ color: valueColor(averages.lossPct) }}>{formatPercent(averages.lossPct)}</span>
                  </div>
                </div>
              </div>

              <div className="realized-panel">
                <div className="tile-title">Transacciones</div>
                <div className="grid" style={{ gap: 10 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Con ganancia</span>
                    <span className="tile-value" style={{ color: valueColor(counts.gain) }}>{counts.gain}</span>
                  </div>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13 }}>Con pérdida</span>
                    <span className="tile-value" style={{ color: valueColor(-counts.loss) }}>{counts.loss}</span>
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
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          {activeDisplayMode === DISPLAY_CURRENCY_NATIVE
            ? 'Valores en moneda original usando método de costo promedio.'
            : `Valores en ${currencyLabel} usando método de costo promedio.`}
        </div>
        {(() => {
          if (!scatterSeries.length) {
            return (
              <div className="card" style={{ padding: 12, marginBottom: 12, fontSize: 12, color: 'var(--danger)' }}>
                Aún no hay movimientos realizados en el período seleccionado para graficar.
              </div>
            );
          }
          const w = 1200;
          const h = 480;
          const leftPad = 52;
          const rightPad = 8;
          const topPad = 16;
          const bottomPad = 40;
          const plotWidth = w - leftPad - rightPad;
          const plotHeight = h - topPad - bottomPad;
          const pctValues = scatterSeries.map((point) => point.pct);
          const magnitudeValues = scatterSeries.map((point) => Math.abs(
            activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? point.total : point.chartTotal,
          ));
          const maxMagnitude = Math.max(...magnitudeValues, 0);
          const niceY = buildNiceTicks(Math.min(...pctValues), Math.max(...pctValues), 4);
          const domainMin = niceY.min;
          const domainMax = niceY.max;
          const domainSpan = domainMax - domainMin || 1;
          const minTime = scatterSeries[0].date.getTime();
          const maxTime = scatterSeries[scatterSeries.length - 1].date.getTime();
          const timeSpan = maxTime - minTime || 1;
          const yFor = (value) => topPad + ((domainMax - value) / domainSpan) * plotHeight;
          const xFor = (date) => {
            if (scatterSeries.length === 1) return leftPad + plotWidth / 2;
            return leftPad + ((date.getTime() - minTime) / timeSpan) * plotWidth;
          };
          const gridValues = niceY.ticks;
          const xTickCount = 4;
          const xTicks = Array.from({ length: xTickCount }, (_, idx) => {
            const ratio = xTickCount === 1 ? 0 : idx / (xTickCount - 1);
            const tickTime = minTime + (timeSpan * ratio);
            return new Date(tickTime);
          });
          const formatShortDate = (date) => date?.toLocaleDateString('es-PE', { day: 'numeric', month: 'short' }) || '—';
          const formatAxisPct = (value) => `${value > 0 ? '+' : ''}${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}%`;
          const zeroY = yFor(0);
          const showZeroLine = domainMin <= 0 && domainMax >= 0;
          const radiusFor = (magnitude) => {
            if (maxMagnitude <= 0) return 12;
            const normalized = Math.sqrt(Math.max(0, magnitude) / maxMagnitude);
            return 2 + (normalized * 40);
          };
          const scatterBubbles = scatterSeries
            .map((point) => ({
              ...point,
              radius: radiusFor(Math.abs(
                activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? point.total : point.chartTotal,
              )),
            }))
            .sort((a, b) => b.radius - a.radius);
          const fmtTooltipSigned = (value, currency) => `${value >= 0 ? '+' : '-'}${formatMoney(Math.abs(value), currency)}`;
          const getTooltipPosition = (event) => {
            const svgRect = event.currentTarget?.ownerSVGElement?.getBoundingClientRect();
            if (!svgRect) return null;
            return {
              x: event.clientX - svgRect.left + 10,
              y: event.clientY - svgRect.top - 10,
            };
          };
          const handlePointEnter = (event, point) => {
            const position = getTooltipPosition(event);
            if (!position) return;
            setChartTooltip({
              x: position.x,
              y: position.y,
              point,
            });
          };
          const handlePointMove = (event) => {
            const position = getTooltipPosition(event);
            if (!position) return;
            setChartTooltip((current) => (
              current
                ? { ...current, x: position.x, y: position.y }
                : current
            ));
          };
          return (
            <div style={{ width: '90%', margin: '0 auto 12px', padding: 4, position: 'relative' }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
                <div className="muted" style={{ fontSize: 12 }}>
                  Rendimiento realizado por operación (%)
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Gráfico basado en {scatterSeries.length} registros
                </div>
              </div>
              <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 460, display: 'block' }}>
                {gridValues.map((value, idx) => {
                  const y = yFor(value);
                  return (
                    <g key={`grid-${idx}`}>
                      <line
                        x1={leftPad}
                        y1={y}
                        x2={w - rightPad}
                        y2={y}
                        stroke="rgba(157,176,208,0.16)"
                        strokeWidth="0.5"
                      />
                      <text
                        x={leftPad - 1.5}
                        y={y + 4}
                        textAnchor="end"
                        fill="var(--muted)"
                        fontSize="11"
                      >
                        {formatAxisPct(value)}
                      </text>
                    </g>
                  );
                })}
                {showZeroLine && (
                  <line
                    x1={leftPad}
                    y1={zeroY}
                    x2={w - rightPad}
                    y2={zeroY}
                    stroke="rgba(157,176,208,0.32)"
                    strokeWidth="0.65"
                  />
                )}
                {xTicks.map((tick, idx) => {
                  const x = xFor(tick);
                  return (
                    <g key={`tick-${idx}`}>
                      <line
                        x1={x}
                        y1={topPad}
                        x2={x}
                        y2={h - bottomPad}
                        stroke="rgba(157,176,208,0.08)"
                        strokeWidth="0.45"
                      />
                      <text
                        x={x}
                        y={h - 12}
                        textAnchor="middle"
                        fill="var(--muted)"
                        fontSize="11"
                      >
                        {formatShortDate(tick)}
                      </text>
                    </g>
                  );
                })}
                {scatterBubbles.map((point) => {
                  const x = xFor(point.date);
                  const y = yFor(point.pct);
                  const stroke = point.total > 0 ? 'var(--accent)' : point.total < 0 ? 'var(--danger)' : 'var(--text)';
                  const fill = point.total > 0
                    ? 'rgba(34,197,94,0.20)'
                    : point.total < 0
                      ? 'rgba(239,68,68,0.20)'
                      : 'rgba(231,238,252,0.18)';
                  return (
                    <circle
                      key={point.id}
                      cx={x}
                      cy={y}
                      r={point.radius}
                      fill={fill}
                      stroke={stroke}
                      strokeWidth="2"
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(event) => handlePointEnter(event, point)}
                      onMouseMove={handlePointMove}
                      onMouseLeave={() => setChartTooltip(null)}
                    />
                  );
                })}
              </svg>
              {chartTooltip && (
                <div
                  className="card"
                  style={{
                    position: 'absolute',
                    left: Math.min(chartTooltip.x, 760),
                    top: Math.max(chartTooltip.y, 44),
                    padding: '10px 12px',
                    minWidth: 220,
                    pointerEvents: 'none',
                    zIndex: 3,
                    boxShadow: '0 10px 24px rgba(0,0,0,.35)',
                    background: 'linear-gradient(180deg, rgba(18,26,47,.98), rgba(12,20,39,.98))',
                  }}
                >
                  <div style={{ fontSize: 12, marginBottom: 6 }}>
                    <span className="muted">Closed Date:</span>{' '}
                    <span>{formatDateLabel(chartTooltip.point.rawDate)}</span>
                  </div>
                  <div style={{ fontSize: 12, marginBottom: 6 }}>
                    <span className="muted">Transaction:</span>{' '}
                    <span>{chartTooltip.point.symbol} Sold {chartTooltip.point.qty}</span>
                  </div>
                  <div style={{ fontSize: 12 }}>
                    <span className="muted">Gain:</span>{' '}
                    <span style={{ color: valueColor(chartTooltip.point.total) }}>
                      {fmtTooltipSigned(chartTooltip.point.total, chartTooltip.point.currency)} ({chartTooltip.point.gainPct >= 0 ? '+' : ''}{formatPercent(chartTooltip.point.gainPct)})
                    </span>
                  </div>
                </div>
              )}
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
          const fmtSigned = (v, currency) => `${v >= 0 ? '+' : ''}${formatMoney(v, currency)}`;
          const fmtDate = (iso) => {
            if (!iso) return '—';
            const d = parseDisplayDate(iso);
            return d ? d.toLocaleDateString('es-PE') : iso;
          };
          const formatQty = (qty) => {
            const num = Number(qty);
            if (!Number.isFinite(num)) return '0';
            return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
          };
          const totalsRow = totalsDisplay;
          const nativeTotalRows = nativeSummary.map((bucket) => ({
            label: bucket.currency === 'USD' ? 'Totales por moneda original ($)' : 'Totales por moneda original (S/)',
            currency: bucket.currency,
            proceeds: bucket.proceeds,
            costBasis: bucket.costBasis,
            netGain: bucket.netGain,
            longTerm: bucket.longTerm,
            shortTerm: bucket.shortTerm,
          }));
          return (
            <>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
                <div className="muted" style={{ fontSize: 12 }}>
                  {totalDetailRows === 0
                    ? '0 resultados'
                    : `${detailRangeStart}-${detailRangeEnd} de ${totalDetailRows} resultados`}
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <span className="muted" style={{ fontSize: 12 }}>Máx. entradas</span>
                  <select
                    className="select"
                    value={detailPageSize}
                    onChange={(e) => {
                      const nextValue = e.target.value === PAGE_SIZE_ALL ? PAGE_SIZE_ALL : Number(e.target.value);
                      setDetailPageSize(nextValue);
                      setDetailPage(1);
                    }}
                    style={{ minWidth: 92 }}
                  >
                    {PAGE_SIZE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option === PAGE_SIZE_ALL ? 'Todos' : option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="scroll-pretty" style={{ width: '100%', maxWidth: '100%', overflowX: 'auto', WebkitOverflowScrolling: 'touch', fontSize: 11, lineHeight: 1.25, color: 'var(--danger)' }}>
                <table className="table positions-table realized-details-table" style={{ minWidth: 1100, fontSize: 11 }}>
                  <thead>
                    <tr style={{ textAlign: 'left' }}>
                      <th className="sticky-col" style={{ whiteSpace: 'nowrap', minWidth: 90 }}>Símbolo</th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 380 }}>Descripción</th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>Fecha de cierre</th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 70 }}>Cantidad</th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Precio venta' : `Precio venta (${currencyLabel})`}
                      </th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 150 }}>Método de base de costo</th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Ingresos' : `Ingresos (${currencyLabel})`}
                      </th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 140 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Base de costo' : `Base de costo (${currencyLabel})`}
                      </th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 120 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Total' : `Total (${currencyLabel})`}
                      </th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 140 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Largo plazo' : `Largo plazo (${currencyLabel})`}
                      </th>
                      <th style={{ whiteSpace: 'nowrap', minWidth: 140 }}>
                        {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? 'Corto plazo' : `Corto plazo (${currencyLabel})`}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedDetailRows.map((r, idx) => (
                      <tr key={`${r.symbol}-${detailRangeStart + idx}`}>
                        <td className="sticky-col" style={{ fontWeight: 600, minWidth: 90 }}>{r.symbol}</td>
                        <td style={{ minWidth: 380 }}>{r.description}</td>
                        <td style={{ minWidth: 120 }}>{fmtDate(r.closed)}</td>
                        <td style={{ minWidth: 70 }}>{formatQty(r.qty)}</td>
                        <td style={{ minWidth: 120 }}>{formatMoney(r.price, r.currency)}</td>
                        <td style={{ minWidth: 150 }}>{r.cbMethod}</td>
                        <td style={{ minWidth: 120 }}>{formatMoney(r.proceeds, r.currency)}</td>
                        <td style={{ minWidth: 140 }}>{formatMoney(r.costBasis, r.currency)}</td>
                        <td style={{ minWidth: 120 }} className={r.total >= 0 ? 'up' : 'down'}>{fmtSigned(r.total, r.currency)}</td>
                        <td style={{ minWidth: 140 }} className={r.longTerm >= 0 ? 'up' : 'down'}>{formatMoney(r.longTerm, r.currency)}</td>
                        <td style={{ minWidth: 140 }} className={r.shortTerm >= 0 ? 'up' : 'down'}>{fmtSigned(r.shortTerm, r.currency)}</td>
                      </tr>
                    ))}
                    {activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? nativeTotalRows.map((row) => (
                      <tr key={`native-total-${row.currency}`} style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <td className="sticky-col" style={{ fontWeight: 700, minWidth: 90 }}>
                          <span
                            onMouseEnter={(event) => showTotalTooltip(event, row.label)}
                            onMouseLeave={hideTotalTooltip}
                            style={{ textDecoration: 'underline dotted', cursor: 'help', textDecorationColor: '#666' }}
                          >
                            {row.label}
                          </span>
                        </td>
                        <td style={{ minWidth: 380 }}>—</td>
                        <td style={{ minWidth: 120 }}>—</td>
                        <td style={{ minWidth: 70 }}>—</td>
                        <td style={{ minWidth: 120 }}>—</td>
                        <td style={{ minWidth: 150 }}>—</td>
                        <td style={{ minWidth: 120 }}>{formatMoney(row.proceeds, row.currency)}</td>
                        <td style={{ minWidth: 140 }}>{formatMoney(row.costBasis, row.currency)}</td>
                        <td style={{ minWidth: 120 }} className={row.netGain >= 0 ? 'up' : 'down'}>{fmtSigned(row.netGain, row.currency)}</td>
                        <td style={{ minWidth: 140 }} className={row.longTerm >= 0 ? 'up' : 'down'}>{formatMoney(row.longTerm, row.currency)}</td>
                        <td style={{ minWidth: 140 }} className={row.shortTerm >= 0 ? 'up' : 'down'}>{fmtSigned(row.shortTerm, row.currency)}</td>
                      </tr>
                    )) : (
                      <tr style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <td className="sticky-col" style={{ fontWeight: 700, minWidth: 90 }}>
                          <span
                            onMouseEnter={(event) => showTotalTooltip(event, 'Total de la cuenta')}
                            onMouseLeave={hideTotalTooltip}
                            style={{ textDecoration: 'underline dotted', cursor: 'help', textDecorationColor: '#666' }}
                          >
                            Total de la cuenta
                          </span>
                        </td>
                        <td style={{ minWidth: 380 }}>—</td>
                        <td style={{ minWidth: 120 }}>—</td>
                        <td style={{ minWidth: 70 }}>—</td>
                        <td style={{ minWidth: 120 }}>—</td>
                        <td style={{ minWidth: 150 }}>—</td>
                        <td style={{ minWidth: 120 }}>{formatMoney(totalsRow.proceeds, summaryCurrency)}</td>
                        <td style={{ minWidth: 140 }}>{formatMoney(totalsRow.costBasis, summaryCurrency)}</td>
                        <td style={{ minWidth: 120 }} className={totalsRow.netGain >= 0 ? 'up' : 'down'}>{fmtSigned(totalsRow.netGain, summaryCurrency)}</td>
                        <td style={{ minWidth: 140 }} className={totalsRow.longTerm >= 0 ? 'up' : 'down'}>{formatMoney(totalsRow.longTerm, summaryCurrency)}</td>
                        <td style={{ minWidth: 140 }} className={totalsRow.shortTerm >= 0 ? 'up' : 'down'}>{fmtSigned(totalsRow.shortTerm, summaryCurrency)}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {detailPageSize !== PAGE_SIZE_ALL && totalDetailPages > 1 && (
                <div className="row" style={{ justifyContent: 'flex-end', alignItems: 'center', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                  <span className="muted" style={{ fontSize: 12 }}>
                    Página {detailPage} de {totalDetailPages}
                  </span>
                  <button
                    type="button"
                    className="btn xs ghost"
                    onClick={() => setDetailPage((page) => Math.max(1, page - 1))}
                    disabled={detailPage <= 1}
                  >
                    Anterior
                  </button>
                  <button
                    type="button"
                    className="btn xs ghost"
                    onClick={() => setDetailPage((page) => Math.min(totalDetailPages, page + 1))}
                    disabled={detailPage >= totalDetailPages}
                  >
                    Siguiente
                  </button>
                </div>
              )}
            </>
          );
        })()}
      </div>
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

export default RealizedTab;
