import React, { useEffect, useMemo, useState } from 'react';
import { createTransaction, getPortfolios, getTransactions } from '../services/api';
import { useStockPrices } from '../contexts/StockPriceContext';
import { formatCurrency } from '../utils/format';

const Transactions = () => {
  const [portfolios, setPortfolios] = useState([]);
  const [selected, setSelected] = useState('');
  const [list, setList] = useState({ results: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ type: 'DEPOSIT', stock: '', quantity: '', amount: '' });
  const [submitting, setSubmitting] = useState(false);

  const { stocks } = useStockPrices();

  const isTrade = useMemo(() => form.type === 'BUY' || form.type === 'SELL', [form.type]);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const ps = await getPortfolios();
      const pItems = ps?.results ?? ps;
      setPortfolios(pItems);
      const defaultId = (pItems.find(p => p.is_default) || pItems[0])?.id;
      const portfolioId = selected || defaultId;
      setSelected(portfolioId || '');
      if (portfolioId) {
        const data = await getTransactions({ portfolio: portfolioId });
        setList(data);
      } else {
        setList({ results: [], count: 0 });
      }
    } catch (e) {
      setError('No se pudieron cargar las transacciones');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);


  useEffect(() => {
    const rel = async () => {
      if (!selected) return;
      try {
        const data = await getTransactions({ portfolio: selected });
        setList(data);
      } catch (_) {}
    };
    rel();
  }, [selected]);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const payload = { transaction_type: form.type, portfolio_id: selected ? Number(selected) : undefined };
      if (isTrade) {
        payload.stock = form.stock ? Number(form.stock) : undefined;
        payload.quantity = form.quantity ? Number(form.quantity) : undefined;
      } else {
        payload.amount = form.amount ? form.amount : undefined;
      }
      await createTransaction(payload);
      setForm({ type: 'DEPOSIT', stock: '', quantity: '', amount: '' });
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || 'No se pudo enviar la transacción');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="muted">Cargando…</div>;

  return (
    <div>
      <h2>Transacciones</h2>
      <div className="row">
        <label>
          Portafolio:
          <select className="select" value={selected} onChange={e => setSelected(e.target.value)} style={{ marginLeft: 8 }}>
            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}{p.is_default ? ' (predeterminado)' : ''}</option>)}
          </select>
        </label>
      </div>

      <form onSubmit={submit} className="grid" style={{ maxWidth: 640, marginTop: 16 }}>
        <label>
          Tipo
          <select className="select" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
            <option value="DEPOSIT">Depósito</option>
            <option value="WITHDRAWAL">Retiro</option>
            <option value="BUY">Compra</option>
            <option value="SELL">Venta</option>
          </select>
        </label>

        {isTrade ? (
          <>
            <label>
              Acción
              <select className="select" value={form.stock} onChange={e => setForm({ ...form, stock: e.target.value })} required={isTrade}>
                <option value="">Selecciona una acción…</option>
                {stocks.map(s => (
                  <option key={s.id} value={s.id}>{s.symbol} — {s.name}</option>
                ))}
              </select>
            </label>
            <input className="input" type="number" placeholder="Cantidad" value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} required={isTrade} />
          </>
        ) : (
          <input className="input" type="number" step="0.01" placeholder="Monto" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} required />
        )}

        <button className="btn primary" disabled={submitting}>{submitting ? 'Enviando…' : 'Enviar'}</button>
      </form>
      {error && <p className="down">{error}</p>}

      <h3 style={{ marginTop: 24 }}>History</h3>
      {list.results?.length === 0 ? (
        <p>Aún no hay transacciones.</p>
      ) : (
        <table className="table">
          <thead>
            <tr style={{ textAlign: 'left' }}>
              <th>Fecha</th>
              <th>Tipo</th>
              <th>Símbolo</th>
              <th>Cant.</th>
              <th>Precio</th>
              <th>Monto</th>
            </tr>
          </thead>
          <tbody>
            {list.results.map(t => (
              <tr key={t.id}>
                <td>{new Date(t.timestamp).toLocaleString()}</td>
                <td>{t.transaction_type_display}</td>
                <td>{t.stock_symbol || '-'}</td>
                <td>{t.quantity || '-'}</td>
                <td>{t.executed_price ? formatCurrency(t.executed_price) : '-'}</td>
                <td>{t.amount ? formatCurrency(t.amount) : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default Transactions;
