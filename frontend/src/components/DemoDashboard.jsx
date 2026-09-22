import { Link } from 'react-router-dom';
import '../styles/DemoDashboard.css';

const positions = [
  { symbol: 'ALICORC1', name: 'Alicorp', shares: '1,200', price: 'S/ 7.25', value: 'S/ 8,700.00', change: '+S/ 240.00' },
  { symbol: 'BCP', name: 'Credicorp', shares: '1,000', price: 'S/ 6.10', value: 'S/ 6,100.00', change: '+S/ 450.00' },
  { symbol: 'VOLCABC1', name: 'Volcan', shares: '15,000', price: 'S/ 0.47', value: 'S/ 7,050.00', change: '+S/ 200.00' },
  { symbol: 'CREDITC1', name: 'Crédito', shares: '700', price: 'S/ 5.115', value: 'S/ 3,580.50', change: '+S/ 80.50' },
];

export default function DemoDashboard() {
  return (
    <main className="preview-page">
      <div className="preview-shell">
        <div className="preview-heading">
          <div>
            <p className="preview-eyebrow">BOLSA<span>SIM</span> / VISTA PREVIA</p>
            <h1>Tu portafolio, de un vistazo.</h1>
            <p className="muted">Una ilustración de los balances, posiciones y rendimiento que ofrece la plataforma.</p>
          </div>
          <span className="preview-badge">Datos ficticios · Solo lectura</span>
        </div>

        <div className="preview-toolbar">
          <strong>Portafolio de ejemplo</strong>
          <span>Moneda de visualización: PEN</span>
        </div>

        <section className="preview-metrics" aria-label="Resumen del portafolio de ejemplo">
          <div className="preview-card preview-primary">
            <span>Valor total</span>
            <strong>S/ 30,080.50</strong>
            <small>+3.8% rendimiento estimado</small>
          </div>
          <div className="preview-card">
            <span>Posiciones</span>
            <strong>S/ 25,430.50</strong>
            <small>4 activos simulados</small>
          </div>
          <div className="preview-card">
            <span>Efectivo</span>
            <strong>S/ 4,650.00</strong>
            <small>S/ 2,400.00 + US$ 600.00*</small>
          </div>
        </section>

        <div className="preview-grid">
          <section className="preview-card preview-chart" aria-label="Gráfico ilustrativo de evolución del portafolio">
            <div className="preview-section-title">
              <div>
                <h2>Evolución del portafolio</h2>
                <p>Valor estimado en PEN</p>
              </div>
              <span>Últimos 6 meses</span>
            </div>
            <svg viewBox="0 0 680 220" role="img" aria-label="Gráfico de muestra con tendencia ascendente del valor del portafolio">
              <defs>
                <linearGradient id="preview-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#29c57a" stopOpacity=".25" />
                  <stop offset="100%" stopColor="#29c57a" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0 175 L90 159 L170 170 L252 128 L333 142 L417 99 L500 111 L580 62 L680 40 L680 220 L0 220Z" fill="url(#preview-fill)" />
              <path d="M0 175 L90 159 L170 170 L252 128 L333 142 L417 99 L500 111 L580 62 L680 40" fill="none" stroke="#31d68b" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="680" cy="40" r="7" fill="#31d68b" />
            </svg>
            <div className="preview-chart-labels"><span>ABR</span><span>MAY</span><span>JUN</span><span>JUL</span><span>AGO</span><span>SEP</span></div>
          </section>

          <section className="preview-card preview-wallets">
            <div className="preview-section-title"><h2>Balances</h2></div>
            <div><span>Sol peruano</span><strong>S/ 2,400.00</strong></div>
            <div><span>Dólar estadounidense</span><strong>US$ 600.00</strong></div>
            <p>* Conversión ilustrativa a 3.75 PEN/USD. No son tipos de cambio actuales.</p>
          </section>
        </div>

        <section className="preview-card preview-positions">
          <div className="preview-section-title"><h2>Posiciones</h2><span>Ejemplo ilustrativo</span></div>
          <p className="preview-scroll-hint">Desliza para ver todas las columnas <span aria-hidden="true">→</span></p>
          <div className="preview-table-wrap" tabIndex="0" aria-label="Tabla de posiciones; desliza horizontalmente para ver todas las columnas">
            <table>
              <thead><tr><th>Activo</th><th>Cantidad</th><th>Precio</th><th>Valor</th><th>G/P</th></tr></thead>
              <tbody>
                {positions.map((position) => (
                  <tr key={position.symbol}>
                    <td><strong>{position.symbol}</strong><small>{position.name}</small></td>
                    <td>{position.shares}</td><td>{position.price}</td><td>{position.value}</td><td className="preview-positive">{position.change}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <p className="preview-disclaimer">Esta vista usa datos ficticios. La demo interactiva y las cotizaciones están pausadas.</p>
        <div className="preview-links"><Link className="btn" to="/">Volver al inicio</Link><a className="btn primary" href="https://github.com/Pumpurri/PrivateIV">Explorar el código</a></div>
      </div>
    </main>
  );
}
