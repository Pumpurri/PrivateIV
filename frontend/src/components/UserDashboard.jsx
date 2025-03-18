import React, { useState, useEffect } from 'react';
import { useNavigate } from "react-router-dom";
import apiClient from "../services/axios";

function UserDashboard() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [logoutLoading, setLogoutLoading] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        let isMounted = true;
        const loadUser = async () => {
            try {
                const { data } = await apiClient.get("/auth/me/");
                if (isMounted) {
                    setUser(data);
                    setLoading(false);
                }
            } catch {
                if (isMounted) {
                    setLoading(false);
                    navigate("/login");
                }
            }
        };
        loadUser();
        return () => { isMounted = false; };
    }, [navigate]);

    const handleLogout = async () => {
        setLogoutLoading(true);
        try {
            await apiClient.post('/auth/logout/');
            navigate('/login');
        } catch (error) {
            console.error("Logout failed:", error);
            alert('Logout failed. Please try again.');
        } finally {
            setLogoutLoading(false);
        }
    };

    if (loading) {
        return <div>Loading user data...</div>;
    }

    return (
        <div>
            <h2>User Dashboard</h2>
            {user ? (
                <div>
                    <p>Name: {user.full_name}</p>
                    <p>Email: {user.email}</p>
                    <p>Age: {user.age}</p>
                </div>
            ) : (
                <p>No user data found</p>
            )}
            <button onClick={handleLogout} disabled={logoutLoading}>
                {logoutLoading ? 'Logging out...' : 'Logout'}
            </button>
        </div>
    );

}

export default UserDashboard;
