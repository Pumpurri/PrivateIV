import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getPortfolioPerformance } from '../services/api';
import { formatCurrency, formatPercent } from '../utils/format';

const PortfolioPerformance = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const d = await getPortfolioPerformance(id);
        setData(d);
      } catch (e) {
        setError('Failed to load performance');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) return <div className="muted">Cargando…</div>;
  if (error) return <div className="down">{error}</div>;
  if (!data) return <div>Sin datos</div>;

  return (
    <div>
      <h2>Rendimiento</h2>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0,1fr))' }}>
        <div className="card"><div className="muted">Depósitos totales</div><div style={{ fontSize: 20 }}>{formatCurrency(data.total_deposits)}</div></div>
        <div className="card"><div className="muted">Retiros totales</div><div style={{ fontSize: 20 }}>{formatCurrency(data.total_withdrawals)}</div></div>
        <div className="card"><div className="muted">Retorno ponderado por tiempo</div><div style={{ fontSize: 20 }}>{data.time_weighted_return}</div></div>
        <div className="card"><div className="muted">Retorno total</div><div style={{ fontSize: 20 }}>{formatPercent(data.total_return_percentage)}</div></div>
      </div>
      <div className="muted" style={{ marginTop: 8 }}>Última actualización: {new Date(data.last_updated).toLocaleString()}</div>
      <p className="muted">Podemos añadir gráficas (p. ej., Recharts) cuando haya una serie temporal.</p>
    </div>
  );
};

export default PortfolioPerformance;
