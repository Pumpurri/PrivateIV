import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import apiClient from '../services/axios';
import { clearCSRFToken } from '../services/axios';
import { useAuth } from '../contexts/AuthContext';

const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout: authLogout } = useAuth();

  const handleBrandClick = (e) => {
    e.preventDefault();
    const targetPath = isAuthenticated ? '/dashboard' : '/';

    if (location.pathname === targetPath) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      navigate(targetPath);
    }
  };

  const onBrandKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleBrandClick(e);
    }
  };

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const isAuthPage = location.pathname === '/register' || location.pathname === '/login';

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout/');
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      // Always update client state, even if API call fails
      clearCSRFToken(); // Clear CSRF token on logout
      authLogout();
      // Use window.location for clean logout (full page reload)
      window.location.href = '/';
    }
  };

  return (
    <header className="landing-nav">
      <div className="container row justify-between">
        <a
          href="/"
          className="brand brand-clickable"
          role="button"
          tabIndex={0}
          onClick={handleBrandClick}
          onKeyDown={onBrandKey}
        >
          <span className="brand-text">Simula</span> <span className="brand-badge">BETA</span>
        </a>
        {!isAuthPage && !isAuthenticated && (
          <nav className="row">
            <Link className="btn primary" to="/register">Regístrate</Link>
            <Link className="nav-link" to="/login">Iniciar sesión</Link>
          </nav>
        )}
        {isAuthenticated && (
          <div className="row" ref={menuRef} style={{ position: 'relative' }}>
            <button className="btn" onClick={() => setMenuOpen(v => !v)} aria-haspopup="menu" aria-expanded={menuOpen}>
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="3" />
              </svg>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {menuOpen && (
              <div className="card" role="menu" style={{ position: 'absolute', right: 0, top: 'calc(100% + 8px)', minWidth: 180, padding: 8 }}>
                <Link className="nav-link" to="/dashboard" role="menuitem" onClick={() => setMenuOpen(false)}>Avatar</Link>
                <Link className="nav-link" to="#" role="menuitem" onClick={() => setMenuOpen(false)}>Settings</Link>
                <button className="btn ghost" role="menuitem" onClick={handleLogout}>Logout</button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
