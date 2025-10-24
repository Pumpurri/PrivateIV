import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';

const Landing = () => {
  const [scrolled, setScrolled] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [isVisible, setIsVisible] = useState({});
  const [mockupValue, setMockupValue] = useState(0);
  const [mockupReturn, setMockupReturn] = useState(0);
  const mockupAnimatedRef = useRef(false);
  // Row-by-row staged animation state
  const [currentRow, setCurrentRow] = useState(-1);
  const [symbolReveal, setSymbolReveal] = useState(-1); // last symbol index revealed
  const [detailsReveal, setDetailsReveal] = useState(0); // count of fully revealed rows
  const [rowAnimQty, setRowAnimQty] = useState(0);
  const [rowAnimPrice, setRowAnimPrice] = useState(0);
  const [rowAnimPnl, setRowAnimPnl] = useState(0);
  const [rowAnimating, setRowAnimating] = useState(false);

  // Demo rows tuned so totals aggregate to ~S/ 25,430.50 and ~3.8%
  const demoRows = [
    { symbol: 'ALICORC1', qty: 1200, price: 7.25, pnl: 240.0 },     // 8,700.00
    { symbol: 'BCP',      qty: 1000, price: 6.10, pnl: 450.0 },     // 6,100.00
    { symbol: 'VOLCABC1', qty: 15000, price: 0.47, pnl: 200.0 },    // 7,050.00
    { symbol: 'CREDITC1', qty: 700,  price: 5.115, pnl: 80.5  },    // 3,580.50
  ];
  

  const formatCurrency = (v) => `S/ ${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // Show floating CTA after scrolling down
  useEffect(() => {
    const handleScroll = () => {
      const y = window.scrollY || document.documentElement.scrollTop || 0;
      setScrolled(y > 2);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // (Green blob removed per request)

  // Intersection observer for animations
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(prev => ({ ...prev, [entry.target.id]: true }));
          }
        });
      },
      { threshold: 0.1 }
    );

    // Observe elements with animation classes
    const animatedElements = document.querySelectorAll('[data-animate]');
    animatedElements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  // Per-row sequence: symbol -> animate qty/price/pnl -> next row; totals animate alongside
  useEffect(() => {
    if (!isVisible['mockup']) return;
    if (mockupAnimatedRef.current) return;
    mockupAnimatedRef.current = true;
    setCurrentRow(0);
    setSymbolReveal(-1);
    setDetailsReveal(0);
    setMockupValue(0);
    setMockupReturn(0);
    setRowAnimating(false);

    const revealNext = (idx, prevTotal, prevPnl) => {
      if (idx >= demoRows.length) return; // done
      setCurrentRow(idx);
      // Stage 1: reveal symbol immediately with a short lead time
      setSymbolReveal(idx);
      // Stage 2: after symbol reveal completes, animate numbers simultaneously
      setTimeout(() => {
        setRowAnimating(true);
        const row = demoRows[idx];
        const rowTotal = row.qty * row.price;
        const targetTotal = prevTotal + rowTotal;
        const targetPnl = prevPnl + row.pnl;
        const targetRet = targetTotal > 0 ? (targetPnl / targetTotal) * 100 : 0;

        const startVal = prevTotal;
        const startRet = prevTotal > 0 ? (prevPnl / prevTotal) * 100 : 0;
        const start = performance.now();
        const duration = 650;

        const tick = (now) => {
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          // Animate row numbers
          setRowAnimQty(Math.round(row.qty * eased));
          setRowAnimPrice(row.price * eased);
          setRowAnimPnl(row.pnl * eased);
          // Animate totals
          setMockupValue(startVal + (rowTotal * eased));
          const curTotal = startVal + (rowTotal * eased);
          const curPnl = prevPnl + (row.pnl * eased);
          setMockupReturn(curTotal > 0 ? (curPnl / curTotal) * 100 : 0);

          if (t < 1) {
            requestAnimationFrame(tick);
          } else {
            // Row complete
            setDetailsReveal(idx + 1);
            setRowAnimating(false);
            // Small settle ease to exact targets
            const settleStart = performance.now();
            const settleDur = 250;
            const settleTick = (now2) => {
              const tt = Math.min(1, (now2 - settleStart) / settleDur);
              const ee = 1 - Math.pow(1 - tt, 3);
              setMockupValue(startVal + rowTotal * ee);
              setMockupReturn(startRet + (targetRet - startRet) * ee);
              if (tt < 1) requestAnimationFrame(settleTick);
            };
            requestAnimationFrame(settleTick);
            // Next row
            setTimeout(() => revealNext(idx + 1, targetTotal, targetPnl), 120);
          }
        };
        requestAnimationFrame(tick);
      }, 260);
    };

    revealNext(0, 0, 0);

    return () => {
      mockupAnimatedRef.current = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isVisible['mockup']]);

  

  return (
    <div className="landing-root min-h-screen">
      {/* Shared header is rendered by SiteLayout */}

      {/* Hero */}
      <section className="hero">
        <div className="container">
          <div className="grid-bg" aria-hidden="true" />
          <div className="flex flex-col md:flex-row items-center md:items-start gap-8 md:gap-10">
            <div
              data-animate="fade-up"
              id="hero-content"
              className={`w-full md:flex-1 max-w-3xl md:max-w-xl lg:max-w-2xl mx-auto md:mx-0 text-center md:text-left py-10 md:py-16 ${isVisible['hero-content'] ? 'animate-fade-up' : ''}`}
            >
              <div className="transform-gpu -translate-y-2 md:-translate-y-3">
                <span className="pill">Suite de Simulación de Inversión</span>
                <h1 className="hero-title neon text-4xl md:text-5xl lg:text-6xl leading-tight">Simula tus inversiones en la BVL</h1>
                <p className="hero-sub text-lg md:text-xl mt-3 md:mt-4">El simulador es GRATIS para unirse y usarlo</p>
                <div className="row justify-center md:justify-start" style={{ gap: 12, marginTop: 12 }}>
                  <Link className="btn primary transform-gpu scale-105 md:scale-110" to="/register">Regístrate</Link>
                </div>
              </div>
              
            </div>
            {/* Mockup ilustrativo */}
            <div
              id="mockup"
              data-animate="slide-up"
              className={`card mockup w-full md:flex-1 md:w-auto max-w-lg md:max-w-2xl lg:max-w-3xl mx-auto md:mx-0 p-4 md:p-8 ${isVisible['mockup'] ? 'animate-slide-up' : ''}`}
              style={{ animationDelay: '0.18s' }}
            >
              <div className="muted text-sm md:text-base" style={{ marginBottom: 8 }}>Vista previa de portafolio (ejemplo)</div>
              <div className="mockup-grid">
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Valor total</div>
                  <div className="metric-value text-2xl md:text-3xl">{formatCurrency(mockupValue)}</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Retorno</div>
                  <div className="metric-value text-green-500 flex items-center gap-1 text-2xl md:text-3xl">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="w-5 h-5">
                      <path d="M7 17L17 7" />
                      <path d="M7 7h10v10" />
                    </svg>
                    <span>+{mockupReturn.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
              <div className="mockup-table text-sm md:text-base">
                <div className="row head"><span>Símbolo</span><span>Cant.</span><span>Precio</span><span>P&amp;L</span></div>
                {demoRows.map((r, i) => (
                  <div
                    className={`row ${i <= currentRow ? 'expanded' : 'collapsed'} ${i === currentRow && i === symbolReveal ? 'row-appear' : ''}`}
                    key={r.symbol}
                  >
                    <span className={`symbol ${i === symbolReveal && i >= detailsReveal ? 'pop slide-in' : ''}`}>
                      {i <= symbolReveal ? r.symbol : <span className="muted">—</span>}
                    </span>
                    <span>
                      {i < detailsReveal
                        ? r.qty
                        : i === currentRow
                          ? (rowAnimating ? rowAnimQty : '')
                          : ''}
                    </span>
                    <span>
                      {i < detailsReveal
                        ? `S/ ${r.price.toFixed(3).replace(/0+$/,'').replace(/\.$/,'')}`
                        : i === currentRow
                          ? (rowAnimating ? `S/ ${rowAnimPrice.toFixed(2)}` : '')
                          : ''}
                    </span>
                    <span className={(i < detailsReveal ? r.pnl : (i === currentRow ? rowAnimPnl : 0)) >= 0 ? 'up' : 'down'}>
                      {i < detailsReveal
                        ? `${r.pnl >= 0 ? '+' : '−'}S/ ${Math.abs(r.pnl).toFixed(2)}`
                        : i === currentRow
                          ? (rowAnimating ? `${rowAnimPnl >= 0 ? '+' : '−'}S/ ${Math.abs(rowAnimPnl).toFixed(2)}` : '')
                          : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        {/* decorative blobs */}
        <div className="blob a" />
      </section>

      {/* Features */}
      <section id="features" className="features">
        <div className="container">
          <div className="grid grid-cols-1 md:grid-cols-3 items-stretch gap-6">
            <div data-animate="slide-up" id="feature-1" className={`card feature flex flex-col items-center text-center gap-2 p-4 md:p-5 ${isVisible['feature-1'] ? 'animate-slide-up' : ''}`} style={{ animationDelay: '0.1s' }}>
              <div className="row" style={{ alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span className="feature-icon transform-gpu scale-110 md:scale-125" aria-hidden="true">
                  <svg viewBox="0 0 24 24" role="img" aria-label="">
                    <path d="M5 20V10" />
                    <path d="M12 20V6" />
                    <path d="M19 20V3" />
                  </svg>
                </span>
                <h3 className="text-lg md:text-xl" style={{ margin: 0 }}>Estadísticas de tu portafolio</h3>
              </div>
              <p className="muted text-sm md:text-base">TWR, P&amp;L y evolución histórica para entender tu desempeño con claridad.</p>
            </div>
            <div data-animate="slide-up" id="feature-2" className={`card feature flex flex-col items-center text-center gap-2 p-4 md:p-5 ${isVisible['feature-2'] ? 'animate-slide-up' : ''}`} style={{ animationDelay: '0.2s' }}>
              <div className="row" style={{ alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span className="feature-icon transform-gpu scale-110 md:scale-125" aria-hidden="true">
                  <svg viewBox="0 0 24 24" role="img" aria-label="">
                    <circle cx="12" cy="12" r="8" />
                    <path d="M12 8v4l3 2" />
                  </svg>
                </span>
                <h3 className="text-lg md:text-xl" style={{ margin: 0 }}>Precios en Tiempo Real</h3>
              </div>
              <p className="muted text-sm md:text-base">Precios actualizados y respaldo histórico para valorar tu portafolio con fidelidad.</p>
            </div>
            <div data-animate="slide-up" id="feature-3" className={`card feature flex flex-col items-center text-center gap-2 p-4 md:p-5 ${isVisible['feature-3'] ? 'animate-slide-up' : ''}`} style={{ animationDelay: '0.3s', width: 402, height: 108 }}>
              <div className="row" style={{ alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span className="feature-icon transform-gpu scale-110 md:scale-125" aria-hidden="true">
                  <svg viewBox="0 0 24 24" role="img" aria-label="">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M5 10a7 7 0 0 1 7-5" />
                    <path d="M12 5l-2-1" />
                    <path d="M12 5l1.5-2" />
                    <path d="M19 14a7 7 0 0 1-7 5" />
                    <path d="M12 19l2 1" />
                    <path d="M12 19l-1.5 2" />
                  </svg>
                </span>
                <h3 className="text-lg md:text-xl" style={{ margin: 0 }}>Flujos Realistas</h3>
              </div>
              <p className="muted text-sm md:text-base">Deposita fondos, realiza compras y vende activos con un flujo igual al de la vida real.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div
          id="footer-top"
          data-animate="fade-up"
          className={`container row ${isVisible['footer-top'] ? 'animate-fade-up' : ''}`}
          style={{ justifyContent: 'space-between' }}
        >
          <span className="muted">© {new Date().getFullYear()} Simula</span>
          <span />
        </div>
        <div
          id="footer-bottom"
          data-animate="fade-up"
          className={`container ${isVisible['footer-bottom'] ? 'animate-fade-up' : ''}`}
          style={{ marginTop: 8 }}
        >
          <p className="disclaimer">Simulador educativo, no es una recomendación de inversión.</p>
          <p className="disclaimer" style={{ marginTop: 6 }}>
            ¿Tienes ideas o comentarios?{' '}
            <a href="https://forms.gle/V2SPgfMPHMWqz38G6" target="_blank" rel="noopener noreferrer">Manda feedback</a>
          </p>
        </div>
      </footer>

    </div>
  );
};

export default Landing;
