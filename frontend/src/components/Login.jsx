import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from "react-router-dom";
import { loginUser } from "../services/api";

function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [errorMessage, setErrorMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const navigate = useNavigate();
    const abortControllerRef = useRef(null);

    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (isSubmitting) return;

        setErrorMessage("");
        setIsSubmitting(true);
        
        abortControllerRef.current = new AbortController();

        try {
            const response = await loginUser({
                email: email.trim().toLowerCase(),
                password: password.trim()
            }, {
                signal: abortControllerRef.current.signal
            });

            navigate("/dashboard");
        } catch (err) {
            if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
                console.log('Request was intentionally canceled');
                return;
            }
            
            setErrorMessage(
                err.response?.data?.error ||
                "Login failed. Please check your credentials."
            );
        } finally {
            setIsSubmitting(false);
            abortControllerRef.current = null;
        }
    };

    return (
        <div>
            <h2>Login</h2>
            <form onSubmit={handleSubmit}>
                <input
                    type="email"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
                <input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
                <button 
                    type="submit" 
                    disabled={isSubmitting}
                >
                    {isSubmitting ? 'Logging in...' : 'Login'}
                </button>
            </form>
            {errorMessage && <p style={{ color: "red" }}>{errorMessage}</p>}
        </div>
    );
}

export default Login;