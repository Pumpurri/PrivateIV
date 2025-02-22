import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../services/axios";

function UserDashboard() {
    const [user, setUser] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const loadUser = async () => {
            try {
                const { data } = await apiClient.get("/auth/me/");
                setUser(data);
            } catch {
                navigate("/login");
            }
        };
        loadUser();
    }, [navigate]);

    const handleLogout = async () => {
        try {
            await apiClient.post("/auth/logout/");
            navigate("/login");
        } catch (error) {
            console.error("Logout failed:", error);
        }
    };

    return (
        <div>
            <h2>User Dashboard</h2>
            {user ? (
                <div>
                    <p>Username: {user.username}</p>
                    <p>Email: {user.email || "Not set"}</p>
                </div>
            ) : (
                <p>Loading...</p>
            )}
            <button onClick={handleLogout}>Logout</button>
        </div>
    );

}

export default UserDashboard;
