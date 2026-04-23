import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useParams, useNavigate } from 'react-router-dom';
import ErrorBoundary from './ErrorBoundary';
import { createTransaction, deletePortfolio, getFXRates, getPortfolio, getPortfolioHoldings, getTransactions, updatePortfolio } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const BalancesTab = React.lazy(() => import('../tabs/BalancesTab'));
const PositionsTab = React.lazy(() => import('../tabs/PositionsTab'));
const RealizedTab = React.lazy(() => import('../tabs/RealizedTab'));
const PerformanceTab = React.lazy(() => import('../tabs/PerformanceTab'));
const HistoryTab = React.lazy(() => import('../tabs/HistoryTab'));
const TradeTab = React.lazy(() => import('../tabs/TradeTab'));

const tabsList = [
  { id: 'balances', label: 'Balances' },
  { id: 'positions', label: 'Posiciones' },
  { id: 'realized', label: 'Ganancias Realizadas' },
  { id: 'performance', label: 'Rendimiento del Portafolio' },
  { id: 'history', label: 'Historial de Transacciones' },
  { id: 'trade', label: 'Operar', separator: true }
];

const PortfolioDetail = () => {
  const navigate = useNavigate();
  const { id, tab } = useParams();
  const { user } = useAuth();
  const isAdmin = user?.is_staff || user?.is_superuser;

  // Show all tabs, but mark admin-only tabs
  const visibleTabs = useMemo(() => {
    return tabsList.map(t => ({
      ...t,
      disabled: t.id === 'performance' && !isAdmin
    }));
  }, [isAdmin]);

  const tabsSet = useMemo(() => new Set(tabsList.map(t => t.id)), []);
  const initialTab = useMemo(() => {
    if (tab && tabsSet.has(tab)) return tab;
    return 'balances';
  }, [tab, tabsSet]);
  const [activeTab, setActiveTab] = useState(initialTab);
  const [loading, setLoading] = useState(true);
  const [portfolio, setPortfolio] = useState(null);
  const [holdings, setHoldings] = useState([]);
  const [holdingsSummary, setHoldingsSummary] = useState(null);
  const [displayCurrency, setDisplayCurrency] = useState('NATIVE');
  const [transactions, setTransactions] = useState([]);
  const lastDataLoadIdRef = React.useRef(null);
  const [editingMeta, setEditingMeta] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftDesc, setDraftDesc] = useState('');
  const [savingMeta, setSavingMeta] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');
  const [deleteModal, setDeleteModal] = useState(false);
  const [deletingPortfolio, setDeletingPortfolio] = useState(false);
  const [walletModal, setWalletModal] = useState(false);
  const [walletAction, setWalletAction] = useState('deposit');
  const [walletAmount, setWalletAmount] = useState('');
  const [walletSubmitting, setWalletSubmitting] = useState(false);
  const [walletError, setWalletError] = useState('');
  const [convertFrom, setConvertFrom] = useState('PEN');
  const [walletCurrency, setWalletCurrency] = useState('PEN');
  const [fxRates, setFxRates] = useState(null);
  const fxFetchedRef = useRef(false);
  const [hoveredDisabledTab, setHoveredDisabledTab] = useState(null);

  // Sync tab state with URL param; default to balances
  useEffect(() => {
    if (!tab) {
      navigate(`/app/portfolios/${id}/balances`, { replace: true });
      return;
    }

    // Redirect non-admin from admin-only tabs
    if (tab === 'performance' && !isAdmin) {
      navigate(`/app/portfolios/${id}/balances`, { replace: true });
      return;
    }

    if (tabsSet.has(tab) && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, [tab, id, tabsSet, activeTab, navigate, isAdmin]);

  // Load real data to avoid mock flicker
  useEffect(() => {
    if (!id) return;
    if (lastDataLoadIdRef.current === id) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [p, h, tx] = await Promise.all([
          getPortfolio(id),
          getPortfolioHoldings(id, displayCurrency ? { display_currency: displayCurrency } : {}).catch(() => ({ results: [] })),
          getTransactions({ portfolio: id }).catch(() => ({ results: [] })),
        ]);
        if (cancelled) return;
        lastDataLoadIdRef.current = id;
        setPortfolio(p);
        const holdingsList = Array.isArray(h?.results) ? h.results : Array.isArray(h) ? h : [];
        setHoldings(holdingsList);
        setHoldingsSummary(h?.summary || null);
        const txList = Array.isArray(tx?.results) ? tx.results : tx;
        setTransactions(txList || []);
      } catch (e) {
        if (cancelled) return;
        setPortfolio(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (walletAction !== 'convert' || fxFetchedRef.current) return;
    let cancelled = false;
    getFXRates().then(data => { if (!cancelled) { setFxRates(data); fxFetchedRef.current = true; } }).catch(() => {});
    return () => { cancelled = true; };
  }, [walletAction]);

  const refreshAll = async (currencyOverride) => {
    const currency = currencyOverride !== undefined ? currencyOverride : displayCurrency;
    try {
      const [p, h, tx] = await Promise.all([
        getPortfolio(id),
        getPortfolioHoldings(id, currency ? { display_currency: currency } : {}).catch(() => ({ results: [] })),
        getTransactions({ portfolio: id }).catch(() => ({ results: [] })),
      ]);
      setPortfolio(p);
      const holdingsList = Array.isArray(h?.results) ? h.results : Array.isArray(h) ? h : [];
      setHoldings(holdingsList);
      setHoldingsSummary(h?.summary || null);
      const txList = Array.isArray(tx?.results) ? tx.results : tx;
      setTransactions(txList || []);
    } catch (_) {}
  };

  const normalize = (value) => (value || '').toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

  const handleStartEdit = () => {
    if (!portfolio) return;
    setDraftName(portfolio.name || '');
    setDraftDesc(portfolio.description || '');
    setEditingMeta(true);
  };

  const handleSaveMeta = async (e) => {
    e?.preventDefault();
    if (!portfolio || savingMeta) return;
    const name = draftName.trim();
    if (!name) return;
    setSavingMeta(true);
    try {
      const payload = { name, description: draftDesc.trim() };
      await updatePortfolio(portfolio.id, payload);
      await refreshAll();
      setEditingMeta(false);
    } catch (err) {
      console.error(err);
      alert('No se pudo actualizar el portafolio. Intenta nuevamente.');
    } finally {
      setSavingMeta(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!portfolio || deletingPortfolio) return;
    const required = normalize(`eliminar ${portfolio.name || ''}`);
    if (normalize(deleteInput) !== required) return;
    setDeletingPortfolio(true);
    try {
      await deletePortfolio(portfolio.id);
      setDeleteModal(false);
      setDeleteInput('');
      navigate('/app/portfolios');
    } catch (err) {
      console.error(err);
      alert('No se pudo eliminar el portafolio. Intenta nuevamente.');
    } finally {
      setDeletingPortfolio(false);
    }
  };

  const closeWalletModal = () => {
    setWalletModal(false);
    setWalletAmount('');
    setWalletError('');
    setWalletAction('deposit');
    setConvertFrom('PEN');
    setWalletCurrency('PEN');
  };

  const handleWalletSubmit = async () => {
    if (!portfolio || walletSubmitting) return;
    const amountNum = Number(walletAmount);
    if (!Number.isFinite(amountNum) || amountNum <= 0) {
      setWalletError('Ingresa un monto válido.');
      return;
    }
    if (walletAction === 'withdraw') {
      const available = walletCurrency === 'USD'
        ? Number(portfolio?.cash_balance_usd ?? 0)
        : Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0);
      if (amountNum > available) {
        setWalletError(`El monto excede tu saldo disponible en ${walletCurrency === 'USD' ? 'dólares' : 'soles'}.`);
        return;
      }
    }
    if (walletAction === 'convert') {
      const available = convertFrom === 'PEN'
        ? Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0)
        : Number(portfolio?.cash_balance_usd ?? 0);
      if (amountNum > available) {
        setWalletError(`El monto excede tu saldo disponible en ${convertFrom === 'PEN' ? 'soles' : 'dólares'}.`);
        return;
      }
    }
    const amountPayload = Number(amountNum.toFixed(2));
    setWalletSubmitting(true);
    setWalletError('');
    try {
      const txPayload = walletAction === 'convert'
        ? { transaction_type: 'CONVERT', amount: amountPayload, cash_currency: convertFrom, counter_currency: convertFrom === 'PEN' ? 'USD' : 'PEN', idempotency_key: crypto.randomUUID(), portfolio_id: portfolio.id }
        : { transaction_type: walletAction === 'deposit' ? 'DEPOSIT' : 'WITHDRAWAL', amount: amountPayload, cash_currency: walletCurrency, idempotency_key: crypto.randomUUID(), portfolio_id: portfolio.id };
      await createTransaction(txPayload);
      try {
        const [updatedPortfolio, tx] = await Promise.all([
          getPortfolio(portfolio.id),
          getTransactions({ portfolio: portfolio.id }).catch(() => ({ results: [] })),
        ]);
        setPortfolio(updatedPortfolio);
        const txList = Array.isArray(tx?.results) ? tx.results : tx;
        setTransactions(txList || []);
      } catch {
        await refreshAll();
      }
      closeWalletModal();
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        'No se pudo procesar la operación.';
      setWalletError(detail);
    } finally {
      setWalletSubmitting(false);
    }
  };

  if (loading) return <div className="muted">Cargando…</div>;
  if (!portfolio) return <div>No encontrado</div>;

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(180deg, rgba(18,26,47,.9), rgba(12,20,39,.9))', padding: '40px 20px' }}>
      <style>{`
        .balance-date-picker .input { font-size: 12px !important; padding: 4px 8px !important; }
        .balance-date-picker .icon { width: 14px !important; height: 14px !important; }
        /* Sticky first column for positions/realized tables */
        .positions-table .sticky-col { position: sticky; left: 0; z-index: 2; background: rgba(12,20,39,1); backdrop-filter: saturate(120%) blur(2px); border-right: 1px solid var(--border); }
        .positions-table thead .sticky-col { z-index: 3; }
        /* Realized segmented control - moved to index.css */
        /* History table readability */
        .history-card h3 { font-size: 16px; }
        .history-table thead th { color: var(--muted); font-weight: 500; font-size: 12px; position: sticky; top: 0; background: linear-gradient(180deg, rgba(18,26,47,.96), rgba(12,20,39,.96)); z-index: 1; }
        .history-table tbody td { font-size: 12px; }
        .history-table tbody tr:hover { background: rgba(255,255,255,.03);}
        .history-table thead th:nth-child(4), .history-table tbody td:nth-child(4),
        .history-table thead th:nth-child(5), .history-table tbody td:nth-child(5),
        .history-table thead th:nth-child(6), .history-table tbody td:nth-child(6),
        .history-table thead th:nth-child(7), .history-table tbody td:nth-child(7) { text-align: right; }
        .history-table tbody td:nth-child(1), .history-table tbody td:nth-child(3) { white-space: normal; }

        /* Performance tables */
        .perf-returns-wrapper { overflow: auto; max-width: 100%; }
        .perf-returns { width: 100%; border-collapse: separate; border-spacing: 0; }
        .perf-returns th, .perf-returns td { padding: 8px 10px; }
        .perf-returns thead th { position: sticky; top: 0; background: rgba(255,255,255,.03); backdrop-filter: saturate(110%); }
        .perf-returns tbody tr:nth-child(odd) { background: rgba(255,255,255,.02); }
        .perf-returns td:not(:first-child), .perf-returns th:not(:first-child) { text-align: right; }

        .perf-history-wrapper { overflow: auto; max-width: 100%; }
        .perf-history { width: 100%; border-collapse: separate; border-spacing: 0; }
        .perf-history th, .perf-history td { padding: 8px 10px; }
        .perf-history thead th { position: sticky; top: 0; background: rgba(255,255,255,.03); backdrop-filter: saturate(110%); }
        .perf-history tbody tr:nth-child(odd) { background: rgba(255,255,255,.02); }
        .perf-history td:not(:first-child), .perf-history th:not(:first-child) { text-align: right; }
        .caret-btn { appearance: none; background: none; border: none; color: inherit; font: inherit; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; padding: 0; }
        .caret { display: inline-block; transition: transform .2s ease; }
        .caret.open { transform: rotate(90deg); }
        .perf-child td:first-child { padding-left: 18px; opacity: .95; }
        .perf-history .perf-parent td:first-child { color: rgba(99,179,237,1); font-weight: 700; }
        .perf-history .perf-parent td:not(:first-child) { color: #fff; font-weight: 700; }
        .portfolio-title { position: relative; cursor: help; display: inline-block; }
        .portfolio-title .portfolio-desc-tip {
          position: absolute;
          top: calc(100% + 8px);
          left: 50%;
          transform: translateX(-50%);
          background: rgba(12,20,39,0.95);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 8px;
          padding: 8px 12px;
          font-size: 12px;
          color: #e7eefc;
          max-width: min(70vw, 720px);
          width: max-content;
          box-shadow: 0 8px 20px rgba(0,0,0,0.35);
          opacity: 0;
          visibility: hidden;
          transition: opacity .15s ease, visibility .15s ease;
          z-index: 20;
          pointer-events: none;
        }
        .portfolio-title:hover .portfolio-desc-tip {
          opacity: 1;
          visibility: visible;
        }
        .portfolio-title .portfolio-desc-tip::before {
          content: '';
          position: absolute;
          top: -6px;
          left: 50%;
          transform: translateX(-50%);
          width: 0;
          height: 0;
          border-left: 6px solid transparent;
          border-right: 6px solid transparent;
          border-bottom: 6px solid rgba(12,20,39,0.95);
        }
      `}</style>

      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ marginBottom: 24, textAlign: 'center' }}>
          <div className="row" style={{ alignItems: 'center', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span
                className="portfolio-title"
                style={{
                  display: 'inline-block',
                  fontSize: 24,
                  fontWeight: 600,
                  textDecoration: portfolio.description ? 'underline dotted rgba(255,255,255,0.35)' : 'none',
                  textDecorationThickness: '1px',
                }}
              >
                {portfolio.name}
                {portfolio.description && (
                  <span className="portfolio-desc-tip">
                    {portfolio.description}
                  </span>
                )}
              </span>
            </div>
            <div className="row" style={{ gap: 4, alignItems: 'center', paddingTop: 4 }}>
              <button
                className="icon-inline-btn"
                aria-label="Depósitos y retiros"
                title="Abrir depósitos y retiros"
                onClick={() => {
                  setWalletAction('deposit');
                  setWalletModal(true);
                  setWalletAmount('');
                  setWalletError('');
                }}
                style={{ paddingTop: 6 }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <rect x="3" y="7" width="18" height="10" rx="2" ry="2" />
                  <path d="M16 7V5a2 2 0 0 0-2-2H3v4" />
                  <path d="M16 11h4" />
                  <circle cx="18" cy="13" r="1" />
                </svg>
              </button>
              <button
                className="icon-inline-btn"
                aria-label="Editar"
                title="Editar"
                onClick={handleStartEdit}
                style={{ paddingTop: 4 }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
                </svg>
              </button>
              <button
                className="icon-inline-btn"
                aria-label="Eliminar"
                title="Eliminar portafolio"
                onClick={() => {
                  setDeleteInput('');
                  setDeleteModal(true);
                }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                  <path d="M10 11v6"></path>
                  <path d="M14 11v6"></path>
                  <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>

        {editingMeta &&
          createPortal(
            <div
              style={{
                position: 'fixed',
                inset: 0,
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                padding: '64px 16px',
                background: 'rgba(0,0,0,0.35)',
                backdropFilter: 'blur(2px)',
                WebkitBackdropFilter: 'blur(2px)',
                zIndex: 1000,
              }}
              onClick={() => setEditingMeta(false)}
            >
              <div
                className="card"
                style={{
                  width: 'min(640px, 96vw)',
                  maxHeight: 'calc(100vh - 128px)',
                  padding: 16,
                  overflow: 'auto',
                  background: 'rgba(18,26,47,0.98)',
                  borderRadius: 12,
                  boxShadow: '0 12px 32px rgba(0,0,0,.35)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <form className="grid" style={{ gap: 8 }} onSubmit={handleSaveMeta}>
                  <div className="grid" style={{ gap: 4 }}>
                    <label className="muted" htmlFor="pf-name">Nombre</label>
                    <input
                      id="pf-name"
                      className="input"
                      value={draftName}
                      onChange={(e) => setDraftName(e.target.value)}
                      maxLength={100}
                      autoFocus
                    />
                  </div>
                  <div className="grid" style={{ gap: 4 }}>
                    <label className="muted" htmlFor="pf-desc">Descripción</label>
                    <textarea
                      id="pf-desc"
                      className="input"
                      rows={4}
                      value={draftDesc}
                      onChange={(e) => setDraftDesc(e.target.value)}
                    />
                  </div>
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    <button type="button" className="btn xs ghost" onClick={() => setEditingMeta(false)}>
                      Cancelar
                    </button>
                    <button type="submit" className="btn xs primary" disabled={savingMeta || !draftName.trim()}>
                      {savingMeta ? 'Guardando…' : 'Guardar'}
                    </button>
                  </div>
                </form>
              </div>
            </div>,
            document.body
          )}

        {deleteModal &&
          createPortal(
            <div
              style={{
                position: 'fixed',
                inset: 0,
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                padding: '64px 16px',
                background: 'rgba(0,0,0,0.35)',
                backdropFilter: 'blur(2px)',
                WebkitBackdropFilter: 'blur(2px)',
                zIndex: 1000,
              }}
              onClick={() => {
                setDeleteInput('');
                setDeleteModal(false);
              }}
            >
              <div
                className="card"
                style={{
                  width: 'min(640px, 96vw)',
                  maxHeight: 'calc(100vh - 128px)',
                  padding: 16,
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
                    Para eliminar tu portafolio, escribe exactamente <strong>"eliminar {portfolio.name}"</strong>.
                  </p>
                  <input
                    className="input"
                    value={deleteInput}
                    onChange={(e) => setDeleteInput(e.target.value)}
                    placeholder={`eliminar ${portfolio.name}`}
                    autoFocus
                  />
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    <button
                      type="button"
                      className="btn xs ghost"
                      onClick={() => {
                        setDeleteInput('');
                        setDeleteModal(false);
                      }}
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      className="btn xs danger"
                      disabled={
                        deletingPortfolio ||
                        normalize(deleteInput) !== normalize(`eliminar ${portfolio.name}`)
                      }
                      onClick={handleConfirmDelete}
                    >
                      {deletingPortfolio ? 'Eliminando…' : 'Eliminar'}
                    </button>
                  </div>
                </div>
              </div>
            </div>,
            document.body
          )}

        {walletModal &&
          createPortal(
            <div
              style={{
                position: 'fixed',
                inset: 0,
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                padding: '64px 16px',
                background: 'rgba(0,0,0,0.35)',
                backdropFilter: 'blur(2px)',
                WebkitBackdropFilter: 'blur(2px)',
                zIndex: 1000,
              }}
              onClick={closeWalletModal}
            >
              <div
                className="card"
                style={{
                  width: 'min(480px, 92vw)',
                  padding: 16,
                  background: 'rgba(18,26,47,0.98)',
                  borderRadius: 12,
                  boxShadow: '0 12px 32px rgba(0,0,0,.35)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                  <div className="grid" style={{ gap: 12 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontWeight: 600 }}>Depósitos, retiros y cambio</div>
                    </div>
                    {/* 3-way action toggle */}
                    <div style={{ display: 'flex', borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.18)' }}>
                      {[
                        { id: 'deposit', label: 'Depósito' },
                        { id: 'withdraw', label: 'Retiro' },
                        { id: 'convert', label: 'Cambiar S/ ↔ $' },
                      ].map((opt, i, arr) => (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => { setWalletAction(opt.id); setWalletError(''); setWalletAmount(''); setWalletCurrency('PEN'); }}
                          className="btn ghost"
                          style={{
                            flex: 1,
                            borderRadius: i === 0 ? '999px 0 0 999px' : i === arr.length - 1 ? '0 999px 999px 0' : '0',
                            padding: '10px 12px',
                            border: 'none',
                            borderRight: i < arr.length - 1 ? '1px solid rgba(255,255,255,0.12)' : 'none',
                            background: walletAction === opt.id ? 'var(--primary-600)' : 'transparent',
                            boxShadow: walletAction === opt.id ? '0 0 12px rgba(37,99,235,0.35)' : 'none',
                            color: walletAction === opt.id ? '#fff' : 'rgba(255,255,255,0.55)',
                            fontWeight: walletAction === opt.id ? 600 : 400,
                            fontSize: 13,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>

                    {walletAction === 'convert' ? (
                      <div className="grid" style={{ gap: 10 }}>
                        {/* Direction row */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1, background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: '8px 12px', textAlign: 'center' }}>
                            <div className="muted" style={{ fontSize: 10, marginBottom: 2 }}>De</div>
                            <div style={{ fontWeight: 600 }}>{convertFrom === 'PEN' ? 'S/ Soles' : '$ Dólares'}</div>
                            <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>
                              {convertFrom === 'PEN'
                                ? `Disponible: S/ ${Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0).toFixed(2)}`
                                : `Disponible: $ ${Number(portfolio?.cash_balance_usd ?? 0).toFixed(2)}`}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => { setConvertFrom(f => f === 'PEN' ? 'USD' : 'PEN'); setWalletAmount(''); setWalletError(''); }}
                            style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '50%', width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', fontSize: 16, flexShrink: 0 }}
                            title="Invertir dirección"
                          >
                            ⇄
                          </button>
                          <div style={{ flex: 1, background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: '8px 12px', textAlign: 'center' }}>
                            <div className="muted" style={{ fontSize: 10, marginBottom: 2 }}>A</div>
                            <div style={{ fontWeight: 600 }}>{convertFrom === 'PEN' ? '$ Dólares' : 'S/ Soles'}</div>
                            <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>
                              {convertFrom === 'PEN'
                                ? `Tienes: $ ${Number(portfolio?.cash_balance_usd ?? 0).toFixed(2)}`
                                : `Tienes: S/ ${Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0).toFixed(2)}`}
                            </div>
                          </div>
                        </div>

                        {/* Amount */}
                        <div className="grid" style={{ gap: 4 }}>
                          <label className="muted" htmlFor="wallet-amount" style={{ fontSize: 12 }}>
                            Monto en {convertFrom === 'PEN' ? 'soles (S/)' : 'dólares ($)'}
                          </label>
                          <input
                            id="wallet-amount"
                            className="input no-spin"
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="0.00"
                            value={walletAmount}
                            onChange={(e) => setWalletAmount(e.target.value)}
                          />
                        </div>

                        {/* Preview */}
                        {(() => {
                          const amt = Number(walletAmount);
                          if (!fxRates || !Number.isFinite(amt) || amt <= 0) return null;
                          const venta = Number(fxRates?.venta?.rate);
                          const compra = Number(fxRates?.compra?.rate);
                          let preview = null;
                          let rateLabel = '';
                          let rateVal = '';
                          if (convertFrom === 'PEN' && venta > 0) {
                            preview = (amt / venta).toFixed(2);
                            rateLabel = 'venta'; rateVal = venta.toFixed(4);
                          } else if (convertFrom === 'USD' && compra > 0) {
                            preview = (amt * compra).toFixed(2);
                            rateLabel = 'compra'; rateVal = compra.toFixed(4);
                          }
                          if (!preview) return null;
                          return (
                            <div style={{ background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)', borderRadius: 8, padding: '10px 12px' }}>
                              <div style={{ fontSize: 12, color: '#aaa', marginBottom: 4 }}>Recibirás aproximadamente</div>
                              <div style={{ fontSize: 18, fontWeight: 700, color: '#4ade80' }}>
                                {convertFrom === 'PEN' ? `$ ${preview}` : `S/ ${preview}`}
                              </div>
                              <div style={{ fontSize: 10, color: '#666', marginTop: 4 }}>
                                Tasa {rateLabel}: {rateVal} PEN/USD · El monto final lo determina el servidor
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    ) : (
                      <div className="grid" style={{ gap: 8 }}>
                        {/* Currency picker */}
                        <div style={{ display: 'flex', gap: 6 }}>
                          {['PEN', 'USD'].map(cur => (
                            <button
                              key={cur}
                              type="button"
                              onClick={() => { setWalletCurrency(cur); setWalletAmount(''); setWalletError(''); }}
                              style={{
                                flex: 1,
                                padding: '7px 0',
                                borderRadius: 8,
                                border: `1px solid ${walletCurrency === cur ? 'var(--primary-600)' : 'rgba(255,255,255,0.12)'}`,
                                background: walletCurrency === cur ? 'rgba(37,99,235,0.18)' : 'transparent',
                                color: walletCurrency === cur ? '#fff' : 'rgba(255,255,255,0.45)',
                                fontWeight: walletCurrency === cur ? 600 : 400,
                                fontSize: 13,
                                cursor: 'pointer',
                              }}
                            >
                              {cur === 'PEN' ? 'S/ Soles' : '$ Dólares'}
                            </button>
                          ))}
                        </div>
                        {/* Balance for selected currency */}
                        <div className="muted" style={{ fontSize: 12 }}>
                          {walletAction === 'withdraw' ? 'Disponible para retirar: ' : 'Saldo actual: '}
                          {walletCurrency === 'USD'
                            ? `$ ${Number(portfolio?.cash_balance_usd ?? 0).toFixed(2)}`
                            : `S/ ${Number(portfolio?.cash_balance_pen ?? portfolio?.cash_balance ?? 0).toFixed(2)}`}
                        </div>
                        <div className="grid" style={{ gap: 4 }}>
                          <label className="muted" htmlFor="wallet-amount">
                            Monto en {walletCurrency === 'USD' ? 'dólares ($)' : 'soles (S/)'}
                          </label>
                          <input
                            id="wallet-amount"
                            className="input no-spin"
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="0.00"
                            value={walletAmount}
                            onChange={(e) => setWalletAmount(e.target.value)}
                          />
                        </div>
                      </div>
                    )}
                  {walletError && (
                    <div className="card" style={{ background: 'rgba(239,68,68,0.12)', color: '#fca5a5', padding: 8, fontSize: 12 }}>
                      {walletError}
                    </div>
                  )}
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    <button className="btn xs ghost" onClick={closeWalletModal}>
                      Cancelar
                    </button>
                    <button
                      className="btn xs primary"
                      onClick={handleWalletSubmit}
                      disabled={walletSubmitting}
                    >
                      {walletSubmitting ? 'Procesando…' : 'Confirmar'}
                    </button>
                  </div>
                </div>
              </div>
            </div>,
            document.body
          )}

        {/* Tabs Nav */}
        <div className="row" style={{ gap: 8, marginBottom: 24, borderBottom: '1px solid var(--border)', paddingBottom: 8, justifyContent: 'center', alignItems: 'center' }}>
          {visibleTabs.map((t) => (
            <React.Fragment key={t.id}>
              {t.separator && <span style={{ color: 'var(--border)', fontSize: 18, fontWeight: 300 }}>|</span>}
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <button
                  className={`btn ${activeTab === t.id ? 'primary' : 'ghost'}`}
                  onClick={() => !t.disabled && navigate(`/app/portfolios/${id}/${t.id}`)}
                  style={{
                    fontSize: 14,
                    opacity: t.disabled ? 0.4 : 1,
                    cursor: t.disabled ? 'not-allowed' : 'pointer',
                    pointerEvents: t.disabled ? 'none' : 'auto'
                  }}
                  onMouseEnter={() => {
                    // simple prefetch hint
                    if (!t.disabled) {
                      if (t.id === 'performance') import('../tabs/PerformanceTab');
                      if (t.id === 'realized') import('../tabs/RealizedTab');
                    }
                  }}
                  disabled={t.disabled}
                >
                  {t.label}
                </button>
                {t.disabled && (
                  <>
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        cursor: 'not-allowed',
                        zIndex: 1
                      }}
                      onMouseEnter={() => setHoveredDisabledTab(t.id)}
                      onMouseLeave={() => setHoveredDisabledTab(null)}
                    />
                    {hoveredDisabledTab === t.id && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '-32px',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          background: 'rgba(0, 0, 0, 0.9)',
                          color: '#fff',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          whiteSpace: 'nowrap',
                          zIndex: 1000,
                          pointerEvents: 'none'
                        }}
                      >
                        En desarrollo
                        <div
                          style={{
                            position: 'absolute',
                            top: '-4px',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            width: 0,
                            height: 0,
                            borderLeft: '4px solid transparent',
                            borderRight: '4px solid transparent',
                            borderBottom: '4px solid rgba(0, 0, 0, 0.9)'
                          }}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            </React.Fragment>
          ))}
        </div>

        {/* Content */}
        <ErrorBoundary>
          <React.Suspense fallback={<div className="muted">Loading…</div>}>
            {activeTab === 'balances' && <BalancesTab portfolio={portfolio} transactions={transactions} />}
            {activeTab === 'positions' && <PositionsTab portfolio={portfolio} holdings={holdings} summary={holdingsSummary} displayCurrency={displayCurrency} onDisplayCurrencyChange={async (cur) => { setDisplayCurrency(cur); await refreshAll(cur); }} />}
            {activeTab === 'realized' && <RealizedTab portfolio={portfolio} />}
            {activeTab === 'performance' && isAdmin && <PerformanceTab />}
            {activeTab === 'history' && <HistoryTab transactions={transactions} />}
            {activeTab === 'trade' && <TradeTab portfolio={portfolio} holdings={holdings} onTransaction={refreshAll} />}
          </React.Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
};

export default PortfolioDetail;
