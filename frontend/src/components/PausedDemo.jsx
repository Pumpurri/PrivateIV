import { Link } from 'react-router-dom';

export default function PausedDemo() {
  return (
    <main className="app-page" style={{ minHeight: 'calc(100vh - 80px)', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div className="card" style={{ width: '100%', maxWidth: 560, padding: 32, textAlign: 'center' }}>
        <h1 style={{ marginTop: 0 }}>La demo está en pausa</h1>
        <p className="muted">El servidor está apagado por ahora, así que no se pueden crear cuentas ni iniciar sesión. Puedes explorar el código y las capturas del proyecto en GitHub.</p>
        <div className="row" style={{ justifyContent: 'center', flexWrap: 'wrap', gap: 12, marginTop: 24 }}>
          <Link className="btn" to="/">Volver al inicio</Link>
          <a className="btn primary" href="https://github.com/Pumpurri/PrivateIV">Ver el proyecto</a>
        </div>
      </div>
    </main>
  );
}
