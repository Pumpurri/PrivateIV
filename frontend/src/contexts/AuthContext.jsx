import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { verifyAuth } from '../services/api';
import { DEMO_PAUSED } from '../config/demo';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(DEMO_PAUSED ? false : null);
  const [isLoading, setIsLoading] = useState(!DEMO_PAUSED);
  const [user, setUser] = useState(null);
  const authCheckPromiseRef = useRef(null);
  const authStateVersionRef = useRef(0);

  const checkAuth = useCallback(async () => {
    if (DEMO_PAUSED) return false;
    if (authCheckPromiseRef.current) {
      return authCheckPromiseRef.current;
    }

    authCheckPromiseRef.current = (async () => {
      const authStateVersion = authStateVersionRef.current;
      setIsLoading(true);

      try {
        const result = await verifyAuth();

        if (authStateVersionRef.current !== authStateVersion) {
          return result.authenticated;
        }

        setIsAuthenticated(result.authenticated);
        setUser(result.authenticated ? (result.user ?? null) : null);
        return result.authenticated;
      } catch (error) {
        console.error('Auth check failed:', error);

        if (authStateVersionRef.current === authStateVersion) {
          setIsAuthenticated(false);
          setUser(null);
        }

        return false;
      } finally {
        if (authStateVersionRef.current === authStateVersion) {
          setIsLoading(false);
        }
        authCheckPromiseRef.current = null;
      }
    })();

    return authCheckPromiseRef.current;
  }, []);

  // Check auth on mount
  useEffect(() => {
    if (!DEMO_PAUSED) void checkAuth();
  }, [checkAuth]);

  // Call this after successful login/register
  const login = useCallback((userData = null) => {
    authStateVersionRef.current += 1;
    setIsAuthenticated(true);
    setUser(userData);
    setIsLoading(false);
  }, []);

  // Call this after logout
  const logout = useCallback(() => {
    authStateVersionRef.current += 1;
    setIsAuthenticated(false);
    setUser(null);
    setIsLoading(false);
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

// The hook intentionally lives alongside its provider for a single import path.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
