import axios from "./axios";
import apiClient from "./axios"; 

export const registerUser = async (userData) => {
    try {
      const response = await apiClient.post("/auth/register/", userData);  // Use the configured axios instance
      return response.data;
    } catch (error) {
      console.error("Registration failed:", error.response?.data || error);
      throw error;
    }
};

export const loginUser = async (credentials) => {
    try {
        const response = await apiClient.post("/auth/login/", credentials);
        return response.data;
    } catch (error) {
        console.error("Login failed:", error.response?.data || error);
        throw error;
    }
};

export const verifyAuth = async () => {
  try {
    await apiClient.get("/auth/me/");
    return true;
  } catch {
    return false;
  }
};

apiClient.interceptors.request.use(config => {
  const csrfToken = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1];
  
  if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});