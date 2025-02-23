import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api", // Proxy to Django backend
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

export default apiClient;