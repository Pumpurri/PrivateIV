import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
  xsrfCookieName: 'csrftoken', 
  xsrfHeaderName: 'X-CSRFToken', 
});

export { apiClient };
export default apiClient;