import React from 'react';
import { useState } from "react";
import { registerUser } from "../services/api"; 
import apiClient from '../services/axios';

function Register() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [errorMessage, setErrorMessage] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await apiClient.get('/auth/csrf/');
            
            await registerUser({ username, password });
            alert("Registration successful");
        } catch (error) {
            console.error("Registration failed", error);
            setErrorMessage(error.response?.data?.detail || "Registration failed.");
        }
    };

    return (
        <div>
            <h2>Register</h2>
            <form onSubmit={handleSubmit}>
                <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
                <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button type="submit">Register</button>
            </form>
            {errorMessage && <p style={{ color: "red" }}>{errorMessage}</p>}
        </div>
    );
}

export default Register;