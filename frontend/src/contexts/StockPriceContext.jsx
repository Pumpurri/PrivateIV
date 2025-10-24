import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { getAllStocks, getStocksLastRefresh } from '../services/api';

const StockPriceContext = createContext();

export const useStockPrices = () => {
  const context = useContext(StockPriceContext);
  if (!context) {
    throw new Error('useStockPrices must be used within a StockPriceProvider');
  }
  return context;
};

export const StockPriceProvider = ({ children }) => {
  const CACHE_DURATION = 14 * 60 * 1000; // 14 minutes
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetch, setLastFetch] = useState(0);
  const [lastBackendRefresh, setLastBackendRefresh] = useState(null);
  const fetchingRef = useRef(false);
  const initialFetchRef = useRef(false);
  const stocksRef = useRef([]);
  const lastBackendRefreshRef = useRef(null);

  useEffect(() => {
    stocksRef.current = stocks;
  }, [stocks]);

  useEffect(() => {
    lastBackendRefreshRef.current = lastBackendRefresh;
  }, [lastBackendRefresh]);

  const fetchStocks = useCallback(async (force = false) => {
    const now = Date.now();
    const cacheAge = now - lastFetch;

    if (!force && cacheAge < CACHE_DURATION && stocksRef.current.length > 0) {
      return;
    }
    if (fetchingRef.current) {
      return;
    }
    fetchingRef.current = true;

    try {
      setLoading(true);
      setError(null);
      const { stocks: list = [], lastRefreshedAt } = await getAllStocks();
      const normalized = Array.isArray(list) ? list : [];
      stocksRef.current = normalized;
      setStocks(normalized);
      setLastFetch(now);
      if (lastRefreshedAt) {
        setLastBackendRefresh(lastRefreshedAt);
      }
    } catch (err) {
      setError(err.message);
      console.error('Failed to fetch stocks:', err);
    } finally {
      fetchingRef.current = false;
      setLoading(false);
    }
  }, [lastFetch]);

  // Initial fetch
  useEffect(() => {
    if (initialFetchRef.current) return;
    initialFetchRef.current = true;
    fetchStocks(true);
  }, [fetchStocks]);

  // Cache duration fallback refresh
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const cacheAge = now - lastFetch;
      if (cacheAge > CACHE_DURATION) {
        fetchStocks();
      }
    }, 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchStocks, lastFetch]);

  // Poll backend refresh timestamp to stay aligned with ingest cadence
  useEffect(() => {
    let cancelled = false;

    const checkRefresh = async () => {
      try {
        const data = await getStocksLastRefresh();
        if (cancelled) return;
        const serverTs = data?.last_refreshed_at;
        if (!serverTs) return;
        if (!lastBackendRefreshRef.current) {
          setLastBackendRefresh(serverTs);
          return;
        }
        const serverDate = Date.parse(serverTs);
        const localDate = Date.parse(lastBackendRefreshRef.current);
        if (Number.isFinite(serverDate) && Number.isFinite(localDate) && serverDate > localDate) {
          await fetchStocks(true);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to poll stock refresh timestamp:', err);
        }
      }
    };

    checkRefresh();
    const poll = setInterval(checkRefresh, 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [fetchStocks]);

  const findStock = (symbol) => {
    return stocks.find(stock => stock.symbol === symbol);
  };

  const searchStocks = (query) => {
    if (!query) return [];
    const q = query.trim().toLowerCase();
    return stocks.filter(stock => {
      const sym = (stock.symbol || '').toLowerCase();
      const name = (stock.name || '').toLowerCase();
      return sym.includes(q) || name.includes(q);
    }).slice(0, 10);
  };

  const value = {
    stocks,
    loading,
    error,
    lastFetch,
    lastBackendRefresh,
    fetchStocks,
    forceRefresh: () => fetchStocks(true),
    findStock,
    searchStocks,
    cacheAge: lastFetch ? Date.now() - lastFetch : 0,
  };

  return (
    <StockPriceContext.Provider value={value}>
      {children}
    </StockPriceContext.Provider>
  );
};
