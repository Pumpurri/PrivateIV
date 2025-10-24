import React, { useEffect, useMemo, useRef, useState } from 'react';
import DatePicker from '../components/DatePicker';
import TimeSeriesChart from '../components/TimeSeriesChart';
import { formatCurrency, formatPercent } from '../utils/format';
import { getPortfolioOverviewApi } from '../services/api';

const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_OVERVIEW_DAYS = 1825;
const MONTHS_PER_PRESET = {
  '1M': 1,
  '3M': 3,
  '6M': 6,
  '1Y': 12,
};
const REQUEST_BUFFER_DAYS = 7;

function parseSnapshotDate(value) {
  if (!value) return null;
  if (value instanceof Date) return new Date(value.getTime());
  if (typeof value === 'number' && Number.isFinite(value)) {
    const direct = new Date(value);
    return Number.isNaN(direct.getTime()) ? null : direct;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const dateOnlyMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnlyMatch) {
      const year = Number(dateOnlyMatch[1]);
      const month = Number(dateOnlyMatch[2]) - 1;
      const day = Number(dateOnlyMatch[3]);
      const local = new Date(year, month, day, 0, 0, 0, 0);
      return Number.isNaN(local.getTime()) ? null : local;
    }
    const parsed = Date.parse(trimmed);
    if (!Number.isNaN(parsed)) return new Date(parsed);
    return null;
  }
  const fallback = new Date(value);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}

function subtractMonths(date, months) {
  if (!Number.isFinite(months) || months <= 0) {
    return new Date(date.getTime());
  }
  const base = new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);
  base.setMonth(base.getMonth() - months);
  const lastDay = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
  const day = Math.min(date.getDate(), lastDay);
  return new Date(base.getFullYear(), base.getMonth(), day, 0, 0, 0, 0);
}

function getLatestSnapshotDate(snaps) {
  if (!Array.isArray(snaps) || snaps.length === 0) return null;
  const last = snaps[snaps.length - 1];
  const raw = last?.date ?? last?.timestamp ?? last?.t;
  return parseSnapshotDate(raw);
}

function computeDaysForPreset(preset, snaps) {
  if (preset === 'MAX') return MAX_OVERVIEW_DAYS;
  const today = new Date();
  const normalizedToday = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0, 0, 0, 0);
  const latestAvailable = getLatestSnapshotDate(snaps) || normalizedToday;
  const end = new Date(latestAvailable.getFullYear(), latestAvailable.getMonth(), latestAvailable.getDate(), 0, 0, 0, 0);
  let start;
  if (preset === 'YTD') {
    start = new Date(end.getFullYear(), 0, 1, 0, 0, 0, 0);
  } else {
    const months = MONTHS_PER_PRESET[preset] ?? 6;
    start = subtractMonths(end, months);
  }
  const spanDays = Math.max(0, Math.ceil((end - start) / DAY_MS) + 1);
  const staleDays = Math.max(0, Math.ceil((normalizedToday - end) / DAY_MS));
  const total = spanDays + staleDays + REQUEST_BUFFER_DAYS;
  return Math.min(MAX_OVERVIEW_DAYS, Math.max(total, 30));
}

const BalancesTab = ({ portfolio, transactions = [] }) => {
  const [selectedDate, setSelectedDate] = useState('');
  const minDateISO = useMemo(() => {
    const ca = portfolio?.created_at;
    if (!ca) return undefined;
    const d = new Date(ca);
    if (isNaN(d.getTime())) return undefined;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }, [portfolio?.created_at]);
  const maxDateISO = useMemo(() => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }, []);
  const [snapshots, setSnapshots] = useState([]);
  const [dayAbs, setDayAbs] = useState(0);
  const [dayPct, setDayPct] = useState(0);
  const [asOf, setAsOf] = useState(null);
  const [rangePreset, setRangePreset] = useState('6M');
  const [overviewLoading, setOverviewLoading] = useState(false);
  const overviewPortfolioRef = useRef(null);

  useEffect(() => {
    if (!portfolio?.id) return;
    const cacheKey = `${portfolio.id}-initial`;
    if (overviewPortfolioRef.current === cacheKey) return;
    let cancelled = false;
    setOverviewLoading(true);
    (async () => {
      try {
        // Initial load: fetch 6 months of data (default preset)
        const initialDays = computeDaysForPreset('6M');
        const data = await getPortfolioOverviewApi(portfolio.id, { days: initialDays });
        if (cancelled) return;
        overviewPortfolioRef.current = cacheKey;
        const snaps = Array.isArray(data?.snapshots) ? data.snapshots : [];
        setSnapshots(snaps);
        const dAbs = Number(data?.portfolio?.day_change_abs ?? 0);
        const dPct = Number(data?.portfolio?.day_change_pct ?? 0);
        if (Number.isFinite(dAbs) && Number.isFinite(dPct)) {
          setDayAbs(dAbs);
          setDayPct(dPct);
        } else if (snaps.length >= 2) {
          const prev = Number(snaps[snaps.length - 2]?.total_value || 0);
          const last = Number(snaps[snaps.length - 1]?.total_value || 0);
          const abs = last - prev;
          const pct = prev ? (abs / prev) * 100 : 0;
          setDayAbs(abs);
          setDayPct(pct);
        } else {
          setDayAbs(0);
          setDayPct(0);
        }
        setAsOf(null);
      } catch {
        if (cancelled) return;
        setSnapshots([]);
        setDayAbs(0);
        setDayPct(0);
      } finally {
        if (!cancelled) setOverviewLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [portfolio?.id]);

  async function handleSearch() {
    if (!selectedDate || !portfolio?.id) return;
    setOverviewLoading(true);
    try {
      const today = new Date();
      const sel = new Date(selectedDate + 'T00:00:00');
      const diffDays = Math.max(1, Math.ceil((today - sel) / DAY_MS) + 1);
      const days = Math.min(Math.max(diffDays, 30), MAX_OVERVIEW_DAYS);
      const data = await getPortfolioOverviewApi(portfolio.id, { days });
      const snaps = Array.isArray(data?.snapshots) ? data.snapshots : [];
      setSnapshots(snaps);
      if (!snaps.length) return;
      // Find snapshot on or before selectedDate
      let idx = -1;
      for (let i = 0; i < snaps.length; i++) {
        const d = String(snaps[i].date).slice(0, 10);
        if (d === selectedDate) { idx = i; break; }
        if (d <= selectedDate) { idx = i; }
      }
      if (idx < 0) idx = 0; // fallback to earliest available snapshot
      const cur = snaps[idx];
      const prev = idx > 0 ? snaps[idx - 1] : null;
      const total = Number(cur.total_value || 0);
      const cash = Number(cur.cash_balance || 0);
      const investment = Number(cur.investment_value || 0);
      const abs = prev ? (total - Number(prev.total_value || 0)) : 0;
      const prevTotal = prev ? Number(prev.total_value || 0) : 0;
      const pct = prev ? (prevTotal ? (abs / prevTotal) * 100 : 0) : 0;
      setAsOf({ date: selectedDate, total, cash, investment, dayAbs: abs, dayPct: pct });
    } catch {
      // keep previous values
    } finally {
      setOverviewLoading(false);
    }
  }

  const balanceSeries = useMemo(() => {
    return (snapshots || []).map(snap => {
      const dateValue = snap.date ?? snap.timestamp;
      if (!dateValue) return null;
      const total = Number(snap.total_value ?? snap.total ?? 0);
      if (!Number.isFinite(total)) return null;
      return { t: dateValue, v: total };
    }).filter(Boolean);
  }, [snapshots]);

  const handleRangeChange = async ({ preset }) => {
    if (!preset || !portfolio?.id) return;

    console.log('Range change requested:', preset);
    setRangePreset(preset);

    const days = computeDaysForPreset(preset, snapshots);
    console.log('Fetching snapshots for preset:', preset, 'days:', days);

    // Fetch data for the new range
    setOverviewLoading(true);
    try {
      const data = await getPortfolioOverviewApi(portfolio.id, { days });
      const snaps = Array.isArray(data?.snapshots) ? data.snapshots : [];
      setSnapshots(snaps);
      console.log('Received', snaps.length, 'snapshots for', days, 'days');

      // Update day change if available
      const dAbs = Number(data?.portfolio?.day_change_abs ?? 0);
      const dPct = Number(data?.portfolio?.day_change_pct ?? 0);
      if (Number.isFinite(dAbs) && Number.isFinite(dPct)) {
        setDayAbs(dAbs);
        setDayPct(dPct);
      }
    } catch (error) {
      console.error('Failed to fetch data for range:', error);
    } finally {
      setOverviewLoading(false);
    }
  };

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="card" style={{ padding: 16 }}>
        {/* View historical balances (search) */}
        <div style={{ marginBottom: 12 }}>
          <strong>Consultar balances históricos</strong>
          <div className="row" style={{ gap: 8, marginTop: 8 }}>
            <div style={{ minWidth: 140 }}>
              <DatePicker
                label=""
                value={selectedDate}
                onChange={setSelectedDate}
                min={minDateISO}
                max={maxDateISO}
                placeholder="dd/mm/aaaa"
              />
            </div>
            <button className="btn xs primary" style={{ fontSize: 12, padding: '4px 12px' }} onClick={handleSearch}>Buscar</button>
          </div>
          {asOf && (
            <div style={{ marginTop: 6 }}>
              <button
                className="btn xs ghost"
                onClick={() => {
                  setAsOf(null);
                  // Reload data for current preset by triggering handleRangeChange
                  handleRangeChange({ preset: rangePreset });
                }}
                style={{ fontSize: 11, padding: '2px 8px' }}
              >
                Volver al balance actual
              </button>
            </div>
          )}
        </div>

        <div
          className="grid"
          style={{
            gridTemplateColumns: 'repeat(4, max-content)',
            gap: 48,
            marginBottom: 12,
            justifyItems: 'start',
            justifyContent: 'start',
            alignItems: 'start'
          }}
        >
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Valor de la cuenta</div>
            <div style={{ fontWeight: 700, fontSize: 20 }}>{formatCurrency(asOf ? asOf.total : (portfolio?.total_value || 0))}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Variación diaria</div>
            <div className={(asOf ? asOf.dayAbs : dayAbs) > 0 ? 'up' : ((asOf ? asOf.dayAbs : dayAbs) < 0 ? 'down' : '')} style={{ fontSize: 18 }}>
              {((asOf ? asOf.dayAbs : dayAbs) >= 0 ? '+' : '')}{formatCurrency(Math.abs(asOf ? asOf.dayAbs : dayAbs))} ({formatPercent(asOf ? asOf.dayPct : dayPct)})
            </div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Efectivo</div>
            <div style={{ fontSize: 18 }}>{formatCurrency(asOf ? asOf.cash : (portfolio?.cash_balance || 0))}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 12 }}>Valor de mercado</div>
            <div style={{ fontSize: 18 }}>{formatCurrency(asOf ? asOf.investment : (portfolio?.current_investment_value || 0))}</div>
          </div>
        </div>

        <div className="card" style={{ padding: '12px 12px 30px 12px' }}>
          <TimeSeriesChart
            series={balanceSeries}
            rangePreset={rangePreset}
            onRangeChange={handleRangeChange}
            yFormat="currency"
            currency="PEN"
            showArea
            loading={overviewLoading}
            ariaLabel="Evolución del balance del portafolio"
          />
        </div>
      </div>

      {/* Balance details: totals of deposits and withdrawals for the last years */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <strong>Detalle de balances</strong>
        </div>

        {(() => {
          // Aggregate deposits/withdrawals by year using provided transactions
          const agg = new Map();
          (transactions || []).forEach(t => {
            const ts = t.timestamp || t.date;
            const type = (t.transaction_type || '').toString().toLowerCase();
            const amt = Number(t.amount ?? 0);
            if (!ts || !amt) return;
            const year = new Date(ts).getFullYear();
            if (!agg.has(year)) agg.set(year, { deposits: 0, withdrawals: 0 });
            if (type.includes('deposit')) agg.get(year).deposits += amt;
            if (type.includes('withdrawal') || type.includes('retiro')) agg.get(year).withdrawals += amt;
          });
          const years = Array.from(agg.keys())
            .sort((a,b) => b - a)
            .filter(y => (agg.get(y).deposits || 0) > 0 || (agg.get(y).withdrawals || 0) > 0)
            .slice(0, 2);

          if (years.length === 0) return <div className="muted">No hay depósitos ni retiros registrados.</div>;

          return (
            <table className="table" style={{ maxWidth: 520 }}>
              <thead>
                <tr style={{ textAlign: 'left' }}>
                  <th>Año</th>
                  <th>Total depósitos</th>
                  <th>Total retiros</th>
                </tr>
              </thead>
              <tbody>
                {years.map(y => (
                  <tr key={y}>
                    <td>{y}</td>
                    <td>{formatCurrency(agg.get(y).deposits || 0)}</td>
                    <td>{formatCurrency(agg.get(y).withdrawals || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          );
        })()}
      </div>
    </div>
  );
};

export default BalancesTab;
