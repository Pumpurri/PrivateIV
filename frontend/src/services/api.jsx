import apiClient from "./axios"; 

// Minimal cookie reader to avoid unnecessary /csrf/ calls
function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export const registerUser = async (userData) => {
  await ensureCsrf();
  return apiClient.post('/auth/register/', userData);
};

export const loginUser = async (credentials, config = {}) => {
  await ensureCsrf();
  return apiClient.post("/auth/login/", credentials, config);
};

export const verifyAuth = async () => {
  try {
    const response = await apiClient.get("/auth/me/");
    if (response.status === 200) {
      return {
        authenticated: true,
        user: response.data
      };
    }
    return { authenticated: false };
  } catch (error) {
    // 403/401 is expected when not logged in - don't log as error
    if (error.response?.status === 403 || error.response?.status === 401) {
      return { authenticated: false };
    }
    // Log unexpected errors
    console.error('Auth verification failed:', error);
    return { authenticated: false };
  }
};

// Ensure CSRF cookie prior to mutating requests
export const ensureCsrf = async () => {
  // Only fetch CSRF if cookie is missing
  if (!getCookie('csrftoken')) {
    try { await apiClient.get('/csrf/'); } catch (_) {}
  }
};

// Portfolios ---------------------------------------------------------------
export const getPortfolios = async () => {
  const { data } = await apiClient.get('/portfolios/');
  return data;
};

export const createPortfolio = async (payload) => {
  await ensureCsrf();
  const { data } = await apiClient.post('/portfolios/', payload);
  return data;
};

export const setDefaultPortfolio = async (portfolioId) => {
  await ensureCsrf();
  const { data } = await apiClient.post(`/portfolios/${portfolioId}/set-default/`);
  return data;
};

export const getPortfolio = async (id) => {
  const { data } = await apiClient.get(`/portfolios/${id}/`);
  return data;
};

export const getPortfolioHoldings = async (id) => {
  const { data } = await apiClient.get(`/portfolios/${id}/holdings/`);
  return data;
};

export const getPortfolioPerformance = async (id) => {
  const { data } = await apiClient.get(`/portfolios/${id}/performance/`);
  return data;
};

export const getPortfolioRealized = async (id, params = {}) => {
  const { data } = await apiClient.get(`/dashboard/portfolios/${id}/realized/`, { params });
  return data;
};

export const updatePortfolio = async (id, payload) => {
  await ensureCsrf();
  const { data } = await apiClient.patch(`/portfolios/${id}/`, payload);
  return data;
};

export const deletePortfolio = async (id) => {
  await ensureCsrf();
  const { data } = await apiClient.delete(`/portfolios/${id}/`);
  return data;
};

// Transactions -------------------------------------------------------------
export const getTransactions = async (params = {}) => {
  const { data } = await apiClient.get('/transactions/', { params });
  return data;
};

export const createTransaction = async (payload) => {
  await ensureCsrf();
  const { data } = await apiClient.post('/transactions/create/', payload);
  return data;
};

// Stocks ------------------------------------------------------------------
export const getStocks = async () => {
  const { data } = await apiClient.get('/stocks/');
  return data;
};

// Fetch all stocks across paginated results
export const getAllStocks = async () => {
  let url = '/stocks/';
  let all = [];
  let lastRefreshedAt = null;

  while (url) {
    const { data } = await apiClient.get(url);
    if (Array.isArray(data)) {
      all = data;
      break;
    }
    if (data?.last_refreshed_at && !lastRefreshedAt) {
      lastRefreshedAt = data.last_refreshed_at;
    }
    all = all.concat(data?.results || []);
    const next = data?.next;
    if (!next) {
      url = null;
    } else if (typeof next === 'string' && next.startsWith('http')) {
      const m = next.match(/\/api\/.*$/);
      url = m ? m[0].replace('/api', '') : next;
    } else if (typeof next === 'string' && next.startsWith('/api/')) {
      url = next.replace('/api', '');
    } else {
      url = next;
    }
  }

  return { stocks: all, lastRefreshedAt };
};

export const getStocksLastRefresh = async () => {
  const { data } = await apiClient.get('/stocks/last-refresh/');
  return data;
};

// Dashboard ---------------------------------------------------------------
export const getDashboard = async () => {
  const { data } = await apiClient.get('/dashboard/');
  return data;
};

export const getPortfolioOverviewApi = async (id, params = {}) => {
  const { data } = await apiClient.get(`/dashboard/portfolios/${id}/overview/`, { params });
  return data;
};

// FX Rates -----------------------------------------------------------------
export const getFXRates = async () => {
  const { data } = await apiClient.get('/fx-rates/');
  return data;
};
