import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { verifyAuth } from '../services/api';

// Helper to read cookies
function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  // Initialize from sessionStorage to survive remounts (Strict Mode in dev)
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    const stored = sessionStorage.getItem('isAuthenticated');
    return stored === 'true' ? true : stored === 'false' ? false : null;
  });
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);
  const isCheckingRef = useRef(false);

  // Persist auth state to sessionStorage
  useEffect(() => {
    if (isAuthenticated !== null) {
      sessionStorage.setItem('isAuthenticated', String(isAuthenticated));
    }
  }, [isAuthenticated]);

  // Check auth on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = useCallback(async () => {
    // Prevent duplicate simultaneous checks
    if (isCheckingRef.current) return;

    // If already authenticated via login(), don't recheck
    if (isAuthenticated === true) {
      setIsLoading(false);
      return;
    }

    isCheckingRef.current = true;
    setIsLoading(true);

    try {
      // Fast check: Do we have a session cookie?
      const hasSessionCookie = getCookie('sessionid');

      if (!hasSessionCookie) {
        // No session cookie = definitely not logged in
        // Skip API call for better performance
        setIsAuthenticated(false);
        setIsLoading(false);
        isCheckingRef.current = false;
        return;
      }

      // Has session cookie = verify with backend
      const authenticated = await verifyAuth();
      setIsAuthenticated(authenticated);
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
      isCheckingRef.current = false;
    }
  }, [isAuthenticated]);

  // Call this after successful login/register
  const login = useCallback((userData = null) => {
    setIsAuthenticated(true);
    setUser(userData);
  }, []);

  // Call this after logout
  const logout = useCallback(() => {
    setIsAuthenticated(false);
    setUser(null);
    sessionStorage.removeItem('isAuthenticated');
  }, []);

  // Recheck auth (useful for session expiry scenarios)
  const recheckAuth = useCallback(async () => {
    return checkAuth();
  }, [checkAuth]);

  const value = {
    isAuthenticated,
    isLoading,
    user,
    login,
    logout,
    recheckAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
