import axios from 'axios';

// Use environment variable for API URL, fallback to /api for local dev with proxy
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
});

// Small optimization: mark X-Requested-With for CSRF middleware heuristics
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// Read CSRF token from cookie (for local dev with same domain)
function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

// Store CSRF token from /csrf/ response (for production cross-domain)
let csrfTokenFromHeader = null;

// Clear CSRF token (call on logout)
export function clearCSRFToken() {
  csrfTokenFromHeader = null;
  document.cookie = 'csrftoken=; Max-Age=0; path=/;';
}

// Interceptor to capture CSRF token from /csrf/ response
apiClient.interceptors.response.use(
  (response) => {
    // Capture CSRF token from /csrf/ endpoint response header
    if (response.config.url?.includes('/csrf/')) {
      const token = response.headers['x-csrftoken'];
      if (token) {
        csrfTokenFromHeader = token;
      }
    }
    return response;
  },
  (error) => Promise.reject(error)
);

// Interceptor to add CSRF token to requests
apiClient.interceptors.request.use(
  (config) => {
    // Skip CSRF for GET requests and the /csrf/ endpoint itself
    if (config.method !== 'get' && !config.url.includes('/csrf/')) {
      // Try cookie first (local dev), then header (production)
      const csrfToken = getCookie('csrftoken') || csrfTokenFromHeader;
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export { apiClient };
export default apiClient;
