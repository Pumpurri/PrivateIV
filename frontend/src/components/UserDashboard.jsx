import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  getDashboard,
  getPortfolioOverviewApi,
  setDefaultPortfolio,
  updatePortfolio,
  deletePortfolio,
} from '../services/api';
import { ChangePill, MoneyValue } from './dashboard/DashboardValues';
import PortfolioOverview from './dashboard/PortfolioOverview';
import {
  formatTimeHHMM,
  isMarketOpen,
  readStoredCurrencyMode,
} from './dashboard/dashboardFormat';
function UserDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dash, setDash] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [badgeMode, setBadgeMode] = useState('amount'); // 'amount' | 'percent'
  const [currencyMode, setCurrencyMode] = useState(readStoredCurrencyMode); // 'PEN' | 'USD'
  const [portfolios, setPortfolios] = useState([]);
  const [dragIndex, setDragIndex] = useState(null);
  const listRef = useRef(null);
  const [listMaxHeight, setListMaxHeight] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [now, setNow] = useState(new Date());
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth <= 768 : false
  );
  const [detailEnter, setDetailEnter] = useState(false);
  // Drag + FLIP animation helpers
  const isDraggingRef = useRef(false);
  const itemRefs = useRef({});
  const pendingPrevRects = useRef(null);
  const animateNextReorder = useRef(false);
  const longPressTimer = useRef(null);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const draggingIdRef = useRef(null);

  const startDrag = (idx) => {
    isDraggingRef.current = true;
    setDragIndex(idx);
    const id = portfolios[idx]?.id;
    draggingIdRef.current = id ?? null;
    const el = id ? itemRefs.current[id] : null;
    if (el) el.classList.add('dragging');
  };

  const endDrag = (save) => {
    if (save && dragIndex !== null) saveOrder(portfolios);
    const id = draggingIdRef.current;
    if (id && itemRefs.current[id]) itemRefs.current[id]?.classList.remove('dragging');
    isDraggingRef.current = false;
    draggingIdRef.current = null;
    setDragIndex(null);
  };

  const getRects = useCallback(() => {
    const rects = {};
    portfolios.forEach((p) => {
      const el = itemRefs.current[p.id];
      if (el) rects[p.id] = el.getBoundingClientRect();
    });
    return rects;
  }, [portfolios]);

  useEffect(() => {
    if (!animateNextReorder.current || !pendingPrevRects.current) return;
    const prev = pendingPrevRects.current;
    const nextRects = getRects();
    Object.keys(nextRects).forEach((id) => {
      const before = prev[id];
      const after = nextRects[id];
      if (!before || !after) return;
      const dx = before.left - after.left;
      const dy = before.top - after.top;
      if (dx || dy) {
        const el = itemRefs.current[id];
        if (!el) return;
        el.style.transform = `translate(${dx}px, ${dy}px)`;
        el.style.transition = 'none';
        requestAnimationFrame(() => {
          el.style.transition = 'transform 150ms ease';
          el.style.transform = '';
          const cleanup = () => {
            el.style.transition = '';
            el.removeEventListener('transitionend', cleanup);
          };
          el.addEventListener('transitionend', cleanup);
        });
      }
    });
    animateNextReorder.current = false;
    pendingPrevRects.current = null;
  }, [getRects]);

  // Limit the visible list with internal scroll
  const measureList = useCallback(() => {
    const listEl = listRef.current;
    if (!listEl) return;
    const firstCard = listEl.querySelector('.card');
    if (!firstCard) {
      setListMaxHeight(null);
      return;
    }
    const cardH = firstCard.getBoundingClientRect().height;
    const cs = getComputedStyle(listEl);
    const gap = parseInt(cs.rowGap || cs.gap || '0', 10) || 0;
    const visible = typeof window !== 'undefined' && window.innerWidth <= 768 ? 4 : 7;

    // Only set maxHeight (and show fade-mask) if there are more portfolios than can fit
    if (portfolios.length > visible) {
      const maxH = cardH * visible + gap * (visible - 1);
      setListMaxHeight(maxH);
    } else {
      setListMaxHeight(null);
    }
  }, [portfolios.length]);

  useEffect(() => {
    const r = () => measureList();
    r();
    window.addEventListener('resize', r);
    return () => window.removeEventListener('resize', r);
  }, [portfolios, badgeMode, selectedId, measureList]);

  // Track viewport to adapt layout for mobile
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Tick every 30s to refresh market open/closed indicators
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('dashboardCurrencyMode', currencyMode);
    } catch {
      /* ignore */
    }
  }, [currencyMode]);

  // Smooth enter animation for right detail card on selection changes
  useEffect(() => {
    if (!selectedId) return;
    setDetailEnter(true);
    const t = setTimeout(() => setDetailEnter(false), 350);
    return () => clearTimeout(t);
  }, [selectedId]);

  const saveOrder = async (items) => {
    try {
      const ids = items.map((p) => p.id);
      localStorage.setItem('portfolioOrder', JSON.stringify(ids));
      // Make top portfolio the default
      const topId = ids[0];
      if (topId) {
        // Optimistically update UI star
        setPortfolios((cur) => cur.map((p) => ({ ...p, is_default: p.id === topId })));
        try {
          await setDefaultPortfolio(topId);
        } catch {
          /* ignore network errors for now */
        }
      }
    } catch {
      /* ignore */
    }
  };

  const applySavedOrder = (items) => {
    try {
      const raw = localStorage.getItem('portfolioOrder');
      if (!raw) return items;
      const order = JSON.parse(raw);
      const map = new Map(items.map((p) => [p.id, p]));
      const ordered = order.map((id) => map.get(id)).filter(Boolean);
      const remaining = items.filter((p) => !order.includes(p.id));
      return [...ordered, ...remaining];
    } catch {
      return items;
    }
  };

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const d = await getDashboard({ currency: currencyMode });
        if (!mounted) return;
        setDash(d);
        const ordered = applySavedOrder(d.portfolios || []);
        const topId = ordered[0]?.id;
        const withDefault = ordered.map((p) => ({ ...p, is_default: p.id === topId }));
        setPortfolios(withDefault);
        // Auto-select first portfolio if user only has one
        setSelectedId((prev) => prev ?? (ordered.length === 1 ? topId : null));
      } catch {
        if (!mounted) return;
        setError('No se pudo cargar el panel');
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [currencyMode]);

  useEffect(() => {
    let mounted = true;
    const loadOverview = async () => {
      if (!selectedId) {
        setOverview(null);
        return;
      }
      setLoadingOverview(true);
      try {
        const d = await getPortfolioOverviewApi(selectedId, { days: 30, currency: currencyMode });
        if (!mounted) return;
        setOverview(d);
        setLastUpdated(new Date());
      } catch {
        if (!mounted) return;
        setOverview(null);
        setLastUpdated(new Date());
      } finally {
        setLoadingOverview(false);
      }
    };
    loadOverview();
    return () => {
      mounted = false;
    };
  }, [selectedId, dash, currencyMode]);

  if (loading) return <div className="muted">Cargando panel…</div>;
  if (!dash) return <div className="down">No se pudo cargar el panel</div>;

  const hasSelection = !!selectedId;
  const compact = !hasSelection;
  const nyseOpen = isMarketOpen(now, 'America/New_York', 9, 30, 16, 0);
  const bvlOpen = isMarketOpen(now, 'America/Lima', 8, 30, 16, 30);

  const savePortfolioMetadata = async (payload) => {
    const currentPortfolio = overview?.portfolio;
    if (!currentPortfolio) return false;
    const previous = {
      name: currentPortfolio.name,
      description: currentPortfolio.description,
    };

    setOverview((current) => (
      current ? { ...current, portfolio: { ...current.portfolio, ...payload } } : current
    ));
    setPortfolios((items) => items.map((item) => (
      item.id === currentPortfolio.id ? { ...item, ...payload } : item
    )));

    try {
      await updatePortfolio(currentPortfolio.id, payload);
      try {
        const fresh = await getPortfolioOverviewApi(currentPortfolio.id, {
          days: 30,
          currency: currencyMode,
        });
        setOverview(fresh);
      } catch {
        // Keep the successfully saved optimistic state if refreshing fails.
      }
      return true;
    } catch {
      setOverview((current) => (
        current ? { ...current, portfolio: { ...current.portfolio, ...previous } } : current
      ));
      setPortfolios((items) => items.map((item) => (
        item.id === currentPortfolio.id ? { ...item, ...previous } : item
      )));
      return false;
    }
  };

  const removeSelectedPortfolio = async () => {
    const portfolioId = overview?.portfolio?.id;
    if (!portfolioId) return;
    await deletePortfolio(portfolioId);
    const freshDashboard = await getDashboard({ currency: currencyMode });
    setDash(freshDashboard);
    const ordered = applySavedOrder(freshDashboard.portfolios || []);
    const topId = ordered[0]?.id;
    setPortfolios(ordered.map((portfolio) => ({
      ...portfolio,
      is_default: portfolio.id === topId,
    })));
    setSelectedId(null);
    setOverview(null);
  };

  return (
    <div className="dashboard">
      {error && <div role="alert" className="down">{error}</div>}
      <div
        className="grid dash-wrap"
        style={
          isMobile
            ? { gridTemplateColumns: '1fr', gap: 10, maxWidth: '100%', margin: '0 auto', padding: '8px 12px' }
            : hasSelection
            ? { gridTemplateColumns: '1.1fr 1fr', gap: 16, maxWidth: 980, margin: '0 auto', paddingTop: 16 }
            : { gridTemplateColumns: '1fr', gap: 12, maxWidth: 580, margin: '0 auto', paddingTop: 16 }
        }
      >
        {/* Left: portfolios list */}
        <div
          ref={listRef}
          className={`grid dash-list ${listMaxHeight ? 'fade-mask' : ''}`}
          style={{
            gap: compact ? 10 : 12,
            maxHeight: listMaxHeight ?? undefined,
            overflowY: listMaxHeight ? 'auto' : undefined,
            overscrollBehavior: 'contain',
          }}
        >
          {isMobile ? (
            <div className="grid" style={{ gap: 6, width: '100%' }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <div className="row" style={{ gap: 4 }}>
                  <button
                    className={`btn xs ${badgeMode === 'amount' ? 'primary' : 'ghost'}`}
                    onClick={() => setBadgeMode('amount')}
                  >
                    Monto
                  </button>
                  <button
                    className={`btn xs ${badgeMode === 'percent' ? 'primary' : 'ghost'}`}
                    onClick={() => setBadgeMode('percent')}
                  >
                    %
                  </button>
                </div>
                <div className="row" style={{ gap: 4 }} aria-label="Moneda de visualización">
                  <button
                    className={`btn xs ${currencyMode === 'PEN' ? 'primary' : 'ghost'}`}
                    onClick={() => setCurrencyMode('PEN')}
                    title="Mostrar en soles"
                  >
                    S/
                  </button>
                  <button
                    className={`btn xs ${currencyMode === 'USD' ? 'primary' : 'ghost'}`}
                    onClick={() => setCurrencyMode('USD')}
                    title="Mostrar en dólares"
                  >
                    $
                  </button>
                </div>
                <Link to="/app/portfolios" className="btn sm primary">Crear</Link>
              </div>
            </div>
          ) : (
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8, width: '100%' }}>
              <div className="row" style={{ gap: 6, alignItems: 'center' }}>
                <button
                  className={`btn xs ${badgeMode === 'amount' ? 'primary' : 'ghost'}`}
                  onClick={() => setBadgeMode('amount')}
                >
                  Monto
                </button>
                <button
                  className={`btn xs ${badgeMode === 'percent' ? 'primary' : 'ghost'}`}
                  onClick={() => setBadgeMode('percent')}
                >
                  %
                </button>
                <span style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 4px' }} />
                <button
                  className={`btn xs ${currencyMode === 'PEN' ? 'primary' : 'ghost'}`}
                  onClick={() => setCurrencyMode('PEN')}
                  title="Mostrar en soles"
                >
                  S/
                </button>
                <button
                  className={`btn xs ${currencyMode === 'USD' ? 'primary' : 'ghost'}`}
                  onClick={() => setCurrencyMode('USD')}
                  title="Mostrar en dólares"
                >
                  $
                </button>
              </div>
              <div>
                <Link to="/app/portfolios" className="btn sm primary">Crear portafolio</Link>
              </div>
            </div>
          )}

          {portfolios?.map((p, idx) => (
            <div
              key={p.id}
              ref={(el) => {
                if (el) itemRefs.current[p.id] = el;
                else delete itemRefs.current[p.id];
              }}
              className="card hoverable"
              role="button"
              onClick={() => {
                if (isDraggingRef.current) return;
                setSelectedId((prev) => (prev === p.id ? null : p.id));
              }}
              style={{ borderColor: selectedId === p.id ? 'rgba(59,130,246,.45)' : 'var(--border)', padding: isMobile ? 12 : 10 }}
              draggable
              onDragStart={() => {
                startDrag(idx);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                if (dragIndex === null || dragIndex === idx) return;
                const rect = e.currentTarget.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                const y = e.clientY;
                const shouldMove = (dragIndex < idx && y > midY) || (dragIndex > idx && y < midY);
                if (!shouldMove) return;
                const next = portfolios.slice();
                const [moved] = next.splice(dragIndex, 1);
                next.splice(idx, 0, moved);
                pendingPrevRects.current = getRects();
                animateNextReorder.current = true;
                setPortfolios(next);
                setDragIndex(idx);
              }}
              onDrop={() => {
                endDrag(true);
              }}
              onDragEnd={() => {
                endDrag(false);
              }}
              onTouchStart={(e) => {
                if (longPressTimer.current) clearTimeout(longPressTimer.current);
                const t = e.touches[0];
                touchStartRef.current = { x: t.clientX, y: t.clientY };
                longPressTimer.current = setTimeout(() => {
                  startDrag(idx);
                }, 250);
              }}
              onTouchMove={(e) => {
                const t = e.touches[0];
                const dx = t.clientX - touchStartRef.current.x;
                const dy = t.clientY - touchStartRef.current.y;
                const dist2 = dx * dx + dy * dy;
                if (!isDraggingRef.current) {
                  if (dist2 > 81) {
                    if (longPressTimer.current) clearTimeout(longPressTimer.current);
                  }
                  return;
                }
                e.preventDefault();
                const y = t.clientY;
                const rects = portfolios.map((pp) => itemRefs.current[pp.id]?.getBoundingClientRect());
                let targetIdx = dragIndex;
                for (let i = 0; i < rects.length; i++) {
                  const r = rects[i];
                  if (!r) continue;
                  const mid = r.top + r.height / 2;
                  if (y < mid) {
                    targetIdx = i;
                    break;
                  }
                  targetIdx = i;
                }
                if (targetIdx !== dragIndex && targetIdx !== null && targetIdx >= 0) {
                  if (dragIndex === null) return;
                  const next = portfolios.slice();
                  const [moved] = next.splice(dragIndex, 1);
                  next.splice(targetIdx, 0, moved);
                  pendingPrevRects.current = getRects();
                  animateNextReorder.current = true;
                  setPortfolios(next);
                  setDragIndex(targetIdx);
                }
              }}
              onTouchEnd={() => {
                if (longPressTimer.current) clearTimeout(longPressTimer.current);
                if (isDraggingRef.current) endDrag(true);
              }}
              onTouchCancel={() => {
                if (longPressTimer.current) clearTimeout(longPressTimer.current);
                if (isDraggingRef.current) endDrag(false);
              }}
            >
              <div className="card-inner-wrap" style={{ maxWidth: compact ? 480 : '100%', margin: compact ? '0 auto' : 0, padding: 0 }}>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: isMobile ? 'flex-start' : 'center' }}>
                  <div style={{ flex: '1 1 auto', minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <strong
                        style={{ fontSize: isMobile ? 14 : 16, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={p.name}
                      >
                        {p.name}
                      </strong>
                      {p.is_default && (
                        <span className="star-default" title="Predeterminado" aria-label="Predeterminado">
                          ★
                        </span>
                      )}
                    </div>
                  </div>
                  <div
                    className="grid"
                    style={{ justifyItems: 'center', textAlign: 'center', gap: isMobile ? 2 : 4, flex: '0 0 auto', minWidth: isMobile ? undefined : 160 }}
                  >
                    <MoneyValue
                      portfolio={p}
                      field="total_value"
                      currency={currencyMode}
                      style={{ fontSize: isMobile ? 14 : 16, fontWeight: 600 }}
                    />
                    <div className="row" style={{ gap: isMobile ? 2 : 4, flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
                      <ChangePill
                        label="Día"
                        portfolio={p}
                        amountKey="day_change_abs"
                        percentKey="day_change_pct"
                        mode={badgeMode}
                        currency={currencyMode}
                      />
                      <ChangePill
                        label="Acum."
                        portfolio={p}
                        amountKey="since_inception_abs"
                        percentKey="since_inception_pct"
                        mode={badgeMode}
                        currency={currencyMode}
                      />
                    </div>
                  </div>
                </div>
              </div>
              {/* Description intentionally hidden in summary list */}
            </div>
          ))}
        </div>

        {/* Right: selected overview */}
        {hasSelection && (
          <div style={{ alignSelf: 'start', display: 'grid', gap: 8 }}>
            {/* Top bar above the right card */}
            {isMobile ? (
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <div className="row" style={{ gap: 4 }}>
                  <span className={`badge ${bvlOpen ? 'green' : 'red'}`}>BVL: {bvlOpen ? 'Abierto' : 'Cerrado'}</span>
                  <span className={`badge ${nyseOpen ? 'green' : 'red'}`}>NYSE: {nyseOpen ? 'Abierto' : 'Cerrado'}</span>
                </div>
                <span className="muted" style={{ fontSize: 11 }}>
                  Últ. act. {formatTimeHHMM(lastUpdated)}
                </span>
              </div>
            ) : (
              <div className="row" style={{ justifyContent: 'flex-end', alignItems: 'center', gap: 6 }}>
                <span className="badge">
                  <span className="muted">Últ. act.</span>
                  <span style={{ fontWeight: 600 }}>{formatTimeHHMM(lastUpdated)}</span>
                </span>
                <span className={`badge ${bvlOpen ? 'green' : 'red'}`}>BVL: {bvlOpen ? 'Abierto' : 'Cerrado'}</span>
                <span className={`badge ${nyseOpen ? 'green' : 'red'}`}>NYSE: {nyseOpen ? 'Abierto' : 'Cerrado'}</span>
              </div>
            )}

            <PortfolioOverview
              overview={overview}
              loading={loadingOverview}
              entering={detailEnter}
              isMobile={isMobile}
              badgeMode={badgeMode}
              currencyMode={currencyMode}
              onSave={savePortfolioMetadata}
              onDelete={removeSelectedPortfolio}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default UserDashboard;
