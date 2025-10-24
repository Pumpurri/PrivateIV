import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { createPortal } from 'react-dom';
import {
  getDashboard,
  getPortfolioOverviewApi,
  setDefaultPortfolio,
  updatePortfolio,
  deletePortfolio,
} from '../services/api';

const fmt = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '-';
  return `S/ ${fmt.format(Number(n))}`;
};
const pct = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '-';
  return `${Number(n).toFixed(2)}%`;
};
const formatDateDDMMYYYY = (value) => {
  if (!value) return '';
  const d = new Date(value);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
};

function UserDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dash, setDash] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [badgeMode, setBadgeMode] = useState('amount'); // 'amount' | 'percent'
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
  const [editingMeta, setEditingMeta] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftDesc, setDraftDesc] = useState('');
  const [savingMeta, setSavingMeta] = useState(false);
  const [overlayRect, setOverlayRect] = useState(null);

  // Delete confirmation modal state
  const [deletingMeta, setDeletingMeta] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');
  const [deletingBusy, setDeletingBusy] = useState(false);

  const normalize = (s) =>
    (s || '')
      .toString()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();

  const popRef = useRef(null);
  const nameInputRef = useRef(null);
  const nameWrapRef = useRef(null);
  const origNameRef = useRef('');
  const origDescRef = useRef('');

  // Drag + FLIP animation helpers
  const isDraggingRef = useRef(false);
  const itemRefs = useRef({});
  const pendingPrevRects = useRef(null);
  const animateNextReorder = useRef(false);
  const longPressTimer = useRef(null);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const draggingIdRef = useRef(null);

  const computeOverlayRect = () => {
    try {
      const lr = listRef.current?.getBoundingClientRect();
      if (!lr) return null;
      const pad = 8;
      const vw = window.innerWidth || document.documentElement.clientWidth || 0;
      const vh = window.innerHeight || document.documentElement.clientHeight || 0;
      const top = Math.max(0, Math.round(lr.top - pad));
      const left = Math.max(0, Math.round(lr.left - pad));
      const width = Math.min(vw - left, Math.round(lr.width + pad * 2));
      const height = Math.min(vh - top, Math.round(lr.height + pad * 2));
      return { top, left, width, height };
    } catch {
      return null;
    }
  };

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

  const getRects = () => {
    const rects = {};
    portfolios.forEach((p) => {
      const el = itemRefs.current[p.id];
      if (el) rects[p.id] = el.getBoundingClientRect();
    });
    return rects;
  };

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
  }, [portfolios]);

  // Limit the visible list with internal scroll
  const measureList = () => {
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
  };

  useEffect(() => {
    const r = () => measureList();
    r();
    window.addEventListener('resize', r);
    return () => window.removeEventListener('resize', r);
  }, [portfolios, badgeMode, selectedId]);

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

  // Smooth enter animation for right detail card on selection changes
  useEffect(() => {
    if (!selectedId) return;
    setDetailEnter(true);
    const t = setTimeout(() => setDetailEnter(false), 350);
    return () => clearTimeout(t);
  }, [selectedId]);

  // Keep the blur overlay aligned with the left list when resizing/scrolling
  useEffect(() => {
    if (!(editingMeta || deletingMeta)) return;
    const update = () => {
      const rect = computeOverlayRect();
      if (rect) setOverlayRect(rect);
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, { passive: true });
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update);
    };
  }, [editingMeta, deletingMeta]);

  // Keep the edit overlay aligned with the left list during resize/scroll/layout changes
  useEffect(() => {
    if (!editingMeta) return;
    const updateRect = () => {
      try {
        const lr = listRef.current?.getBoundingClientRect();
        if (lr) {
          setOverlayRect({ top: lr.top, left: lr.left, width: lr.width, height: lr.height });
        }
      } catch {
        /* ignore */
      }
    };
    updateRect();
    window.addEventListener('resize', updateRect);
    const onScrollCapture = () => updateRect();
    window.addEventListener('scroll', onScrollCapture, true);
    let ro = null;
    try {
      if (typeof ResizeObserver !== 'undefined' && listRef.current) {
        ro = new ResizeObserver(updateRect);
        ro.observe(listRef.current);
      }
    } catch {
      /* ignore */
    }
    return () => {
      window.removeEventListener('resize', updateRect);
      window.removeEventListener('scroll', onScrollCapture, true);
      if (ro) ro.disconnect();
    };
  }, [editingMeta]);

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
        const d = await getDashboard();
        if (!mounted) return;
        setDash(d);
        const ordered = applySavedOrder(d.portfolios || []);
        const topId = ordered[0]?.id;
        const withDefault = ordered.map((p) => ({ ...p, is_default: p.id === topId }));
        setPortfolios(withDefault);
        // Auto-select first portfolio if user only has one
        setSelectedId(ordered.length === 1 ? topId : null);
      } catch (e) {
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
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadOverview = async () => {
      if (!selectedId) {
        setOverview(null);
        return;
      }
      setLoadingOverview(true);
      try {
        const d = await getPortfolioOverviewApi(selectedId, { days: 30 });
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
  }, [selectedId, dash]);

  if (loading) return <div className="muted">Cargando panel…</div>;
  if (!dash) return <div className="down">No se pudo cargar el panel</div>;

  const Pill = ({ label, abs, pctv, mode }) => {
    const hasValue = (v) => v !== null && v !== undefined && !Number.isNaN(Number(v));
    const up = hasValue(abs) ? Number(abs) >= 0 : null;
    const content = mode === 'percent'
      ? (hasValue(pctv) ? pct(Math.abs(pctv)) : '-')
      : (hasValue(abs) ? money(Math.abs(abs)) : '-');
    const className = up === null ? '' : (up ? 'up' : 'down');
    const sign = up === null ? '' : (up ? '+' : '−');
    return (
      <span className="badge">
        <span className="muted">{label}</span>
        <span className={className} style={{ fontWeight: 600 }}>
          {up === null ? '' : sign}
          {content}
        </span>
      </span>
    );
  };

  const hasSelection = !!selectedId;
  const compact = !hasSelection;

  const formatTimeHHMM = (value) => {
    if (!value) return '--:--';
    const d = new Date(value);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
  };

  const isOpenInTZ = (date, timeZone, openH, openM, closeH, closeM) => {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(date);
    const get = (type) => parts.find((p) => p.type === type)?.value || '';
    const wd = get('weekday');
    if (wd === 'Sat' || wd === 'Sun') return false;
    const h = Number(get('hour'));
    const m = Number(get('minute'));
    if (Number.isNaN(h) || Number.isNaN(m)) return false;
    const mins = h * 60 + m;
    const openMin = openH * 60 + openM;
    const closeMin = closeH * 60 + closeM;
    return mins >= openMin && mins < closeMin;
  };

  const nyseOpen = isOpenInTZ(now, 'America/New_York', 9, 30, 16, 0);
  const bvlOpen = isOpenInTZ(now, 'America/Lima', 8, 30, 16, 30);

  const formatDateDDMM = (value) => {
    if (!value) return '';
    const d = new Date(value);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}/${mm}`;
  };

  // No mock data: show '-' or empty states when data is missing

  return (
    <div className="dashboard">
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
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <div className="row" style={{ gap: 4 }}>
                  <button
                    className={`btn xs ${badgeMode === 'amount' ? 'primary' : 'ghost'}`}
                    onClick={() => setBadgeMode('amount')}
                  >
                    S/
                  </button>
                  <button
                    className={`btn xs ${badgeMode === 'percent' ? 'primary' : 'ghost'}`}
                    onClick={() => setBadgeMode('percent')}
                  >
                    %
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
                  S/
                </button>
                <button
                  className={`btn xs ${badgeMode === 'percent' ? 'primary' : 'ghost'}`}
                  onClick={() => setBadgeMode('percent')}
                >
                  %
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
                    <div style={{ fontSize: isMobile ? 14 : 16, fontWeight: 600 }}>{money(p.total_value)}</div>
                    <div className="row" style={{ gap: isMobile ? 2 : 4, flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
                      <Pill label="Día" abs={p.day_change_abs} pctv={p.day_change_pct} mode={badgeMode} />
                      <Pill label="Acum." abs={p.since_inception_abs} pctv={p.since_inception_pct} mode={badgeMode} />
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

            <div className={`dash-panel ${detailEnter ? 'enter' : ''}`} style={{ alignSelf: 'start' }}>
              <div className="card">
                {loadingOverview || !overview ? (
                  <div className="muted">Cargando resumen…</div>
                ) : overview.portfolio ? (
                  <div className="grid" style={{ gap: 10 }}>
                    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div ref={nameWrapRef} style={{ position: 'relative', flex: '1 1 auto', minWidth: 0 }}>
                        <div className="row" style={{ alignItems: 'center', gap: 6, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, minWidth: 0, flex: '1 1 auto' }}>
                            <h3
                              style={{
                                margin: 0,
                                marginLeft: 8,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                flex: 'none',
                              }}
                              title={overview.portfolio.name}
                            >
                              {overview.portfolio.name}
                            </h3>
                            <div className="row" style={{ gap: 2, alignItems: 'center', flex: 'none' }}>
                              <button
                                className="icon-inline-btn"
                                aria-label="Editar"
                                disabled={deletingMeta}
                                onClick={() => {
                                  if (deletingMeta) return;
                                  setOverlayRect(computeOverlayRect());
                                  setEditingMeta(true);
                                  const curName = overview.portfolio.name || '';
                                  const curDesc = overview.portfolio.description || '';
                                  origNameRef.current = curName;
                                  origDescRef.current = curDesc;
                                  setDraftName(curName);
                                  setDraftDesc(curDesc);
                                }}
                                title="Editar"
                              >
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="12"
                                  height="12"
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  aria-hidden="true"
                                >
                                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
                                </svg>
                              </button>
                              <button
                                className="icon-inline-btn"
                                aria-label="Eliminar"
                                disabled={editingMeta}
                                title="Eliminar portafolio"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (editingMeta) return;
                                  setOverlayRect(computeOverlayRect());
                                  setDeleteInput('');
                                  setDeletingMeta(true);
                                }}
                              >
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="12"
                                  height="12"
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  aria-hidden="true"
                                >
                                  <polyline points="3 6 5 6 21 6"></polyline>
                                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                                  <path d="M10 11v6"></path>
                                  <path d="M14 11v6"></path>
                                  <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path>
                                </svg>
                              </button>
                            </div>
                          </div>

                          {editingMeta
                            ? createPortal(
                                <div
                                  style={{
                                    position: 'fixed', inset: 0,
                                    display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
                                    padding: '64px 16px',
                                    background: 'rgba(0,0,0,0.35)',
                                    backdropFilter: 'blur(2px)', WebkitBackdropFilter: 'blur(2px)',
                                    zIndex: 1000,
                                  }}
                                >
                                  <div
                                    ref={popRef}
                                    className="card"
                                    style={{
                                      width: 'min(720px, 96vw)',
                                      maxHeight: 'calc(100vh - 128px)',
                                      padding: 12,
                                      overflow: 'auto',
                                      background: 'rgba(18,26,47,0.98)',
                                      borderRadius: 12,
                                      boxShadow: '0 12px 32px rgba(0,0,0,.35)',
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <form
                                      className="grid"
                                      style={{ gap: 8 }}
                                      onSubmit={async (e) => {
                                        e.preventDefault();
                                        if (savingMeta) return;
                                        const name = draftName.trim();
                                        if (!name) {
                                          try {
                                            nameInputRef.current?.focus();
                                            nameInputRef.current?.select();
                                          } catch {}
                                          return;
                                        }
                                        setSavingMeta(true);
                                        const id = overview.portfolio.id;
                                        const payload = { name, description: draftDesc.trim() };
                                        const prev = { name: overview.portfolio.name, description: overview.portfolio.description };
                                        try {
                                          // Optimistic sync
                                          setOverview((o) => (o ? { ...o, portfolio: { ...o.portfolio, ...payload } } : o));
                                          setPortfolios((list) =>
                                            list.map((pp) => (pp.id === id ? { ...pp, name: payload.name, description: payload.description } : pp))
                                          );
                                          await updatePortfolio(id, payload);
                                          try {
                                            const fresh = await getPortfolioOverviewApi(id, { days: 30 });
                                            setOverview(fresh);
                                          } catch {
                                            /* keep optimistic */
                                          }
                                          setEditingMeta(false);
                                        } catch {
                                          setOverview((o) => ({ ...o, portfolio: { ...o.portfolio, ...prev } }));
                                        } finally {
                                          setSavingMeta(false);
                                        }
                                      }}
                                    >
                                      <div className="grid" style={{ gap: 6 }}>
                                        <label className="muted" htmlFor="pf-name">
                                          Nombre
                                        </label>
                                        <input
                                          id="pf-name"
                                          ref={nameInputRef}
                                          className="input"
                                          value={draftName}
                                          maxLength={100}
                                          onChange={(e) => setDraftName(e.target.value)}
                                          autoFocus
                                          style={{ fontSize: 12, padding: '6px 8px' }}
                                        />
                                      </div>
                                      <div className="grid" style={{ gap: 6 }}>
                                        <label className="muted" htmlFor="pf-desc">
                                          Descripción
                                        </label>
                                        <textarea
                                          id="pf-desc"
                                          className="input"
                                          rows={6}
                                          value={draftDesc}
                                          style={{ fontSize: 12, padding: '6px 8px' }}
                                          onChange={(e) => setDraftDesc(e.target.value)}
                                        />
                                      </div>
                                      <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                                        <button
                                          type="button"
                                          className="btn xs ghost"
                                          onClick={() => {
                                            const n0 = origNameRef.current;
                                            const d0 = origDescRef.current;
                                            setOverview((o) => ({ ...o, portfolio: { ...o.portfolio, name: n0, description: d0 } }));
                                            setEditingMeta(false);
                                          }}
                                        >
                                          ✕
                                        </button>
                                        <button className="btn xs primary" type="submit" disabled={savingMeta || !draftName.trim()}>
                                          {savingMeta ? 'Guardando…' : 'Guardar'}
                                        </button>
                                      </div>
                                    </form>
                                  </div>
                                </div>,
                                document.body
                              )
                            : null}

                          {deletingMeta
                            ? createPortal(
                                <div
                                  style={{
                                    position: 'fixed', inset: 0,
                                    display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
                                    padding: '64px 16px',
                                    background: 'rgba(0,0,0,0.35)',
                                    backdropFilter: 'blur(2px)', WebkitBackdropFilter: 'blur(2px)',
                                    zIndex: 1000,
                                  }}
                                >
                                  <div
                                    className="card"
                                    style={{
                                      width: 'min(720px, 96vw)',
                                      maxHeight: 'calc(100vh - 128px)',
                                      padding: 12,
                                      overflow: 'auto',
                                      background: 'rgba(18,26,47,0.98)',
                                      borderRadius: 12,
                                      boxShadow: '0 12px 32px rgba(0,0,0,.35)',
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <div className="grid" style={{ gap: 8 }}>
                                      <h4 style={{ margin: 0 }}>Eliminar portafolio</h4>
                                      <p className="muted" style={{ margin: 0 }}>
                                        Para eliminar tu portafolio, escribe exactamente &quot;eliminar {overview.portfolio.name}&quot;.
                                      </p>
                                      <input
                                        className="input"
                                        placeholder={`eliminar ${overview.portfolio.name}`}
                                        value={deleteInput}
                                        onChange={(e) => setDeleteInput(e.target.value)}
                                        autoFocus
                                      />
                                      <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                                        <button
                                          type="button"
                                          className="btn xs ghost"
                                          onClick={() => {
                                            setDeletingMeta(false);
                                            setDeleteInput('');
                                          }}
                                        >
                                          ✕
                                        </button>
                                        <button
                                          type="button"
                                          className="btn xs danger"
                                          disabled={
                                            deletingBusy ||
                                            normalize(deleteInput) !== normalize(`eliminar ${overview.portfolio.name}`)
                                          }
                                          onClick={async () => {
                                            if (deletingBusy) return;
                                            setDeletingBusy(true);
                                            try {
                                              const id = overview.portfolio.id;
                                              await deletePortfolio(id);
                                              const d = await getDashboard();
                                              setDash(d);
                                              const ordered = applySavedOrder(d.portfolios || []);
                                              const topId = ordered[0]?.id;
                                              const withDefault = ordered.map((pp) => ({
                                                ...pp,
                                                is_default: pp.id === topId,
                                              }));
                                              setPortfolios(withDefault);
                                              setSelectedId(null);
                                              setOverview(null);
                                              setDeletingMeta(false);
                                              setDeleteInput('');
                                            } catch (err) {
                                              alert('No se pudo eliminar el portafolio. Intenta de nuevo.');
                                            } finally {
                                              setDeletingBusy(false);
                                            }
                                          }}
                                        >
                                          {deletingBusy ? 'Eliminando…' : 'Eliminar'}
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                </div>,
                                document.body
                              )
                            : null}
                        </div>
                        
                        {overview.portfolio.description && (
                          <div>
                            <span className="pill truncate" title={overview.portfolio.description}>
                              {overview.portfolio.description}
                            </span>
                          </div>
                        )}
                      </div>
                      <div style={{ textAlign: 'right', flex: 'none' }}>
                        <div className="muted" style={{ fontSize: 12 }}>
                          Valor total
                        </div>
                        <div style={{ fontWeight: 700, fontSize: 20 }}>{money(overview.portfolio.total_value)}</div>
                      </div>
                    </div>

                    <div
                      className="grid"
                      style={{ gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0,1fr))', gap: isMobile ? 8 : 10 }}
                    >
                      <div className="card">
                        <div className="muted">Efectivo</div>
                        <div>{money(overview.portfolio.cash_balance)}</div>
                      </div>
                      <div className="card">
                        <div className="muted">Inversión</div>
                        <div>{money(overview.portfolio.current_investment_value)}</div>
                      </div>
                      <div className="card">
                        <div className="muted">Activos</div>
                        <div>{overview.portfolio.holdings_count}</div>
                      </div>
                      <div className="card">
                        <div className="muted">TWR anual</div>
                        <div>{Number(overview.portfolio.twr_annualized).toFixed(4)}</div>
                      </div>
                      <div className="card">
                        <div className="muted">Hoy</div>
                        <div className={(overview.portfolio.day_change_abs === null || overview.portfolio.day_change_abs === undefined) ? '' : (Number(overview.portfolio.day_change_abs) >= 0 ? 'up' : 'down')}>
                          {badgeMode === 'percent'
                            ? pct(overview.portfolio.day_change_pct)
                            : money(overview.portfolio.day_change_abs)}
                        </div>
                      </div>
                      <div className="card">
                        <div className="muted">Desde inicio</div>
                        <div className={(overview.portfolio.since_inception_abs === null || overview.portfolio.since_inception_abs === undefined) ? '' : (Number(overview.portfolio.since_inception_abs) >= 0 ? 'up' : 'down')}>
                          {badgeMode === 'percent'
                            ? pct(overview.portfolio.since_inception_pct)
                            : money(overview.portfolio.since_inception_abs)}
                        </div>
                      </div>
                    </div>

                    <div className="grid" style={{ gridTemplateColumns: isMobile ? '1fr' : '1.25fr 0.75fr', gap: 10 }}>
                      {/* Actividad reciente (wider, first) */}
                      <div className="card">
                        <div className="muted" style={{ marginBottom: 6 }}>
                          Actividad reciente
                        </div>
                        <div className="table-wrap">
                          <table className="table table-transactions">
                            <thead>
                              <tr>
                                <th>Fecha</th>
                                <th>Tipo</th>
                                <th>Símbolo</th>
                                <th>Cant.</th>
                                <th>Monto (S/.)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(overview.recent_transactions?.length ? overview.recent_transactions : [])
                                .filter((tx) => {
                                  const oneYearAgo = new Date();
                                  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                                  return new Date(tx.timestamp) >= oneYearAgo;
                                })
                                .slice(0, isMobile ? 2 : 3)
                                .map((tx) => (
                                  <tr key={tx.id}>
                                    <td>{formatDateDDMM(tx.timestamp) || '-'}</td>
                                    <td>{tx.transaction_type_display || '-'}</td>
                                    <td>{tx.stock_symbol || '-'}</td>
                                    <td>{tx.quantity ?? '-'}</td>
                                    <td>{tx.amount != null ? fmt.format(Number(tx.amount)) : '-'}</td>
                                  </tr>
                                ))}
                              {!(overview.recent_transactions?.length) && (
                                <tr>
                                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--muted)', padding: '16px' }}>-</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                      {/* Composición (smaller, second) */}
                      <div className="card">
                        <div className="muted" style={{ marginBottom: 6 }}>
                          Composición
                        </div>
                        <div className="table-wrap">
                          <table className="table table-composition">
                            <thead>
                              <tr>
                                <th>Símbolo</th>
                                <th>Peso</th>
                              </tr>
                            </thead>
                            <tbody>
                              {overview.composition?.length ? (
                                overview.composition
                                  .slice(0, isMobile ? 2 : 3)
                                  .map((h, i) => (
                                    <tr key={i}>
                                      <td>{h.symbol}</td>
                                      <td>{h.weight_pct}%</td>
                                    </tr>
                                  ))
                              ) : (
                                <tr>
                                  <td colSpan="2" style={{ textAlign: 'center', color: 'var(--muted)', padding: '16px' }}>
                                    No tienes inversiones aún
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>

                    {overview.portfolio?.id && (
                      <div style={{ textAlign: 'center' }}>
                        <Link to={`/app/portfolios/${overview.portfolio.id}`} className="btn sm primary">
                          Ver detalle
                        </Link>
                      </div>
                    )}
                  </div>
              ) : (
                <div className="muted">Selecciona un portafolio</div>
              )}
            </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default UserDashboard;
