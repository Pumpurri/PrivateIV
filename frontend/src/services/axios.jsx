import axios from 'axios';

// Use environment variable for API URL, fallback to /api for local dev with proxy
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
});

// Small optimization: mark X-Requested-With for CSRF middleware heuristics
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// Store CSRF token in memory
let csrfToken = null;

// Function to fetch CSRF token from backend
export async function fetchCSRFToken() {
  try {
    const response = await apiClient.get('/csrf/');
    csrfToken = response.headers['x-csrftoken'];
    return csrfToken;
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error);
    return null;
  }
}

// Interceptor to add CSRF token to requests
apiClient.interceptors.request.use(
  async (config) => {
    // Skip CSRF for GET requests and the /csrf/ endpoint itself
    if (config.method !== 'get' && !config.url.includes('/csrf/')) {
      if (!csrfToken) {
        await fetchCSRFToken();
      }
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
