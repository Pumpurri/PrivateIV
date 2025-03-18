import apiClient from "./axios"; 

export const registerUser = async (userData) => {
  await apiClient.get('/csrf/'); 
  return apiClient.post('/auth/register/', userData);
};

export const loginUser = async (credentials, config = {}) => {
  await apiClient.get('/csrf/');
  return apiClient.post("/auth/login/", credentials, config);
};

export const verifyAuth = async () => {
  try {
    const response = await apiClient.get("/auth/me/");
    return response.status === 200;
  } catch {
    return false;
  }
};

