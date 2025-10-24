import { useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';

const PRESETS = ['1M', '3M', '6M', 'YTD', '1Y', 'MAX'];
const DEFAULT_COLORS = ['#3B82F6', '#0EA5E9', '#22C55E', '#F97316', '#A855F7'];
const MAX_POINTS = 1200;

const DAY_MS = 24 * 60 * 60 * 1000;

function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return new Date(value.getTime());
  if (typeof value === 'number' && Number.isFinite(value)) {
    const direct = new Date(value);
    return Number.isNaN(direct.getTime()) ? null : direct;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    if (/^\d+$/.test(trimmed)) {
      const asNumber = Number(trimmed);
      if (Number.isFinite(asNumber)) {
        const numericDate = new Date(asNumber);
        if (!Number.isNaN(numericDate.getTime())) return numericDate;
      }
    }
    const dateOnlyMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnlyMatch) {
      const year = Number(dateOnlyMatch[1]);
      const month = Number(dateOnlyMatch[2]) - 1;
      const day = Number(dateOnlyMatch[3]);
      if (Number.isInteger(year) && Number.isInteger(month) && Number.isInteger(day)) {
        // Interpret bare dates as local midnight to avoid timezone shift on the chart
        const localDate = new Date(year, month, day, 0, 0, 0, 0);
        if (!Number.isNaN(localDate.getTime())) return localDate;
      }
    }
    const parsed = Date.parse(trimmed);
    if (!Number.isNaN(parsed)) return new Date(parsed);
    return null;
  }
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function subtractMonths(date, months) {
  if (!Number.isFinite(months) || months <= 0) {
    return new Date(date.getTime());
  }
  const base = new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);
  base.setMonth(base.getMonth() - months);
  const lastDay = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
  const day = Math.min(date.getDate(), lastDay);
  return new Date(
    base.getFullYear(),
    base.getMonth(),
    day,
    0,
    0,
    0,
    0,
  );
}

function withAlpha(hex, alpha) {
  if (!hex || hex.startsWith('rgba') || hex.startsWith('rgb')) {
    return hex;
  }
  const value = hex.replace('#', '');
  const bigint = parseInt(value.length === 3
    ? value.split('').map(v => v + v).join('')
    : value, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function niceNumber(value, round) {
  const exponent = Math.floor(Math.log10(value));
  const fraction = value / Math.pow(10, exponent);
  let niceFraction;
  if (round) {
    if (fraction < 1.5) niceFraction = 1;
    else if (fraction < 3) niceFraction = 2;
    else if (fraction < 7) niceFraction = 5;
    else niceFraction = 10;
  } else {
    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
  }
  return niceFraction * Math.pow(10, exponent);
}

function niceDomain(min, max, maxTicks = 5) {
  const range = niceNumber(max - min, false);
  const step = niceNumber(range / (maxTicks - 1), true);
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  return { min: niceMin, max: niceMax, step };
}

function decimate(points, limit = MAX_POINTS) {
  if (points.length <= limit) return points;
  const step = points.length / limit;
  const result = [];
  for (let i = 0; i < points.length; i += step) {
    const idx = Math.floor(i);
    result.push(points[idx]);
  }
  const last = points[points.length - 1];
  const lastResult = result[result.length - 1];
  if (!lastResult || lastResult.ts !== last.ts) {
    result.push(last);
  }
  return result;
}

function linearTicks(start, end, count) {
  if (count <= 1 || !Number.isFinite(start) || !Number.isFinite(end)) {
    return [start];
  }
  const span = end - start;
  const ticks = [];
  const safeCount = Math.max(2, count);
  for (let i = 0; i < safeCount; i += 1) {
    ticks.push(start + (span * i) / (safeCount - 1));
  }
  return ticks;
}

function formatAxisValue(value, format, currency) {
  if (!Number.isFinite(value)) return '';
  if (format === 'percent') {
    return new Intl.NumberFormat(undefined, {
      style: 'percent',
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    }).format(value / 100);
  }
  if (format === 'number') {
    return new Intl.NumberFormat(undefined, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }
  const formatter = new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency || 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  });
  return formatter.format(value);
}

function formatTooltipValue(value, format, currency) {
  if (!Number.isFinite(value)) return '';
  if (format === 'percent') {
    return new Intl.NumberFormat(undefined, {
      style: 'percent',
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    }).format(value / 100);
  }
  if (format === 'number') {
    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    }).format(value);
  }
  const formatter = new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });
  return formatter.format(value);
}

function formatTickDate(date, spanMs) {
  if (!date) return '';
  const spanDays = spanMs / DAY_MS;
  if (spanDays <= 2) {
    return new Intl.DateTimeFormat(undefined, {
      hour: 'numeric',
      minute: spanDays < 1 ? '2-digit' : undefined,
      day: spanDays < 1 ? undefined : 'numeric',
      month: spanDays < 1 ? undefined : 'short',
    }).format(date);
  }
  if (spanDays <= 45) {
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric',
      month: 'short',
    }).format(date);
  }
  if (spanDays <= 370) {
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      year: 'numeric',
    }).format(date);
  }
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
  }).format(date);
}

function formatTooltipDate(date, spanMs) {
  if (!date) return '';
  const spanDays = spanMs / DAY_MS;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: spanDays <= 2 ? 'short' : undefined,
  }).format(date);
}

function straightLine(points) {
  if (points.length === 0) return '';
  const [firstX, firstY] = points[0];
  let d = `M${firstX},${firstY}`;
  for (let i = 1; i < points.length; i += 1) {
    d += ` L${points[i][0]},${points[i][1]}`;
  }
  return d;
}

function monotoneCurve(points) {
  const n = points.length;
  if (n === 0) return '';
  if (n === 1) {
    const [x, y] = points[0];
    return `M${x},${y}`;
  }

  const dx = new Array(n - 1);
  const dy = new Array(n - 1);
  const slopes = new Array(n - 1);
  const tangents = new Array(n);

  for (let i = 0; i < n - 1; i += 1) {
    const x0 = points[i][0];
    const x1 = points[i + 1][0];
    const y0 = points[i][1];
    const y1 = points[i + 1][1];
    const diffX = x1 - x0 || 1e-12;
    dx[i] = diffX;
    dy[i] = y1 - y0;
    slopes[i] = dy[i] / diffX;
  }

  tangents[0] = slopes[0];
  tangents[n - 1] = slopes[n - 2];
  for (let i = 1; i < n - 1; i += 1) {
    tangents[i] = (slopes[i - 1] + slopes[i]) / 2;
  }

  for (let i = 0; i < n - 1; i += 1) {
    if (slopes[i] === 0) {
      tangents[i] = 0;
      tangents[i + 1] = 0;
    } else {
      const a = tangents[i] / slopes[i];
      const b = tangents[i + 1] / slopes[i];
      const h = Math.hypot(a, b);
      if (h > 3) {
        const t = 3 / h;
        tangents[i] = t * a * slopes[i];
        tangents[i + 1] = t * b * slopes[i];
      }
    }
  }

  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < n - 1; i += 1) {
    const x0 = points[i][0];
    const y0 = points[i][1];
    const x1 = points[i + 1][0];
    const y1 = points[i + 1][1];
    const h = dx[i];
    const control1X = x0 + h / 3;
    const control1Y = y0 + (tangents[i] * h) / 3;
    const control2X = x1 - h / 3;
    const control2Y = y1 - (tangents[i + 1] * h) / 3;
    d += ` C${control1X},${control1Y} ${control2X},${control2Y} ${x1},${y1}`;
  }
  return d;
}

function buildLine(points, smooth) {
  return smooth ? monotoneCurve(points) : straightLine(points);
}

function computeRange(preset, seriesList) {
  const all = [];
  seriesList.forEach(s => {
    s.series.forEach(pt => {
      all.push(pt.ts);
    });
  });
  if (!all.length) {
    return { start: null, end: null, min: null, max: null };
  }
  const min = Math.min(...all);
  const max = Math.max(...all);
  const minDate = new Date(min);
  const maxDate = new Date(max);
  const end = new Date(maxDate.getFullYear(), maxDate.getMonth(), maxDate.getDate(), 0, 0, 0, 0);
  const presetToMonths = {
    '1M': 1,
    '3M': 3,
    '6M': 6,
    '1Y': 12,
  };

  let start;
  if (preset === 'YTD') {
    start = new Date(end.getFullYear(), 0, 1, 0, 0, 0, 0);
  } else if (preset === 'MAX') {
    start = new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate(), 0, 0, 0, 0);
  } else if (presetToMonths[preset]) {
    start = subtractMonths(end, presetToMonths[preset]);
  } else {
    start = subtractMonths(end, 6);
  }
  if (start.getTime() > end.getTime()) {
    start = new Date(end.getTime());
  }
  return { start, end, min: minDate, max: maxDate };
}

function findNearestPoint(points, targetTs) {
  if (!points.length) return null;
  if (targetTs <= points[0].ts) return points[0];
  const last = points[points.length - 1];
  if (targetTs >= last.ts) return last;
  let left = 0;
  let right = points.length - 1;
  while (right - left > 1) {
    const mid = Math.floor((left + right) / 2);
    if (points[mid].ts === targetTs) return points[mid];
    if (points[mid].ts < targetTs) left = mid;
    else right = mid;
  }
  const leftPoint = points[left];
  const rightPoint = points[right];
  return (targetTs - leftPoint.ts) <= (rightPoint.ts - targetTs) ? leftPoint : rightPoint;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

const TimeSeriesChart = ({
  series = [],
  seriesList,
  rangePreset = '6M',
  onRangeChange,
  yFormat = 'currency',
  currency = 'PEN',
  showArea = true,
  smooth = false,
  colors = {},
  height = 260,
  ariaLabel = 'Histórico de balance',
  loading = false,
  className = '',
}) => {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState(null);
  const [pointerActive, setPointerActive] = useState(false);

  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(entries => {
      if (!entries.length) return;
      const { width: w } = entries[0].contentRect;
      setWidth(w);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const palette = useMemo(() => {
    const baseLine = colors.line ? [colors.line, ...DEFAULT_COLORS] : DEFAULT_COLORS;
    return baseLine;
  }, [colors.line]);

  const preparedSeries = useMemo(() => {
    const input = seriesList && seriesList.length
      ? seriesList
      : [{ id: 'primary', label: '', color: colors.line, areaColor: colors.area, series }];
    return input.map((item, idx) => {
      const pts = Array.isArray(item.series) ? item.series : [];
      const normalized = pts.map(p => {
        const rawT = p.t ?? p.time ?? p.date ?? p.timestamp;
        const rawV = p.v ?? p.value ?? p.total ?? p.total_value;
        const date = toDate(rawT);
        const value = Number(rawV);
        if (!date || !Number.isFinite(value)) return null;
        return { ts: date.getTime(), date, value };
      }).filter(Boolean).sort((a, b) => a.ts - b.ts);
      const lineColor = item.color || palette[idx % palette.length];
      const areaColor = item.areaColor || withAlpha(lineColor, 0.12);
      return {
        id: item.id || `series-${idx}`,
        label: item.label,
        color: lineColor,
        areaColor,
        series: normalized,
      };
    });
  }, [series, seriesList, palette, colors.area, colors.line]);

  const range = useMemo(
    () => computeRange(rangePreset, preparedSeries),
    [rangePreset, preparedSeries],
  );

  const filteredSeries = useMemo(() => {
    if (!range.start || !range.end) return preparedSeries.map(s => ({ ...s, filtered: [] }));
    const startTs = range.start.getTime();
    const endTs = range.end.getTime();
    return preparedSeries.map(s => {
      const subset = s.series.filter(pt => pt.ts >= startTs && pt.ts <= endTs);
      return { ...s, filtered: decimate(subset) };
    });
  }, [preparedSeries, range.start, range.end]);

  const yDomain = useMemo(() => {
    const values = filteredSeries.flatMap(s => s.filtered.map(pt => pt.value));
    if (!values.length) return null;
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      const padding = Math.abs(min) * 0.05 || 1;
      min -= padding;
      max += padding;
    }
    const nice = niceDomain(min, max);
    return { min: nice.min, max: nice.max, step: nice.step };
  }, [filteredSeries]);

  const inner = useMemo(() => {
    const margin = { top: 24, right: 16, bottom: 32, left: 64 };
    const w = Math.max(width - margin.left - margin.right, 0);
    const h = Math.max(height - margin.top - margin.bottom, 0);
    return { margin, width: w, height: h };
  }, [width, height]);

  const startTs = range.start ? range.start.getTime() : null;
  const endTs = range.end ? range.end.getTime() : null;

  const xScale = useMemo(() => {
    if (!startTs || !endTs || endTs === startTs || inner.width === 0) {
      return () => inner.margin.left;
    }
    return (ts) => inner.margin.left + ((ts - startTs) / (endTs - startTs)) * inner.width;
  }, [startTs, endTs, inner.width, inner.margin.left]);

  const yScale = useMemo(() => {
    if (!yDomain || inner.height === 0) {
      return () => inner.margin.top + inner.height;
    }
    const span = yDomain.max - yDomain.min || 1;
    return (value) => inner.margin.top + inner.height - ((value - yDomain.min) / span) * inner.height;
  }, [yDomain, inner.height, inner.margin.top]);

  const timeTicks = useMemo(() => {
    if (!startTs || !endTs) return [];
    const desired = Math.max(2, Math.min(8, Math.floor(inner.width / 120)));
    return linearTicks(startTs, endTs, desired).map(ts => new Date(ts));
  }, [startTs, endTs, inner.width]);

  const valueTicks = useMemo(() => {
    if (!yDomain) return [];
    const ticks = [];
    for (let v = yDomain.min; v <= yDomain.max + yDomain.step / 2; v += yDomain.step) {
      ticks.push(v);
    }
    return ticks;
  }, [yDomain]);

  const spanMs = useMemo(() => {
    if (!startTs || !endTs) return 0;
    return endTs - startTs;
  }, [startTs, endTs]);
  const hasData = filteredSeries.some(s => s.filtered.length > 0);
  const singlePoint = filteredSeries.some(s => s.filtered.length === 1);

  const gradientId = useMemo(
    () => `chart-gradient-${Math.random().toString(36).slice(2)}`,
    [],
  );

  const handlePresetClick = (preset) => {
    if (!onRangeChange) return;
    onRangeChange({ preset });
  };

  const updateHover = (event) => {
    if (!startTs || !endTs || !hasData) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const clampedX = clamp(x, inner.margin.left, inner.margin.left + inner.width);
    const ratio = inner.width === 0 ? 0 : (clampedX - inner.margin.left) / inner.width;
    const targetTs = startTs + ratio * (endTs - startTs);
    const referenceSeries = filteredSeries.find(s => s.filtered.length > 0);
    if (!referenceSeries) return;
    const anchor = findNearestPoint(referenceSeries.filtered, targetTs);
    if (!anchor) {
      setHover(null);
      return;
    }
    const points = filteredSeries.map(s => {
      if (!s.filtered.length) return null;
      const candidate = findNearestPoint(s.filtered, anchor.ts);
      if (!candidate) return null;
      return {
        id: s.id,
        label: s.label,
        color: s.color,
        value: candidate.value,
        x: xScale(candidate.ts),
        y: yScale(candidate.value),
      };
    }).filter(Boolean);
    setHover({
      ts: anchor.ts,
      date: anchor.date,
      x: xScale(anchor.ts),
      points,
    });
  };

  const releasePointer = (event) => {
    if (svgRef.current && event?.pointerId !== undefined) {
      try { svgRef.current.releasePointerCapture(event.pointerId); } catch (_) { /* ignore */ }
    }
    setPointerActive(false);
    setHover(null);
  };

  const pointerHandlers = {
    onPointerMove: (event) => {
      if (!pointerActive && event.pointerType !== 'mouse') return;
      updateHover(event);
    },
    onPointerDown: (event) => {
      if (!startTs || !endTs || !hasData) return;
      if (svgRef.current && event.pointerId !== undefined) {
        try { svgRef.current.setPointerCapture(event.pointerId); } catch (_) { /* ignore */ }
      }
      setPointerActive(true);
      updateHover(event);
    },
    onPointerUp: (event) => {
      releasePointer(event);
    },
    onPointerCancel: (event) => {
      releasePointer(event);
    },
    onPointerLeave: (event) => {
      if (!pointerActive) {
        setHover(null);
      } else {
        updateHover(event);
      }
    },
  };

  return (
    <div
      ref={containerRef}
      className={`timeseries-chart ${className}`}
      style={{ position: 'relative', width: '100%', height }}
      role="img"
      aria-label={ariaLabel}
    >
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div className="row" role="radiogroup" aria-label="Seleccionar rango">
          {PRESETS.map(preset => (
            <button
              key={preset}
              type="button"
              className={`btn xs ${rangePreset === preset ? 'primary' : 'ghost'}`}
              aria-pressed={rangePreset === preset}
              onClick={() => handlePresetClick(preset)}
              style={{ minWidth: 48 }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      <svg
        ref={svgRef}
        width={width}
        height={height}
        style={{ display: 'block', width: '100%', height: '100%' }}
        {...pointerHandlers}
      >
        <defs>
          {filteredSeries.map(seriesItem => (
            <linearGradient key={seriesItem.id} id={`${gradientId}-${seriesItem.id}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={seriesItem.areaColor} stopOpacity="0.8" />
              <stop offset="100%" stopColor={seriesItem.areaColor} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* Axes */}
        <g>
          {timeTicks.map((tick, idx) => {
            const x = xScale(tick.getTime());
            return (
              <g key={`xtick-${idx}`}>
                <line
                  x1={x}
                  x2={x}
                  y1={inner.margin.top}
                  y2={inner.margin.top + inner.height}
                  stroke="var(--border-muted, rgba(148,163,184,.25))"
                  strokeDasharray="2 4"
                />
                <text
                  x={x}
                  y={inner.margin.top + inner.height + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fill="var(--muted, #64748b)"
                >
                  {formatTickDate(tick, spanMs)}
                </text>
              </g>
            );
          })}
          {valueTicks.map((tick, idx) => {
            const y = yScale(tick);
            return (
              <g key={`ytick-${idx}`}>
                <line
                  x1={inner.margin.left}
                  x2={inner.margin.left + inner.width}
                  y1={y}
                  y2={y}
                  stroke="var(--border-muted, rgba(148,163,184,.18))"
                />
                <text
                  x={inner.margin.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="var(--muted, #64748b)"
                >
                  {formatAxisValue(tick, yFormat, currency)}
                </text>
              </g>
            );
          })}
        </g>

        {/* Series */}
        {hasData && filteredSeries.map(seriesItem => {
          const pts = seriesItem.filtered.map(pt => [xScale(pt.ts), yScale(pt.value)]);
          if (!pts.length) return null;
          const baseline = yScale(yDomain.min);
          const linePath = buildLine(pts, smooth);
          const areaPath = (showArea && pts.length > 1)
            ? `${linePath} L${pts[pts.length - 1][0]},${baseline} L${pts[0][0]},${baseline} Z`
            : null;
          const showMarkers = pts.length > 1 && pts.length <= 500;
          return (
            <g key={seriesItem.id}>
              {areaPath && (
                <path
                  d={areaPath}
                  fill={`url(#${gradientId}-${seriesItem.id})`}
                  pointerEvents="none"
                />
              )}
              <path
                d={linePath}
                fill="none"
                stroke={seriesItem.color}
                strokeWidth={2}
                vectorEffect="non-scaling-stroke"
              />
              {showMarkers && seriesItem.filtered.map(point => (
                <circle
                  key={`${seriesItem.id}-${point.ts}`}
                  cx={xScale(point.ts)}
                  cy={yScale(point.value)}
                  r={2.5}
                  fill={seriesItem.color}
                  stroke="#0f172a"
                  strokeWidth="0.75"
                />
              ))}
            </g>
          );
        })}

        {/* Single point fallback */}
        {singlePoint && filteredSeries.map(seriesItem => {
          if (seriesItem.filtered.length !== 1) return null;
          const pt = seriesItem.filtered[0];
          const cx = xScale(pt.ts);
          const cy = yScale(pt.value);
          const baseline = yScale(yDomain ? yDomain.min : pt.value);
          return (
            <g key={`single-${seriesItem.id}`}>
              <line
                x1={inner.margin.left}
                x2={inner.margin.left + inner.width}
                y1={baseline}
                y2={baseline}
                stroke="var(--border-muted, rgba(148,163,184,.35))"
                strokeDasharray="4 6"
              />
              <circle cx={cx} cy={cy} r={4} fill={seriesItem.color} />
            </g>
          );
        })}

        {/* Empty state */}
        {!loading && !hasData && (
          <text
            x={inner.margin.left + inner.width / 2}
            y={inner.margin.top + inner.height / 2}
            textAnchor="middle"
            fontSize="13"
            fill="var(--muted, #94a3b8)"
          >
            No hay datos para el rango seleccionado.
          </text>
        )}

        {/* Loading */}
        {loading && (
          <text
            x={inner.margin.left + inner.width / 2}
            y={inner.margin.top + inner.height / 2}
            textAnchor="middle"
            fontSize="13"
            fill="var(--muted, #94a3b8)"
          >
            Cargando...
          </text>
        )}

        {/* Crosshair */}
        {hover && (
          <g pointerEvents="none">
            <line
              x1={hover.x}
              x2={hover.x}
              y1={inner.margin.top}
              y2={inner.margin.top + inner.height}
              stroke="var(--border-strong, rgba(59,130,246,.35))"
              strokeDasharray="2 2"
            />
            {hover.points.map(pt => (
              <circle key={`dot-${pt.id}`} cx={pt.x} cy={pt.y} r={4} fill={pt.color} stroke="#0f172a" strokeWidth="1" />
            ))}
          </g>
        )}
      </svg>

      {hover && (
        <div
          className="tooltip"
          style={{
            position: 'absolute',
            top: inner.margin.top + 12,
            left: clamp(hover.x + 16, 12, Math.max(12, width - 200)),
            padding: '8px 12px',
            background: 'var(--popover, rgba(15,23,42,0.9))',
            color: 'white',
            borderRadius: 8,
            fontSize: 12,
            pointerEvents: 'none',
            maxWidth: 220,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {formatTooltipDate(hover.date, spanMs)}
          </div>
          {hover.points.map(pt => (
            <div key={`tooltip-${pt.id}`} className="row" style={{ alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: pt.color }} />
              <span style={{ flex: 1, opacity: 0.9 }}>
                {pt.label || 'Balance'}
              </span>
              <span style={{ fontWeight: 600 }}>
                {formatTooltipValue(pt.value, yFormat, currency)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

TimeSeriesChart.propTypes = {
  series: PropTypes.arrayOf(PropTypes.shape({
    t: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.instanceOf(Date)]),
    v: PropTypes.number,
  })),
  seriesList: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string,
    label: PropTypes.string,
    series: PropTypes.arrayOf(PropTypes.object),
    color: PropTypes.string,
    areaColor: PropTypes.string,
  })),
  rangePreset: PropTypes.string,
  onRangeChange: PropTypes.func,
  yFormat: PropTypes.oneOf(['currency', 'percent', 'number']),
  currency: PropTypes.string,
  showArea: PropTypes.bool,
  smooth: PropTypes.bool,
  colors: PropTypes.shape({
    line: PropTypes.string,
    area: PropTypes.string,
  }),
  height: PropTypes.number,
  ariaLabel: PropTypes.string,
  loading: PropTypes.bool,
  className: PropTypes.string,
};

export default TimeSeriesChart;
