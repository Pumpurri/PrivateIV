import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { logoutUser } from '../services/api';
import { clearCSRFToken } from '../services/axios';
import { useAuth } from '../contexts/AuthContext';

const AppLayout = () => {
  const navigate = useNavigate();
  const { logout: authLogout } = useAuth();

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (e) {
      console.error(e);
    } finally {
      clearCSRFToken();
      authLogout();
      navigate('/login');
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h3>Consola de Inversión</h3>
        <nav className="nav">
          <NavLink to="/dashboard" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>Panel</NavLink>
          <NavLink to="/app/portfolios" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>Portafolios</NavLink>
          <NavLink to="/app/transactions" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>Transacciones</NavLink>
        </nav>
        <div style={{ marginTop: 16 }}>
          <button className="btn" onClick={handleLogout}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="main">
        <div className="container">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AppLayout;
