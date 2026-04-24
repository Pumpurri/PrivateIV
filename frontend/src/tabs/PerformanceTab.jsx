import React, { useEffect, useMemo, useState, useCallback } from 'react';
import DatePicker from '../components/DatePicker';
import TimeSeriesChart from '../components/TimeSeriesChart';
import { formatCurrency, formatPercent } from '../utils/format';
import { getPortfolioBenchmarksApi, getPortfolioOverviewApi } from '../services/api';

const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_OVERVIEW_DAYS = 3650;

const parseDate = (value) => {
  if (!value) return null;
  if (value instanceof Date) return new Date(value.getTime());
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number);
    return new Date(year, month - 1, day, 0, 0, 0, 0);
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const toISODate = (date) => {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
};

const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
const endOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);

const subtractMonths = (date, months) => {
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
  target.setMonth(target.getMonth() - months);
  return target;
};

const clampDate = (date, minDate, maxDate) => {
  if (date < minDate) return new Date(minDate.getTime());
  if (date > maxDate) return new Date(maxDate.getTime());
  return date;
};

const formatRangeLabel = (from, to) => {
  if (!from || !to) return 'Sin rango';
  return `${from.toLocaleDateString('es-PE')} – ${to.toLocaleDateString('es-PE')}`;
};

const DEFAULT_DISPLAY_CURRENCY = 'PEN';
const BENCHMARK_COLOR_MAP = {
  djia: '#F59E0B',
  nasdaq: '#06B6D4',
  sp500: '#EC4899',
  r2k: '#A855F7',
};

const formatDisplayCurrency = (value, currency) => {
  if (value === null || value === undefined || value === '') return '-';
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  const prefix = currency === 'USD' ? '$' : 'S/. ';
  return `${prefix}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatSignedDisplayCurrency = (value, currency) => {
  if (value === null || value === undefined || value === '') return '-';
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  if (num === 0) return formatDisplayCurrency(0, currency);
  return `${num > 0 ? '+' : '-'}${formatDisplayCurrency(Math.abs(num), currency)}`;
};

const toDisplayTransactionAmount = (txn, displayCurrency) => {
  const type = String(txn?.transaction_type || '').toUpperCase();
  if (type !== 'DEPOSIT' && type !== 'WITHDRAWAL') return 0;
  const rawAmount = Number(txn?.amount || 0);
  const fxRate = Number(txn?.fx_rate || 1);
  const cashCurrency = String(txn?.cash_currency || 'PEN').toUpperCase();
  let amountInDisplay = rawAmount;

  if (displayCurrency === 'USD') {
    amountInDisplay = cashCurrency === 'PEN'
      ? rawAmount / (fxRate > 0 ? fxRate : 1)
      : rawAmount;
  } else {
    amountInDisplay = cashCurrency === 'USD'
      ? rawAmount * (fxRate > 0 ? fxRate : 1)
      : rawAmount;
  }

  return type === 'WITHDRAWAL' ? -amountInDisplay : amountInDisplay;
};

const PerformanceTab = ({ portfolio, transactions = [] }) => {
  const [perfSubTab, setPerfSubTab] = useState('performance');
  const [perfIndexSel, setPerfIndexSel] = useState({ djia: false, nasdaq: false, sp500: false, r2k: false });
  const [perfQuickRange, setPerfQuickRange] = useState('3M');
  const [perfFrom, setPerfFrom] = useState('');
  const [perfTo, setPerfTo] = useState('');
  const [perfHistoryOpen, setPerfHistoryOpen] = useState({});
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [snapshots, setSnapshots] = useState([]);
  const [overviewPortfolio, setOverviewPortfolio] = useState(null);
  const [benchmarkRows, setBenchmarkRows] = useState([]);
  const [benchmarkPortfolio, setBenchmarkPortfolio] = useState(null);
  const [performanceHistory, setPerformanceHistory] = useState(null);
  const [perfDisplayCurrency, setPerfDisplayCurrency] = useState(
    String(portfolio?.reporting_currency || portfolio?.base_currency || DEFAULT_DISPLAY_CURRENCY).toUpperCase() === 'USD'
      ? 'USD'
      : 'PEN',
  );

  const transactionRows = useMemo(() => (
    Array.isArray(transactions?.results) ? transactions.results : (Array.isArray(transactions) ? transactions : [])
  ), [transactions]);

  const snapshotRows = useMemo(() => (
    (snapshots || [])
      .map((snap) => {
        const date = parseDate(snap.date ?? snap.timestamp ?? snap.t);
        const totalValue = Number(snap.total_value ?? snap.total ?? 0);
        const cashBalance = Number(snap.cash_balance ?? 0);
        const investmentValue = Number(snap.investment_value ?? 0);
        return date && Number.isFinite(totalValue)
          ? {
              date,
              totalValue,
              cashBalance: Number.isFinite(cashBalance) ? cashBalance : 0,
              investmentValue: Number.isFinite(investmentValue) ? investmentValue : 0,
            }
          : null;
      })
      .filter(Boolean)
      .sort((a, b) => a.date - b.date)
  ), [snapshots]);

  const effectiveSnapshotRows = useMemo(() => {
    const rows = [...snapshotRows];
    const liveTotalValue = Number(overviewPortfolio?.total_value);
    const liveCashBalance = Number(overviewPortfolio?.cash_balance);
    const liveInvestmentValue = Number(overviewPortfolio?.current_investment_value);
    const today = startOfDay(new Date());

    if (!Number.isFinite(liveTotalValue)) return rows;

    const todayIso = toISODate(today);
    const lastIndex = rows.findIndex((row) => toISODate(row.date) === todayIso);
    if (lastIndex >= 0) {
      rows[lastIndex] = {
        ...rows[lastIndex],
        totalValue: liveTotalValue,
        cashBalance: Number.isFinite(liveCashBalance) ? liveCashBalance : rows[lastIndex].cashBalance,
        investmentValue: Number.isFinite(liveInvestmentValue) ? liveInvestmentValue : rows[lastIndex].investmentValue,
      };
      return rows.sort((a, b) => a.date - b.date);
    }

    rows.push({
      date: today,
      totalValue: liveTotalValue,
      cashBalance: Number.isFinite(liveCashBalance) ? liveCashBalance : 0,
      investmentValue: Number.isFinite(liveInvestmentValue) ? liveInvestmentValue : 0,
    });
    return rows.sort((a, b) => a.date - b.date);
  }, [
    snapshotRows,
    overviewPortfolio?.total_value,
    overviewPortfolio?.cash_balance,
    overviewPortfolio?.current_investment_value,
  ]);

  const earliestSnapshotDate = effectiveSnapshotRows[0]?.date || parseDate(portfolio?.created_at) || startOfDay(new Date());
  const latestSnapshotDate = effectiveSnapshotRows[effectiveSnapshotRows.length - 1]?.date || startOfDay(new Date());
  const minDateISO = toISODate(earliestSnapshotDate);
  const maxDateISO = toISODate(latestSnapshotDate);
  const currentYearLabel = String(latestSnapshotDate.getFullYear());

  const computeRangeForPreset = useCallback((preset) => {
    const maxDate = latestSnapshotDate;
    const minDate = earliestSnapshotDate;
    const end = startOfDay(maxDate);
    let start = startOfDay(maxDate);

    switch (preset) {
      case '3M':
        start = subtractMonths(end, 3);
        break;
      case '1Y':
        start = subtractMonths(end, 12);
        break;
      case 'CURRENT_YEAR':
      case 'YTD':
        start = new Date(end.getFullYear(), 0, 1, 0, 0, 0, 0);
        break;
      case 'MAX':
        start = startOfDay(minDate);
        break;
      default:
        start = subtractMonths(end, 3);
        break;
    }

    return {
      from: toISODate(clampDate(start, minDate, maxDate)),
      to: toISODate(end),
    };
  }, [earliestSnapshotDate, latestSnapshotDate]);

  useEffect(() => {
    if (!portfolio?.id) return;
    let cancelled = false;
    setOverviewLoading(true);

    const loadSnapshots = async () => {
      try {
        const createdAt = parseDate(portfolio.created_at) || new Date();
        const today = new Date();
        const days = Math.min(
          MAX_OVERVIEW_DAYS,
          Math.max(30, Math.ceil((today - createdAt) / DAY_MS) + 14),
        );
        const data = await getPortfolioOverviewApi(portfolio.id, { days, currency: perfDisplayCurrency });
        if (cancelled) return;
        const nextSnapshots = Array.isArray(data?.snapshots) ? data.snapshots : [];
        setSnapshots(nextSnapshots);
        setOverviewPortfolio(data?.portfolio || null);
      } catch {
        if (cancelled) return;
        setSnapshots([]);
        setOverviewPortfolio(null);
      } finally {
        if (!cancelled) setOverviewLoading(false);
      }
    };

    loadSnapshots();
    return () => {
      cancelled = true;
    };
  }, [portfolio?.id, portfolio?.created_at, perfDisplayCurrency]);

  useEffect(() => {
    const nextCurrency = String(portfolio?.reporting_currency || portfolio?.base_currency || DEFAULT_DISPLAY_CURRENCY).toUpperCase() === 'USD'
      ? 'USD'
      : 'PEN';
    setPerfDisplayCurrency(nextCurrency);
  }, [portfolio?.reporting_currency, portfolio?.base_currency]);

  useEffect(() => {
    if (!effectiveSnapshotRows.length) return;
    if (perfFrom && perfTo) return;
    const initialRange = computeRangeForPreset('3M');
    setPerfFrom(initialRange.from);
    setPerfTo(initialRange.to);
  }, [effectiveSnapshotRows, perfFrom, perfTo, computeRangeForPreset]);

  useEffect(() => {
    if (!portfolio?.id || !perfFrom || !perfTo) return;
    let cancelled = false;
    setBenchmarkLoading(true);

    const loadBenchmarks = async () => {
      try {
        const data = await getPortfolioBenchmarksApi(portfolio.id, {
          from: perfFrom,
          to: perfTo,
          codes: 'djia,nasdaq,sp500,r2k',
          currency: perfDisplayCurrency,
        });
        if (cancelled) return;
        setBenchmarkRows(Array.isArray(data?.benchmarks) ? data.benchmarks : []);
        setBenchmarkPortfolio(data?.portfolio || null);
        setPerformanceHistory(data?.history || null);
      } catch {
        if (cancelled) return;
        setBenchmarkRows([]);
        setBenchmarkPortfolio(null);
        setPerformanceHistory(null);
      } finally {
        if (!cancelled) setBenchmarkLoading(false);
      }
    };

    loadBenchmarks();
    return () => {
      cancelled = true;
    };
  }, [portfolio?.id, perfFrom, perfTo, perfDisplayCurrency]);

  const filteredSnapshots = useMemo(() => {
    if (!effectiveSnapshotRows.length) return [];
    const fromDate = perfFrom ? startOfDay(parseDate(perfFrom)) : startOfDay(earliestSnapshotDate);
    const toDate = perfTo ? endOfDay(parseDate(perfTo)) : endOfDay(latestSnapshotDate);
    return effectiveSnapshotRows.filter((snap) => snap.date >= fromDate && snap.date <= toDate);
  }, [effectiveSnapshotRows, perfFrom, perfTo, earliestSnapshotDate, latestSnapshotDate]);

  const filteredTransactions = useMemo(() => {
    const fromDate = perfFrom ? startOfDay(parseDate(perfFrom)) : startOfDay(earliestSnapshotDate);
    const toDate = perfTo ? endOfDay(parseDate(perfTo)) : endOfDay(latestSnapshotDate);
    return transactionRows
      .filter((txn) => {
        const date = parseDate(txn.timestamp);
        if (!date) return false;
        return date >= fromDate && date <= toDate;
      })
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }, [transactionRows, perfFrom, perfTo, earliestSnapshotDate, latestSnapshotDate]);

  const contributionsByDate = useMemo(() => {
    const byDate = new Map();
    filteredTransactions.forEach((txn) => {
      const txnDate = parseDate(txn.timestamp);
      if (!txnDate) return;
      const key = toISODate(txnDate);
      byDate.set(key, (byDate.get(key) || 0) + toDisplayTransactionAmount(txn, perfDisplayCurrency));
    });
    return byDate;
  }, [filteredTransactions, perfDisplayCurrency]);

  const perfSeries = useMemo(() => {
    if (!filteredSnapshots.length) return { portfolioValue: [], contrib: [] };
    let runningContributions = 0;
    const portfolioValue = [];
    const contrib = [];
    const beginningValue = Number(filteredSnapshots[0]?.totalValue || 0);

    filteredSnapshots.forEach((snap) => {
      const key = toISODate(snap.date);
      runningContributions += contributionsByDate.get(key) || 0;
      portfolioValue.push(Number(snap.totalValue || 0));
      contrib.push(beginningValue + runningContributions);
    });

    return { portfolioValue, contrib };
  }, [filteredSnapshots, contributionsByDate]);

  const perfChartSeriesList = useMemo(() => {
    const portfolioValueSeries = filteredSnapshots.map((snap, index) => ({
      t: snap.date,
      v: perfSeries.portfolioValue[index] ?? 0,
    }));
    const contributionSeries = filteredSnapshots.map((snap, index) => ({
      t: snap.date,
      v: perfSeries.contrib[index] ?? 0,
    }));

    return [
      {
        id: 'portfolio-value',
        label: 'Valor total del portafolio',
        color: '#3B82F6',
        areaColor: 'rgba(59,130,246,0.12)',
        series: portfolioValueSeries,
      },
      {
        id: 'net-contrib',
        label: 'Valor inicial + aportes netos',
        color: 'rgba(157,176,208,0.95)',
        areaColor: 'rgba(157,176,208,0.08)',
        strokeDasharray: '4 4',
        series: contributionSeries,
      },
    ];
  }, [filteredSnapshots, perfSeries]);

  const selectedMetrics = useMemo(() => {
    if (!filteredSnapshots.length) {
      return {
        beginningValue: 0,
        endingValue: 0,
        netContributions: 0,
        investmentChanges: 0,
        returnPct: 0,
      };
    }

    const beginningValue = Number(filteredSnapshots[0].totalValue || 0);
    const endingValue = Number(filteredSnapshots[filteredSnapshots.length - 1].totalValue || 0);
    const netContributions = filteredTransactions.reduce((sum, txn) => sum + toDisplayTransactionAmount(txn, perfDisplayCurrency), 0);
    const investmentChanges = endingValue - beginningValue - netContributions;
    const returnPct = beginningValue > 0 ? (investmentChanges / beginningValue) * 100 : 0;

    return {
      beginningValue,
      beginningMarketValue: Number(filteredSnapshots[0].investmentValue || 0),
      beginningCashValue: Number(filteredSnapshots[0].cashBalance || 0),
      endingValue,
      endingMarketValue: Number(filteredSnapshots[filteredSnapshots.length - 1].investmentValue || 0),
      endingCashValue: Number(filteredSnapshots[filteredSnapshots.length - 1].cashBalance || 0),
      netContributions,
      deposits: filteredTransactions
        .filter((txn) => String(txn?.transaction_type || '').toUpperCase() === 'DEPOSIT')
        .reduce((sum, txn) => sum + Math.abs(toDisplayTransactionAmount(txn, perfDisplayCurrency)), 0),
      withdrawals: filteredTransactions
        .filter((txn) => String(txn?.transaction_type || '').toUpperCase() === 'WITHDRAWAL')
        .reduce((sum, txn) => sum + Math.abs(toDisplayTransactionAmount(txn, perfDisplayCurrency)), 0),
      investmentChanges,
      returnPct,
    };
  }, [filteredSnapshots, filteredTransactions, perfDisplayCurrency]);

  const computeHistoryRangeMetrics = useCallback((preset) => {
    const range = computeRangeForPreset(preset);
    const fromDate = startOfDay(parseDate(range.from));
    const toDate = endOfDay(parseDate(range.to));

    const snaps = effectiveSnapshotRows.filter((snap) => snap.date >= fromDate && snap.date <= toDate);
    const txns = transactionRows.filter((txn) => {
      const date = parseDate(txn.timestamp);
      if (!date) return false;
      return date >= fromDate && date <= toDate;
    });

    const beginningValue = Number(snaps[0]?.totalValue || 0);
    const endingValue = Number(snaps[snaps.length - 1]?.totalValue || 0);
    const netContributions = txns.reduce((sum, txn) => sum + toDisplayTransactionAmount(txn, perfDisplayCurrency), 0);
    const investmentChanges = endingValue - beginningValue - netContributions;
    const deposits = txns
      .filter((txn) => String(txn?.transaction_type || '').toUpperCase() === 'DEPOSIT')
      .reduce((sum, txn) => sum + Math.abs(toDisplayTransactionAmount(txn, perfDisplayCurrency)), 0);
    const withdrawals = txns
      .filter((txn) => String(txn?.transaction_type || '').toUpperCase() === 'WITHDRAWAL')
      .reduce((sum, txn) => sum + Math.abs(toDisplayTransactionAmount(txn, perfDisplayCurrency)), 0);

    return {
      range,
      beginningValue,
      beginningMarketValue: Number(snaps[0]?.investmentValue || 0),
      beginningCashValue: Number(snaps[0]?.cashBalance || 0),
      netContributions,
      deposits,
      withdrawals,
      investmentChanges,
      endingValue,
      endingMarketValue: Number(snaps[snaps.length - 1]?.investmentValue || 0),
      endingCashValue: Number(snaps[snaps.length - 1]?.cashBalance || 0),
    };
  }, [computeRangeForPreset, effectiveSnapshotRows, transactionRows, perfDisplayCurrency]);

  const historyMetrics = useMemo(() => ({
    selected: {
      range: { from: perfFrom || minDateISO, to: perfTo || maxDateISO },
      beginningValue: selectedMetrics.beginningValue,
      beginningMarketValue: selectedMetrics.beginningMarketValue,
      beginningCashValue: selectedMetrics.beginningCashValue,
      netContributions: selectedMetrics.netContributions,
      deposits: selectedMetrics.deposits,
      withdrawals: selectedMetrics.withdrawals,
      investmentChanges: selectedMetrics.investmentChanges,
      endingValue: selectedMetrics.endingValue,
      endingMarketValue: selectedMetrics.endingMarketValue,
      endingCashValue: selectedMetrics.endingCashValue,
    },
    ytd: computeHistoryRangeMetrics('YTD'),
    oneYear: computeHistoryRangeMetrics('1Y'),
    max: computeHistoryRangeMetrics('MAX'),
  }), [perfFrom, perfTo, minDateISO, maxDateISO, selectedMetrics, computeHistoryRangeMetrics]);

  const historyTableMetrics = useMemo(() => {
    if (!performanceHistory) {
      return {
        selected: {
          range: historyMetrics.selected.range,
          beginning_value: historyMetrics.selected.beginningValue,
          beginning_market_value: historyMetrics.selected.beginningMarketValue,
          beginning_cash_value: historyMetrics.selected.beginningCashValue,
          deposits: historyMetrics.selected.deposits,
          withdrawals: historyMetrics.selected.withdrawals,
          net_contributions: historyMetrics.selected.netContributions,
          investment_changes: historyMetrics.selected.investmentChanges,
          ending_value: historyMetrics.selected.endingValue,
          ending_market_value: historyMetrics.selected.endingMarketValue,
          ending_cash_value: historyMetrics.selected.endingCashValue,
        },
        ytd: {
          range: historyMetrics.ytd.range,
          beginning_value: historyMetrics.ytd.beginningValue,
          beginning_market_value: historyMetrics.ytd.beginningMarketValue,
          beginning_cash_value: historyMetrics.ytd.beginningCashValue,
          deposits: historyMetrics.ytd.deposits,
          withdrawals: historyMetrics.ytd.withdrawals,
          net_contributions: historyMetrics.ytd.netContributions,
          investment_changes: historyMetrics.ytd.investmentChanges,
          ending_value: historyMetrics.ytd.endingValue,
          ending_market_value: historyMetrics.ytd.endingMarketValue,
          ending_cash_value: historyMetrics.ytd.endingCashValue,
        },
        oneYear: {
          range: historyMetrics.oneYear.range,
          beginning_value: historyMetrics.oneYear.beginningValue,
          beginning_market_value: historyMetrics.oneYear.beginningMarketValue,
          beginning_cash_value: historyMetrics.oneYear.beginningCashValue,
          deposits: historyMetrics.oneYear.deposits,
          withdrawals: historyMetrics.oneYear.withdrawals,
          net_contributions: historyMetrics.oneYear.netContributions,
          investment_changes: historyMetrics.oneYear.investmentChanges,
          ending_value: historyMetrics.oneYear.endingValue,
          ending_market_value: historyMetrics.oneYear.endingMarketValue,
          ending_cash_value: historyMetrics.oneYear.endingCashValue,
        },
        max: {
          range: historyMetrics.max.range,
          beginning_value: historyMetrics.max.beginningValue,
          beginning_market_value: historyMetrics.max.beginningMarketValue,
          beginning_cash_value: historyMetrics.max.beginningCashValue,
          deposits: historyMetrics.max.deposits,
          withdrawals: historyMetrics.max.withdrawals,
          net_contributions: historyMetrics.max.netContributions,
          investment_changes: historyMetrics.max.investmentChanges,
          ending_value: historyMetrics.max.endingValue,
          ending_market_value: historyMetrics.max.endingMarketValue,
          ending_cash_value: historyMetrics.max.endingCashValue,
        },
      };
    }
    return {
      selected: performanceHistory.selected,
      ytd: performanceHistory.ytd,
      oneYear: performanceHistory.one_year,
      max: performanceHistory.max,
    };
  }, [performanceHistory, historyMetrics]);

  const handleQuickRange = (preset) => {
    setPerfQuickRange(preset);
    const nextRange = computeRangeForPreset(preset);
    setPerfFrom(nextRange.from);
    setPerfTo(nextRange.to);
  };

  const handlePerfFromChange = (value) => {
    setPerfQuickRange('CUSTOM');
    setPerfFrom(value);
  };

  const handlePerfToChange = (value) => {
    setPerfQuickRange('CUSTOM');
    setPerfTo(value);
  };

  const perfToggleLabel = perfDisplayCurrency === 'PEN' ? 'Ver en $' : 'Ver en S/.';

  const handlePerfCurrencyToggle = () => {
    setPerfDisplayCurrency((current) => (current === 'PEN' ? 'USD' : 'PEN'));
  };

  const selectedBenchmarkTableRows = useMemo(() => {
    const byCode = benchmarkRows.reduce((acc, item) => {
      acc[item.code] = item;
      return acc;
    }, {});
    return [
      { id: 'r2k', label: 'Russell 2000®' },
      { id: 'sp500', label: 'S&P 500®' },
      { id: 'nasdaq', label: 'NASDAQ' },
      { id: 'djia', label: 'Dow Jones Industrial Average (DJIA)' },
    ]
      .filter((item) => perfIndexSel[item.id] && byCode[item.id])
      .map((item) => ({
        id: item.id,
        label: item.label,
        value: Number(byCode[item.id].cumulative_return_pct || 0),
        color: BENCHMARK_COLOR_MAP[item.id] || '#94A3B8',
      }));
  }, [benchmarkRows, perfIndexSel]);

  const portfolioReturnSeries = useMemo(() => (
    (benchmarkPortfolio?.series || []).map((point) => ({
      t: point.date,
      v: Number(point.return_pct || 0),
    }))
  ), [benchmarkPortfolio]);

  const benchmarkChartSeriesList = useMemo(() => {
    const colorMap = {
      portfolio: '#3B82F6',
      ...BENCHMARK_COLOR_MAP,
    };
    const labelMap = {
      djia: 'DJIA',
      nasdaq: 'NASDAQ',
      sp500: 'S&P 500®',
      r2k: 'Russell 2000®',
    };

    const seriesList = [
      {
        id: 'portfolio-return',
        label: portfolio?.name || 'Portafolio',
        color: colorMap.portfolio,
        series: portfolioReturnSeries,
      },
    ];

    benchmarkRows.forEach((row) => {
      if (!perfIndexSel[row.code]) return;
      seriesList.push({
        id: `benchmark-${row.code}`,
        label: labelMap[row.code] || row.name,
        color: colorMap[row.code] || '#94A3B8',
        series: (row.series || []).map((point) => ({
          t: point.date,
          v: Number(point.return_pct || 0),
        })),
      });
    });

    return seriesList;
  }, [benchmarkRows, perfIndexSel, portfolio?.name, portfolioReturnSeries]);

  const IndexChip = ({ id, label }) => (
    <button
      type="button"
      className={`btn xs ${perfIndexSel[id] ? '' : 'ghost'}`}
      onClick={() => setPerfIndexSel((state) => ({ ...state, [id]: !state[id] }))}
      style={perfIndexSel[id] ? {
        background: BENCHMARK_COLOR_MAP[id],
        borderColor: BENCHMARK_COLOR_MAP[id],
        color: '#fff',
      } : undefined}
    >
      {label}
    </button>
  );

  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>Performance</h3>
        {perfSubTab === 'performance' && (
          <button
            className="btn xs ghost"
            onClick={handlePerfCurrencyToggle}
            style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
          >
            {perfToggleLabel}
          </button>
        )}
      </div>

      <div className="row" style={{ gap: 8, marginBottom: 12 }}>
        <button className={`btn ${perfSubTab === 'performance' ? 'primary' : 'ghost'}`} onClick={() => setPerfSubTab('performance')}>Performance</button>
        <button className={`btn ${perfSubTab === 'asset' ? 'primary' : 'ghost'}`} onClick={() => setPerfSubTab('asset')}>Asset Allocation</button>
      </div>

      {perfSubTab === 'performance' && (
        <div className="card perf-controls" style={{ padding: 12, marginBottom: 16 }}>
          <div className="row" style={{ gap: 18, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
              {[
                { key: '3M', label: '3M' },
                { key: '1Y', label: '1Y' },
                { key: 'CURRENT_YEAR', label: currentYearLabel },
                { key: 'YTD', label: 'YTD' },
                { key: 'MAX', label: 'Max' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  className={`btn xs ${perfQuickRange === key ? 'primary' : 'ghost'}`}
                  onClick={() => handleQuickRange(key)}
                  style={{ fontSize: 11, padding: '0 6px', height: 22 }}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="perf-sep" aria-hidden="true" />
            <div className="row" style={{ gap: 8, alignItems: 'center', justifyContent: 'center' }}>
              <span className="muted" style={{ fontSize: 12 }}>From</span>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={perfFrom} onChange={handlePerfFromChange} min={minDateISO} max={perfTo || maxDateISO} placeholder="dd/mm/aaaa" />
              </div>
              <span className="muted" style={{ fontSize: 12 }}>To</span>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={perfTo} onChange={handlePerfToChange} min={perfFrom || minDateISO} max={maxDateISO} placeholder="dd/mm/aaaa" />
              </div>
            </div>
          </div>
        </div>
      )}

      {perfSubTab === 'performance' && (
        <div className="grid" style={{ gap: 16 }}>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0,1fr))', gap: 16, alignItems: 'start' }}>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Valor del portafolio vs. aportes netos</div>
              <div style={{ fontSize: 14, lineHeight: 1.5, marginBottom: 12 }}>
                Tu cuenta {selectedMetrics.investmentChanges >= 0 ? 'ganó' : 'perdió'}{' '}
                <span
                  className={selectedMetrics.investmentChanges >= 0 ? 'up' : 'down'}
                  style={{ fontWeight: 700 }}
                >
                  {formatDisplayCurrency(Math.abs(selectedMetrics.investmentChanges), perfDisplayCurrency)}
                </span>{' '}
                desde {parseDate(perfFrom)?.toLocaleDateString('es-PE') || 'N/A'} hasta {parseDate(perfTo)?.toLocaleDateString('es-PE') || 'N/A'}, excluyendo aportes netos.
              </div>
              <div className="card" style={{ padding: '12px 12px 30px 12px', marginTop: 12 }}>
                <TimeSeriesChart
                  seriesList={perfChartSeriesList}
                  rangePreset={perfQuickRange === 'CURRENT_YEAR' ? 'YTD' : perfQuickRange}
                  showPresetControls={false}
                  fillBetweenSeries={{
                    primaryId: 'portfolio-value',
                    compareId: 'net-contrib',
                    positiveColor: 'rgba(34,197,94,0.18)',
                    negativeColor: 'rgba(239,68,68,0.18)',
                  }}
                  yFormat="currency"
                  currency={perfDisplayCurrency}
                  showArea={false}
                  smooth
                  lineWidth={1.4}
                  loading={overviewLoading}
                  height={220}
                  ariaLabel="Evolución del retorno total y aportes netos"
                />
              </div>
              <div className="row" style={{ gap: 16, marginTop: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <span style={{ width: 18, height: 0, borderTop: '1.4px solid #3B82F6', display: 'inline-block' }} />
                  <span className="muted" style={{ fontSize: 12 }}>Valor total del portafolio</span>
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <span style={{ width: 18, height: 0, borderTop: '1.4px dashed rgba(157,176,208,0.95)', display: 'inline-block' }} />
                  <span className="muted" style={{ fontSize: 12 }}>Contribución total</span>
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Índices comunes</div>
              <div className="card" style={{ padding: '12px 12px 30px 12px', marginBottom: 12 }}>
                <TimeSeriesChart
                  seriesList={benchmarkChartSeriesList}
                  rangePreset={perfQuickRange === 'CURRENT_YEAR' ? 'YTD' : perfQuickRange}
                  showPresetControls={false}
                  yFormat="percent"
                  showArea={false}
                  smooth
                  lineWidth={1.6}
                  loading={overviewLoading || benchmarkLoading}
                  height={220}
                  ariaLabel="Comparación de rendimiento del portafolio e índices"
                />
              </div>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                <IndexChip id="djia" label="DJIA" />
                <IndexChip id="nasdaq" label="NASDAQ" />
                <IndexChip id="sp500" label="S&P 500®" />
                <IndexChip id="r2k" label="Russell 2000®" />
              </div>
              <table className="table returns-compact">
                <thead>
                  <tr style={{ textAlign: 'left' }}>
                        <th>Portafolio/Índice</th>
                        <th>Tasa de retorno</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <span className="row" style={{ gap: 8, alignItems: 'center' }}>
                        <span
                          aria-hidden="true"
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            background: '#3B82F6',
                            flex: '0 0 auto',
                          }}
                        />
                        <span>{portfolio?.name || 'Portafolio'}</span>
                      </span>
                    </td>
                    <td
                      className={
                        Number(benchmarkPortfolio?.cumulative_return_pct || 0) > 0
                          ? 'up'
                          : Number(benchmarkPortfolio?.cumulative_return_pct || 0) < 0
                            ? 'down'
                            : ''
                      }
                    >
                      {formatPercent(Number(benchmarkPortfolio?.cumulative_return_pct || 0))}
                    </td>
                  </tr>
                  {selectedBenchmarkTableRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <span className="row" style={{ gap: 8, alignItems: 'center' }}>
                          <span
                            aria-hidden="true"
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              background: row.color,
                              flex: '0 0 auto',
                            }}
                          />
                          <span>{row.label}</span>
                        </span>
                      </td>
                      <td className={row.value > 0 ? 'up' : row.value < 0 ? 'down' : ''}>{formatPercent(row.value)}</td>
                    </tr>
                  ))}
                  {!benchmarkLoading && selectedBenchmarkTableRows.length === 0 && (
                    <tr>
                      <td colSpan={2} className="muted">Selecciona uno o más índices.</td>
                    </tr>
                  )}
                  {benchmarkLoading && (
                    <tr>
                      <td colSpan={2} className="muted">Cargando índices...</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {perfSubTab === 'performance' && (
        <div className="card anim-fade" style={{ padding: 16, marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Performance history</div>
          <div className="muted" style={{ marginBottom: 12 }}>Compare performance across different time frames.</div>

          <div style={{ fontWeight: 600, marginBottom: 8 }}>Value vs. net contributions</div>
          <div className="perf-history-wrapper">
            <table className="table returns-compact perf-history">
              <thead>
                <tr style={{ textAlign: 'left' }}>
                  <th>Change Factor</th>
                  <th>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span>Selected Time Frame</span>
                      <span className="muted" style={{ fontSize: 10, lineHeight: 1.2 }}>
                        [{formatRangeLabel(parseDate(historyTableMetrics.selected.range.from), parseDate(historyTableMetrics.selected.range.to))}]
                      </span>
                    </div>
                  </th>
                  <th>Year to Date</th>
                  <th>One Year</th>
                  <th>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span>Since Available</span>
                      <span className="muted" style={{ fontSize: 10, lineHeight: 1.2 }}>
                        [{formatRangeLabel(parseDate(historyTableMetrics.max.range.from), parseDate(historyTableMetrics.max.range.to))}]
                      </span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const rows = {
                    beginning: {
                      label: 'Beginning Value',
                      values: [
                        formatDisplayCurrency(historyTableMetrics.selected.beginning_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.ytd.beginning_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.oneYear.beginning_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.max.beginning_value, perfDisplayCurrency),
                      ],
                      children: [
                        {
                          label: 'Market Value',
                          values: [
                            formatDisplayCurrency(historyTableMetrics.selected.beginning_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.ytd.beginning_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.oneYear.beginning_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.max.beginning_market_value, perfDisplayCurrency),
                          ],
                        },
                      ],
                    },
                    net: {
                      label: 'Net Contributions (This Period)',
                      values: [
                        formatSignedDisplayCurrency(historyTableMetrics.selected.net_contributions, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.ytd.net_contributions, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.oneYear.net_contributions, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.max.net_contributions, perfDisplayCurrency),
                      ],
                      children: [
                        {
                          label: 'Contributions',
                          values: [
                            formatSignedDisplayCurrency(historyTableMetrics.selected.deposits, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.ytd.deposits, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.oneYear.deposits, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.max.deposits, perfDisplayCurrency),
                          ],
                        },
                        {
                          label: 'Withdrawals',
                          values: [
                            formatSignedDisplayCurrency(historyTableMetrics.selected.withdrawals == null ? null : -historyTableMetrics.selected.withdrawals, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.ytd.withdrawals == null ? null : -historyTableMetrics.ytd.withdrawals, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.oneYear.withdrawals == null ? null : -historyTableMetrics.oneYear.withdrawals, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.max.withdrawals == null ? null : -historyTableMetrics.max.withdrawals, perfDisplayCurrency),
                          ],
                        },
                      ],
                    },
                    invest: {
                      label: 'Investment Changes',
                      values: [
                        formatSignedDisplayCurrency(historyTableMetrics.selected.investment_changes, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.ytd.investment_changes, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.oneYear.investment_changes, perfDisplayCurrency),
                        formatSignedDisplayCurrency(historyTableMetrics.max.investment_changes, perfDisplayCurrency),
                      ],
                      children: [
                        {
                          label: 'Investment gain/loss',
                          values: [
                            formatSignedDisplayCurrency(historyTableMetrics.selected.investment_changes, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.ytd.investment_changes, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.oneYear.investment_changes, perfDisplayCurrency),
                            formatSignedDisplayCurrency(historyTableMetrics.max.investment_changes, perfDisplayCurrency),
                          ],
                        },
                      ],
                    },
                    ending: {
                      label: 'Ending Value',
                      values: [
                        formatDisplayCurrency(historyTableMetrics.selected.ending_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.ytd.ending_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.oneYear.ending_value, perfDisplayCurrency),
                        formatDisplayCurrency(historyTableMetrics.max.ending_value, perfDisplayCurrency),
                      ],
                      children: [
                        {
                          label: 'Market Value',
                          values: [
                            formatDisplayCurrency(historyTableMetrics.selected.ending_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.ytd.ending_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.oneYear.ending_market_value, perfDisplayCurrency),
                            formatDisplayCurrency(historyTableMetrics.max.ending_market_value, perfDisplayCurrency),
                          ],
                        },
                      ],
                    },
                  };

                  const toggle = (key) => setPerfHistoryOpen((state) => ({ ...state, [key]: !state[key] }));
                  return Object.entries(rows).map(([key, row]) => (
                    <React.Fragment key={key}>
                      <tr className="perf-parent">
                        <td>
                          <button className="caret-btn" onClick={() => toggle(key)} aria-expanded={!!perfHistoryOpen[key]}>
                            <span className={`caret ${perfHistoryOpen[key] ? 'open' : ''}`}>▶</span>
                            {row.label}
                          </button>
                        </td>
                        {row.values.map((value, index) => <td key={index}>{value}</td>)}
                      </tr>
                      {perfHistoryOpen[key] && (row.children || []).map((child) => (
                        <tr className="perf-child" key={`${key}-${child.label}`}>
                          <td>{child.label}</td>
                          {child.values.map((value, index) => <td key={index}>{value}</td>)}
                        </tr>
                      ))}
                    </React.Fragment>
                  ));
                })()}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {perfSubTab === 'asset' && (() => {
        const alloc = [
          { key: 'us_large', label: 'US Large Caps', pct: 90.1, color: '#3b82f6' },
          { key: 'small_cap', label: 'Small Cap', pct: 0.03, color: '#f59e0b' },
          { key: 'cash', label: 'Cash & Investments', pct: 5.77, color: '#22c55e' },
          { key: 'uncat', label: 'Uncategorized', pct: 4.19, color: '#a78bfa' },
        ];

        const totalTiles = 100;
        const base = alloc.map((item) => ({ ...item, tiles: Math.floor(item.pct) }));
        alloc.forEach((item, index) => { if (item.pct > 0 && base[index].tiles === 0) base[index].tiles = 1; });
        let used = base.reduce((sum, item) => sum + item.tiles, 0);
        if (used > totalTiles) {
          const order = [...base].sort((a, b) => b.tiles - a.tiles);
          let over = used - totalTiles;
          for (const category of order) {
            if (over <= 0) break;
            const index = base.findIndex((item) => item.key === category.key);
            const canGive = Math.min(over, Math.max(0, base[index].tiles - 1));
            if (canGive > 0) { base[index].tiles -= canGive; over -= canGive; }
          }
          used = base.reduce((sum, item) => sum + item.tiles, 0);
        }
        if (used < totalTiles) {
          const remainder = alloc
            .map((item, index) => ({ index, frac: item.pct - Math.floor(item.pct) }))
            .sort((a, b) => b.frac - a.frac);
          let index = 0;
          while (used < totalTiles && index < remainder.length) {
            base[remainder[index].index].tiles += 1;
            used += 1;
            index += 1;
          }
        }

        const tiles = [];
        base.forEach((item) => { for (let i = 0; i < item.tiles; i += 1) tiles.push(item.key); });
        while (tiles.length < totalTiles) tiles.push(base[0]?.key || 'us_large');

        return (
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Allocation</div>
            <div className="muted" style={{ marginBottom: 12 }}>Asignación</div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 1fr) minmax(200px, 1fr)', gap: 16, alignItems: 'start' }}>
              <div style={{ position: 'relative', width: '100%' }}>
                <div style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 0, width: '100%', borderRadius: 0 }}>
                  {tiles.map((key, index) => {
                    const item = base.find((entry) => entry.key === key) || base[0];
                    return <div key={index} title={alloc.find((entry) => entry.key === key)?.label} style={{ width: '100%', height: 24, background: item.color }} />;
                  })}
                </div>
              </div>

              <div style={{ display: 'grid', gap: 8, alignContent: 'start' }}>
                {alloc.map((item) => (
                  <div key={item.key} style={{ display: 'grid', gridTemplateColumns: '14px 1fr max-content', gap: 8, alignItems: 'center' }}>
                    <span style={{ width: 14, height: 14, borderRadius: 3, display: 'inline-block', background: item.color, border: '1px solid rgba(255,255,255,.15)' }} />
                    <span style={{ fontSize: 12 }}>{item.label}</span>
                    <span className="muted" style={{ fontSize: 12 }}>{formatPercent(item.pct)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}
    </>
  );
};

export default PerformanceTab;
