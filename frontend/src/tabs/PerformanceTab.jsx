import React, { useMemo, useState, useCallback } from 'react';
import DatePicker from '../components/DatePicker';
import { formatCurrency, formatPercent } from '../utils/format';

const PerformanceTab = () => {
  const [perfSubTab, setPerfSubTab] = useState('performance');
  const [perfShowValue, setPerfShowValue] = useState(true);
  const [perfShowContrib, setPerfShowContrib] = useState(true);
  const [perfIndexSel, setPerfIndexSel] = useState({ djia: false, nasdaq: false, sp500: false, r2k: false });
  const [perfQuickRange, setPerfQuickRange] = useState('3M');
  const [perfFrom, setPerfFrom] = useState('2023-04-21');
  const [perfTo, setPerfTo] = useState('2025-09-14');
  const [perfHistoryOpen, setPerfHistoryOpen] = useState({});

  const makePolyline = useCallback((arr, w = 100, h = 40) => {
    const min = Math.min(...arr);
    const max = Math.max(...arr);
    const span = max - min || 1;
    const step = arr.length > 1 ? w / (arr.length - 1) : w;
    return arr
      .map((v, i) => {
        const x = i * step;
        const y = h - ((v - min) / span) * h;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(' ');
  }, []);

  // Mock series
  const perfSeries = useMemo(() => {
    const n = 28;
    const value = Array.from({ length: n }, (_, i) => Math.max(0, i * 40 + Math.sin(i/3) * 30 + (i%5)*20));
    const contrib = Array.from({ length: n }, (_, i) => i * 25 + (i%6===0? 120:0));
    return { value, contrib };
  }, []);

  const perfValuePts = useMemo(() => makePolyline(perfSeries.value, 100, 40), [perfSeries, makePolyline]);
  const perfContribPts = useMemo(() => makePolyline(perfSeries.contrib, 100, 40), [perfSeries, makePolyline]);

  const IndexChip = ({ id, label }) => (
    <button
      className={`btn xs ${perfIndexSel[id] ? 'primary' : 'ghost'}`}
      onClick={() => setPerfIndexSel(s => ({ ...s, [id]: !s[id] }))}
    >{label}</button>
  );

  return (
    <>
      <h3 style={{ marginBottom: 12 }}>Performance</h3>

      {/* Sub-tabs */}
      <div className="row" style={{ gap: 8, marginBottom: 12 }}>
        <button className={`btn ${perfSubTab === 'performance' ? 'primary' : 'ghost'}`} onClick={() => setPerfSubTab('performance')}>Performance</button>
        <button className={`btn ${perfSubTab === 'asset' ? 'primary' : 'ghost'}`} onClick={() => setPerfSubTab('asset')}>Asset Allocation</button>
      </div>

      {/* Controls */}
      {perfSubTab === 'performance' && (
        <div className="card perf-controls" style={{ padding: 12, marginBottom: 16 }}>
          <div className="row" style={{ gap: 18, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
              {['3M','1Y','2024','YTD','Max'].map(k => (
                <button key={k} className={`btn xs ${perfQuickRange === k ? 'primary' : 'ghost'}`} onClick={() => setPerfQuickRange(k)} style={{ fontSize: 11, padding: '0 6px', height: 22 }}>{k}</button>
              ))}
            </div>
            <div className="perf-sep" aria-hidden="true" />
            <div className="row" style={{ gap: 8, alignItems: 'center', justifyContent: 'center' }}>
              <span className="muted" style={{ fontSize: 12 }}>From</span>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={perfFrom} onChange={setPerfFrom} max={perfTo} placeholder="dd/mm/yyyy" />
              </div>
              <span className="muted" style={{ fontSize: 12 }}>To</span>
              <div style={{ minWidth: 140 }}>
                <DatePicker label="" value={perfTo} onChange={setPerfTo} min={perfFrom} placeholder="dd/mm/yyyy" />
              </div>
            </div>
          </div>
        </div>
      )}

      {perfSubTab === 'performance' && (
        <div className="grid" style={{ gap: 16 }}>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0,1fr))', gap: 16, alignItems: 'start' }}>
            <div className="card" style={{ padding: 16 }}>
              <div className="muted" style={{ marginBottom: 6 }}>Total Return</div>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div style={{ fontSize: 24, fontWeight: 700 }} className={'up'}>
                  {formatCurrency(1284.08)}
                </div>
                <div style={{ fontSize: 18 }} className={'up'}>
                  {formatPercent(19.78)}
                </div>
              </div>
              <div className="card" style={{ padding: 12, marginTop: 12 }}>
                <svg viewBox="0 0 100 40" preserveAspectRatio="none" style={{ width: '100%', height: 160 }}>
                  {perfShowContrib && (
                    <polyline fill="none" stroke="#111" strokeDasharray="2,2" strokeWidth="1.2" points={perfContribPts} />
                  )}
                  {perfShowValue && (
                    <polyline fill="none" stroke="rgba(37,99,235,1)" strokeWidth="1.6" points={perfValuePts} />
                  )}
                </svg>
              </div>
              <div className="row" style={{ gap: 8, marginTop: 8, marginBottom: 16 }}>
                <button className={`btn xs ${perfShowValue ? 'primary' : 'ghost'}`} onClick={() => setPerfShowValue(v => !v)}>Value</button>
                <button className={`btn xs ${perfShowContrib ? 'primary' : 'ghost'}`} onClick={() => setPerfShowContrib(v => !v)}>Net contributions</button>
              </div>
            </div>

            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Common indexes</div>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                <IndexChip id="djia" label="DJIA" />
                <IndexChip id="nasdaq" label="NASDAQ" />
                <IndexChip id="sp500" label="S&P 500®" />
                <IndexChip id="r2k" label="Russell 2000®" />
              </div>
              {(() => {
                const allIdx = [
                  { id: 'r2k', label: 'Russell 2000®', value: '14.57%' },
                  { id: 'sp500', label: 'S&P 500®', value: '23.17%' },
                  { id: 'nasdaq', label: 'NASDAQ', value: '29.73%' },
                  { id: 'djia', label: 'Dow Jones Industrial Average (DJIA)', value: '15.74%' },
                ];
                const rows = allIdx.filter(x => perfIndexSel[x.id]);
                return (
                  <table className="table returns-compact">
                    <thead>
                      <tr style={{ textAlign: 'left' }}>
                        <th>Portfolio/Index</th>
                        <th>Rate of Return (Annualized)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Roth Contributory IRA</td>
                        <td>19.78%</td>
                      </tr>
                      {rows.map(r => (
                        <tr key={r.id}>
                          <td>{r.label}</td>
                          <td>{r.value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* Performance history section */}
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
                  <th>Selected Time Frame [04/21/2023 – 09/15/2025]</th>
                  <th>Year to Date</th>
                  <th>One Year</th>
                  <th>Since Available [04/21/2023]</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const rows = {
                    beginning: {
                      label: 'Beginning Value', values: ['$998.21', '$3,752.48', '$3,301.60', '$998.21'],
                      children: [
                        { label: 'Market Value', values: ['$998.21', '$3,752.48', '$3,301.60', '$998.21'] },
                        { label: 'Accrued Value', values: ['$0.00', '$0.00', '$0.00', '$0.00'] }
                      ]
                    },
                    net: {
                      label: 'Net Contributions (This Period)', values: ['+$2,920.00', '+$820.00', '+$1,220.00', '+$2,920.00'],
                      children: [
                        { label: 'Contributions', values: ['+$2,920.00', '+$820.00', '+$1,220.00', '+$2,920.00'] },
                        { label: 'Withdrawals', values: ['$0.00', '$0.00', '$0.00', '$0.00'] }
                      ]
                    },
                    invest: {
                      label: 'Investment Changes', values: ['+$1,284.08', '+$629.81', '+$680.69', '+$1,284.08'],
                      children: [
                        { label: 'Investment Gain/Loss', values: ['+$1,211.13', '+$624.47', '+$635.07', '+$1,211.13'] },
                        { label: 'Income', values: ['+$72.95', '+$5.34', '+$45.62', '+$72.95'] },
                        { label: 'Fees & Expenses', values: ['$0.00', '$0.00', '$0.00', '$0.00'] },
                      ]
                    },
                    ending: {
                      label: 'Ending Value', values: ['$5,202.29', '$5,202.29', '$5,202.29', '$5,202.29'],
                      children: [
                        { label: 'Market Value', values: ['$5,202.29', '$5,202.29', '$5,202.29', '$5,202.29'] },
                        { label: 'Accrued Value', values: ['$0.00', '$0.00', '$0.00', '$0.00'] }
                      ]
                    }
                  };
                  const toggle = (k) => setPerfHistoryOpen(s => ({ ...s, [k]: !s[k] }));
                  return Object.entries(rows).map(([key, row]) => (
                    <React.Fragment key={key}>
                      <tr className="perf-parent">
                        <td>
                          <button className="caret-btn" onClick={() => toggle(key)} aria-expanded={!!perfHistoryOpen[key]}>
                            <span className={`caret ${perfHistoryOpen[key] ? 'open' : ''}`}>▶</span>
                            {row.label}
                          </button>
                        </td>
                        {row.values.map((v, i) => <td key={i}>{v}</td>)}
                      </tr>
                      {perfHistoryOpen[key] && row.children.map((child, idx) => (
                        <tr className="perf-child" key={`${key}-c-${idx}`}>
                          <td>{child.label}</td>
                          {child.values.map((v, i) => <td key={i}>{v}</td>)}
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
        // Example mocked allocation data (sum ~100)
        const alloc = [
          { key: 'us_large', label: 'US Large Caps', pct: 90.1, color: '#3b82f6' },
          { key: 'small_cap', label: 'Small Cap', pct: 0.03, color: '#f59e0b' },
          { key: 'cash', label: 'Cash & Investments', pct: 5.77, color: '#22c55e' },
          { key: 'uncat', label: 'Uncategorized', pct: 4.19, color: '#a78bfa' },
        ];

        // Build 10x10 grid (100 tiles), guarantee at least 1 tile for any nonzero pct
        const totalTiles = 100;
        const base = alloc.map(a => ({ ...a, tiles: Math.floor(a.pct) }));
        alloc.forEach((a, i) => { if (a.pct > 0 && base[i].tiles === 0) base[i].tiles = 1; });
        let used = base.reduce((s, a) => s + a.tiles, 0);
        if (used > totalTiles) {
          const order = [...base].sort((a,b) => b.tiles - a.tiles);
          let over = used - totalTiles;
          for (const cat of order) {
            if (over <= 0) break;
            const idx = base.findIndex(x => x.key === cat.key);
            const canGive = Math.min(over, Math.max(0, base[idx].tiles - 1));
            if (canGive > 0) { base[idx].tiles -= canGive; over -= canGive; }
          }
          used = base.reduce((s,a)=>s+a.tiles,0);
        }
        if (used < totalTiles) {
          const rem = alloc
            .map((a, i) => ({ i, frac: a.pct - Math.floor(a.pct) }))
            .sort((a, b) => b.frac - a.frac);
          let idx = 0;
          while (used < totalTiles && idx < rem.length) { base[rem[idx].i].tiles += 1; used += 1; idx += 1; }
        }

        const tiles = [];
        base.forEach(a => { for (let i = 0; i < a.tiles; i++) tiles.push(a.key); });
        while (tiles.length < totalTiles) tiles.push(base[0]?.key || 'us_large');

        return (
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Allocation</div>
            <div className="muted" style={{ marginBottom: 12 }}>Asignación</div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 1fr) minmax(200px, 1fr)', gap: 16, alignItems: 'start' }}>
              {/* 10x10 squares grid */}
              <div style={{ position: 'relative', width: '100%' }}>
                <div style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 0, width: '100%', borderRadius: 0 }}>
                  {tiles.map((k, i) => {
                    const a = base.find(x => x.key === k) || base[0];
                    return <div key={i} title={alloc.find(x=>x.key===k)?.label} style={{ width: '100%', height: 24, background: a.color }} />;
                  })}
                </div>
              </div>

              {/* Legend */}
              <div style={{ display: 'grid', gap: 8, alignContent: 'start' }}>
                {alloc.map(a => (
                  <div key={a.key} style={{ display: 'grid', gridTemplateColumns: '14px 1fr max-content', gap: 8, alignItems: 'center' }}>
                    <span style={{ width: 14, height: 14, borderRadius: 3, display: 'inline-block', background: a.color, border: '1px solid rgba(255,255,255,.15)' }} />
                    <span style={{ fontSize: 12 }}>{a.label}</span>
                    <span className="muted" style={{ fontSize: 12 }}>{formatPercent(a.pct)}</span>
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
