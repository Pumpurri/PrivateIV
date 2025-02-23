import apiClient from "../services/axios";
import { useNavigate } from "react-router-dom";

export const logoutUser = async (navigate) => {
    try {
        const response = await apiClient.post("/auth/logout/", {}, {
            withCredentials: true,  // Ensure cookies are sent
        });
        
        if (response.status === 200) {
            console.log("Successfully logged out");
            navigate("/login"); 
        } else {
            console.error("Logout request did not succeed:", response);
        }
    } catch (error) {
        console.error("Logout request failed:", error);
    }
};