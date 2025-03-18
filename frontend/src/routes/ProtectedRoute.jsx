import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { verifyAuth } from '../services/api';

const ProtectedRoute = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    let isMounted = true;
    
    verifyAuth()
      .then(auth => isMounted && setIsAuthenticated(auth))
      .catch(() => isMounted && setIsAuthenticated(false));

    return () => { isMounted = false; };
  }, []);

  if (isAuthenticated === null) return <div>Checking authentication...</div>;
  
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;