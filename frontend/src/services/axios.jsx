import axios from 'axios';

// Use environment variable for API URL, fallback to /api for local dev with proxy
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Small optimization: mark X-Requested-With for CSRF middleware heuristics
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

export { apiClient };
export default apiClient;
