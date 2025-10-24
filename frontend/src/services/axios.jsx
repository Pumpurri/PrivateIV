import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
  xsrfCookieName: 'csrftoken', 
  xsrfHeaderName: 'X-CSRFToken', 
});

// Small optimization: mark X-Requested-With for CSRF middleware heuristics
apiClient.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

export { apiClient };
export default apiClient;
