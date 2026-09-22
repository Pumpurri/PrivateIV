import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { formatRatePercent } from '../../utils/format';
import { MoneyValue, SignedMoneyValue } from './DashboardValues';
import {
  CURRENCY_PREFIX,
  formatDateDDMM,
  hasValue,
  normalizeText,
  NUMBER_FORMAT,
  percent,
} from './dashboardFormat';

const modalBackdropStyle = {
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
};

const modalCardStyle = {
  width: 'min(720px, 96vw)',
  maxHeight: 'calc(100vh - 128px)',
  padding: 12,
  overflow: 'auto',
  background: 'rgba(18,26,47,0.98)',
  borderRadius: 12,
  boxShadow: '0 12px 32px rgba(0,0,0,.35)',
};

const EditIcon = () => (
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
);

const DeleteIcon = () => (
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
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
    <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
  </svg>
);

const PortfolioOverview = ({
  overview,
  loading,
  entering,
  isMobile,
  badgeMode,
  currencyMode,
  onSave,
  onDelete,
}) => {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftDescription, setDraftDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const nameInputRef = useRef(null);

  const portfolio = overview?.portfolio;

  const openEditor = () => {
    setDraftName(portfolio?.name || '');
    setDraftDescription(portfolio?.description || '');
    setEditing(true);
  };

  const submitEdit = async (event) => {
    event.preventDefault();
    if (saving) return;
    const name = draftName.trim();
    if (!name) {
      nameInputRef.current?.focus();
      nameInputRef.current?.select();
      return;
    }

    setSaving(true);
    try {
      const saved = await onSave({ name, description: draftDescription.trim() });
      if (saved !== false) setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (deleteBusy) return;
    setDeleteBusy(true);
    try {
      await onDelete();
      setDeleting(false);
      setDeleteInput('');
    } catch {
      alert('No se pudo eliminar el portafolio. Intenta de nuevo.');
    } finally {
      setDeleteBusy(false);
    }
  };

  const recentTransactions = (overview?.recent_transactions || [])
    .filter((transaction) => {
      const oneYearAgo = new Date();
      oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
      return new Date(transaction.timestamp) >= oneYearAgo;
    })
    .slice(0, isMobile ? 2 : 3);

  return (
    <div className={`dash-panel ${entering ? 'enter' : ''}`} style={{ alignSelf: 'start' }}>
      <div className="card">
        {loading || !overview ? (
          <div className="muted">Cargando resumen…</div>
        ) : portfolio ? (
          <div className="grid" style={{ gap: 10 }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ position: 'relative', flex: '1 1 auto', minWidth: 0 }}>
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
                      title={portfolio.name}
                    >
                      {portfolio.name}
                    </h3>
                    <div className="row" style={{ gap: 2, alignItems: 'center', flex: 'none' }}>
                      <button
                        className="icon-inline-btn"
                        aria-label="Editar"
                        disabled={deleting}
                        onClick={openEditor}
                        title="Editar"
                      >
                        <EditIcon />
                      </button>
                      <button
                        className="icon-inline-btn"
                        aria-label="Eliminar"
                        disabled={editing}
                        title="Eliminar portafolio"
                        onClick={() => {
                          setDeleteInput('');
                          setDeleting(true);
                        }}
                      >
                        <DeleteIcon />
                      </button>
                    </div>
                  </div>
                </div>
                {portfolio.description && (
                  <div>
                    <span className="pill truncate" title={portfolio.description}>{portfolio.description}</span>
                  </div>
                )}
              </div>
              <div style={{ textAlign: 'right', flex: 'none' }}>
                <div className="muted" style={{ fontSize: 12 }}>Valor total</div>
                <MoneyValue
                  portfolio={portfolio}
                  field="total_value"
                  currency={currencyMode}
                  style={{ fontWeight: 700, fontSize: 20 }}
                />
              </div>
            </div>

            <div
              className="grid"
              style={{ gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0,1fr))', gap: isMobile ? 8 : 10 }}
            >
              <div className="card">
                <div className="muted">Efectivo</div>
                <MoneyValue portfolio={portfolio} field="cash_balance" currency={currencyMode} />
              </div>
              <div className="card">
                <div className="muted">Inversión</div>
                <MoneyValue portfolio={portfolio} field="current_investment_value" currency={currencyMode} />
              </div>
              <div className="card">
                <div className="muted">Activos</div>
                <div>{portfolio.holdings_count}</div>
              </div>
              <div className="card">
                <div className="muted">TWR anual</div>
                <div>{formatRatePercent(portfolio.twr_annualized)}</div>
              </div>
              <div className="card">
                <div className="muted">Hoy</div>
                <div>
                  {badgeMode === 'percent' ? (
                    <span className={hasValue(portfolio.day_change_pct) ? (Number(portfolio.day_change_pct) >= 0 ? 'up' : 'down') : ''}>
                      {hasValue(portfolio.day_change_pct) ? percent(portfolio.day_change_pct) : '-'}
                    </span>
                  ) : (
                    <SignedMoneyValue portfolio={portfolio} field="day_change_abs" currency={currencyMode} />
                  )}
                </div>
              </div>
              <div className="card">
                <div className="muted">Desde inicio</div>
                <div>
                  {badgeMode === 'percent' ? (
                    <span className={hasValue(portfolio.since_inception_pct) ? (Number(portfolio.since_inception_pct) >= 0 ? 'up' : 'down') : ''}>
                      {hasValue(portfolio.since_inception_pct) ? percent(portfolio.since_inception_pct) : '-'}
                    </span>
                  ) : (
                    <SignedMoneyValue portfolio={portfolio} field="since_inception_abs" currency={currencyMode} />
                  )}
                </div>
              </div>
            </div>

            <div className="grid" style={{ gridTemplateColumns: isMobile ? '1fr' : '1.25fr 0.75fr', gap: 10 }}>
              <div className="card">
                <div className="muted" style={{ marginBottom: 6 }}>Actividad reciente</div>
                <div className="table-wrap">
                  <table className="table table-transactions">
                    <thead>
                      <tr><th>Fecha</th><th>Tipo</th><th>Símbolo</th><th>Cant.</th><th>Monto</th></tr>
                    </thead>
                    <tbody>
                      {recentTransactions.map((transaction) => (
                        <tr key={transaction.id}>
                          <td>{formatDateDDMM(transaction.timestamp) || '-'}</td>
                          <td>{transaction.transaction_type_display || '-'}</td>
                          <td>{transaction.stock_symbol || '-'}</td>
                          <td>{transaction.quantity ?? '-'}</td>
                          <td>
                            {transaction.amount != null
                              ? `${CURRENCY_PREFIX[transaction.cash_currency] ?? ''}${NUMBER_FORMAT.format(Number(transaction.amount))}`
                              : '-'}
                          </td>
                        </tr>
                      ))}
                      {!overview.recent_transactions?.length && (
                        <tr><td colSpan="5" style={{ textAlign: 'center', color: 'var(--muted)', padding: '16px' }}>-</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="card">
                <div className="muted" style={{ marginBottom: 6 }}>Composición</div>
                <div className="table-wrap">
                  <table className="table table-composition">
                    <thead><tr><th>Símbolo</th><th>Peso</th></tr></thead>
                    <tbody>
                      {overview.composition?.length ? (
                        overview.composition.slice(0, isMobile ? 2 : 3).map((holding) => (
                          <tr key={holding.symbol}>
                            <td>{holding.symbol}</td>
                            <td>{holding.weight_pct}%</td>
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

            <div style={{ textAlign: 'center' }}>
              <Link to={`/app/portfolios/${portfolio.id}`} className="btn sm primary">Ver detalle</Link>
            </div>
          </div>
        ) : (
          <div className="muted">Selecciona un portafolio</div>
        )}
      </div>

      {editing && createPortal(
        <div style={modalBackdropStyle}>
          <div className="card" style={modalCardStyle} onClick={(event) => event.stopPropagation()}>
            <form className="grid" style={{ gap: 8 }} onSubmit={submitEdit}>
              <div className="grid" style={{ gap: 6 }}>
                <label className="muted" htmlFor="pf-name">Nombre</label>
                <input
                  id="pf-name"
                  ref={nameInputRef}
                  className="input"
                  value={draftName}
                  maxLength={100}
                  onChange={(event) => setDraftName(event.target.value)}
                  autoFocus
                  style={{ fontSize: 12, padding: '6px 8px' }}
                />
              </div>
              <div className="grid" style={{ gap: 6 }}>
                <label className="muted" htmlFor="pf-desc">Descripción</label>
                <textarea
                  id="pf-desc"
                  className="input"
                  rows={6}
                  value={draftDescription}
                  style={{ fontSize: 12, padding: '6px 8px' }}
                  onChange={(event) => setDraftDescription(event.target.value)}
                />
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                <button type="button" className="btn xs ghost" onClick={() => setEditing(false)}>✕</button>
                <button className="btn xs primary" type="submit" disabled={saving || !draftName.trim()}>
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body,
      )}

      {deleting && createPortal(
        <div style={modalBackdropStyle}>
          <div className="card" style={modalCardStyle} onClick={(event) => event.stopPropagation()}>
            <div className="grid" style={{ gap: 8 }}>
              <h4 style={{ margin: 0 }}>Eliminar portafolio</h4>
              <p className="muted" style={{ margin: 0 }}>
                Para eliminar tu portafolio, escribe exactamente &quot;eliminar {portfolio.name}&quot;.
              </p>
              <input
                className="input"
                placeholder={`eliminar ${portfolio.name}`}
                value={deleteInput}
                onChange={(event) => setDeleteInput(event.target.value)}
                autoFocus
              />
              <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                <button
                  type="button"
                  className="btn xs ghost"
                  onClick={() => {
                    setDeleting(false);
                    setDeleteInput('');
                  }}
                >
                  ✕
                </button>
                <button
                  type="button"
                  className="btn xs danger"
                  disabled={deleteBusy || normalizeText(deleteInput) !== normalizeText(`eliminar ${portfolio.name}`)}
                  onClick={confirmDelete}
                >
                  {deleteBusy ? 'Eliminando…' : 'Eliminar'}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
};

export default PortfolioOverview;
