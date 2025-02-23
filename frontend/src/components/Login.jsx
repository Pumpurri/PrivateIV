import React from 'react';
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser } from "../services/api";
import apiClient from '../services/axios';

function Login() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [errorMessage, setErrorMessage] = useState("");
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await apiClient.get('/auth/csrf/');
            
            await loginUser({ username, password });
            
            const { data } = await apiClient.get("/auth/me/");
            navigate("/dashboard");
        } catch (error) {
            console.error('Full error:', error);
            setErrorMessage(error.response?.data?.non_field_errors?.[0] || "Login failed");
        }
    };
    
    return (
        <div>
            <h2>Login</h2>
            <form onSubmit={handleSubmit}>
                <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
                <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button type="submit">Login</button>
            </form>
            {errorMessage && <p style={{ color: "red" }}>{errorMessage}</p>}
        </div>
    );
}

export default Login;