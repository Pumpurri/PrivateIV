import { useState } from 'react';
import { formatPercent } from '../../utils/format';
import {
  buildNiceTicks,
  DISPLAY_CURRENCY_NATIVE,
  formatMoney,
  valueColor,
} from './realizedUtils';

const WIDTH = 1200;
const HEIGHT = 480;
const LEFT_PADDING = 52;
const RIGHT_PADDING = 8;
const TOP_PADDING = 16;
const BOTTOM_PADDING = 40;

const RealizedScatterChart = ({ scatterSeries, activeDisplayMode, formatDateLabel }) => {
  const [tooltip, setTooltip] = useState(null);

  if (!scatterSeries.length) {
    return (
      <div className="card" style={{ padding: 12, marginBottom: 12, fontSize: 12, color: 'var(--danger)' }}>
        Aún no hay movimientos realizados en el período seleccionado para graficar.
      </div>
    );
  }

  const plotWidth = WIDTH - LEFT_PADDING - RIGHT_PADDING;
  const plotHeight = HEIGHT - TOP_PADDING - BOTTOM_PADDING;
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
  const yFor = (value) => TOP_PADDING + ((domainMax - value) / domainSpan) * plotHeight;
  const xFor = (date) => {
    if (scatterSeries.length === 1) return LEFT_PADDING + plotWidth / 2;
    return LEFT_PADDING + ((date.getTime() - minTime) / timeSpan) * plotWidth;
  };
  const xTicks = Array.from({ length: 4 }, (_, idx) => {
    const ratio = idx / 3;
    return new Date(minTime + (timeSpan * ratio));
  });
  const zeroY = yFor(0);
  const showZeroLine = domainMin <= 0 && domainMax >= 0;
  const radiusFor = (magnitude) => {
    if (maxMagnitude <= 0) return 12;
    return 2 + (Math.sqrt(Math.max(0, magnitude) / maxMagnitude) * 40);
  };
  const scatterBubbles = scatterSeries
    .map((point) => ({
      ...point,
      radius: radiusFor(Math.abs(
        activeDisplayMode === DISPLAY_CURRENCY_NATIVE ? point.total : point.chartTotal,
      )),
    }))
    .sort((a, b) => b.radius - a.radius);

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
    if (position) setTooltip({ ...position, point });
  };
  const handlePointMove = (event) => {
    const position = getTooltipPosition(event);
    if (position) setTooltip((current) => (current ? { ...current, ...position } : current));
  };
  const formatShortDate = (date) => date?.toLocaleDateString('es-PE', { day: 'numeric', month: 'short' }) || '—';
  const formatAxisPct = (value) => `${value > 0 ? '+' : ''}${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}%`;
  const formatSignedMoney = (value, currency) => `${value >= 0 ? '+' : '-'}${formatMoney(Math.abs(value), currency)}`;

  return (
    <div style={{ width: '90%', margin: '0 auto 12px', padding: 4, position: 'relative' }}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
        <div className="muted" style={{ fontSize: 12 }}>Rendimiento realizado por operación (%)</div>
        <div className="muted" style={{ fontSize: 12 }}>Gráfico basado en {scatterSeries.length} registros</div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" style={{ width: '100%', height: 460, display: 'block' }}>
        {niceY.ticks.map((value, idx) => {
          const y = yFor(value);
          return (
            <g key={`grid-${idx}`}>
              <line
                x1={LEFT_PADDING}
                y1={y}
                x2={WIDTH - RIGHT_PADDING}
                y2={y}
                stroke="rgba(157,176,208,0.16)"
                strokeWidth="0.5"
              />
              <text x={LEFT_PADDING - 1.5} y={y + 4} textAnchor="end" fill="var(--muted)" fontSize="11">
                {formatAxisPct(value)}
              </text>
            </g>
          );
        })}
        {showZeroLine && (
          <line
            x1={LEFT_PADDING}
            y1={zeroY}
            x2={WIDTH - RIGHT_PADDING}
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
                y1={TOP_PADDING}
                x2={x}
                y2={HEIGHT - BOTTOM_PADDING}
                stroke="rgba(157,176,208,0.08)"
                strokeWidth="0.45"
              />
              <text x={x} y={HEIGHT - 12} textAnchor="middle" fill="var(--muted)" fontSize="11">
                {formatShortDate(tick)}
              </text>
            </g>
          );
        })}
        {scatterBubbles.map((point) => {
          const stroke = point.total > 0 ? 'var(--accent)' : point.total < 0 ? 'var(--danger)' : 'var(--text)';
          const fill = point.total > 0
            ? 'rgba(34,197,94,0.20)'
            : point.total < 0
              ? 'rgba(239,68,68,0.20)'
              : 'rgba(231,238,252,0.18)';
          return (
            <circle
              key={point.id}
              cx={xFor(point.date)}
              cy={yFor(point.pct)}
              r={point.radius}
              fill={fill}
              stroke={stroke}
              strokeWidth="2"
              style={{ cursor: 'pointer' }}
              onMouseEnter={(event) => handlePointEnter(event, point)}
              onMouseMove={handlePointMove}
              onMouseLeave={() => setTooltip(null)}
            />
          );
        })}
      </svg>
      {tooltip && (
        <div
          className="card"
          style={{
            position: 'absolute',
            left: Math.min(tooltip.x, 760),
            top: Math.max(tooltip.y, 44),
            padding: '10px 12px',
            minWidth: 220,
            pointerEvents: 'none',
            zIndex: 3,
            boxShadow: '0 10px 24px rgba(0,0,0,.35)',
            background: 'linear-gradient(180deg, rgba(18,26,47,.98), rgba(12,20,39,.98))',
          }}
        >
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            <span className="muted">Fecha de cierre:</span>{' '}
            <span>{formatDateLabel(tooltip.point.rawDate)}</span>
          </div>
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            <span className="muted">Transacción:</span>{' '}
            <span>{tooltip.point.symbol} Vendido {tooltip.point.qty}</span>
          </div>
          <div style={{ fontSize: 12 }}>
            <span className="muted">Ganancia/Pérdida:</span>{' '}
            <span style={{ color: valueColor(tooltip.point.total) }}>
              {formatSignedMoney(tooltip.point.total, tooltip.point.currency)} ({tooltip.point.gainPct >= 0 ? '+' : ''}{formatPercent(tooltip.point.gainPct)})
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealizedScatterChart;
