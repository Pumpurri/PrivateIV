const ResultGauge = ({ label, gainRateValue, gains, losses }) => {
  const hasData = gains !== 0 || losses !== 0;
  const safeRate = hasData
    ? Math.max(0, Math.min(1, Number.isFinite(gainRateValue) ? gainRateValue : 0))
    : 0.5;
  const gainPct = Math.round(safeRate * 100);
  const radius = 15.915;
  const halfCircle = Math.PI * radius;
  const gainLength = safeRate * halfCircle;
  const lossLength = halfCircle - gainLength;

  return (
    <div>
      <div className="tile-title" style={{ marginBottom: 12 }}>{label}</div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <svg viewBox="0 0 42 26" width={200} height={120} style={{ overflow: 'visible' }}>
          {hasData ? (
            <>
              <path
                d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
                fill="transparent"
                stroke="#ef4444"
                strokeWidth="6"
                strokeLinecap="butt"
              />
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
            <path
              d="M 5.085 21 A 15.915 15.915 0 0 1 36.915 21"
              fill="transparent"
              stroke="rgba(157,176,208,0.25)"
              strokeWidth="6"
              strokeLinecap="butt"
            />
          )}
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

export default ResultGauge;
