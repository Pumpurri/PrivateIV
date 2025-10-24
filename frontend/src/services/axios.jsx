import axios from 'axios';

// Use environment variable for API URL, fallback to /api for local dev with proxy
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
});

// Small optimization: mark X-Requested-With for CSRF middleware heuristics
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// Read CSRF token from cookie (Django sets this)
function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

// Clear CSRF token (call on logout) - deletes the cookie
export function clearCSRFToken() {
  document.cookie = 'csrftoken=; Max-Age=0; path=/;';
}

// Interceptor to add CSRF token to requests
apiClient.interceptors.request.use(
  (config) => {
    // Skip CSRF for GET requests and the /csrf/ endpoint itself
    if (config.method !== 'get' && !config.url.includes('/csrf/')) {
      const csrfToken = getCookie('csrftoken');
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export { apiClient };
export default apiClient;
