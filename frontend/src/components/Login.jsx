import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from "react-router-dom";
import { loginUser } from "../services/api";

function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [errorMessage, setErrorMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
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
                "Error al iniciar sesión. Verifica tus credenciales."
            );
        } finally {
            setIsSubmitting(false);
            abortControllerRef.current = null;
        }
    };

    return (
        <div className="app-page" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
            {/* Contenido centrado */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '120px 20px 20px' }}>
                <div className="card" style={{ width: '100%', maxWidth: 480, padding: 24 }}>
                    <div style={{ textAlign: 'center', marginBottom: 12 }}>
                        <h2 style={{ margin: '0 0 6px' }}>Iniciar sesión</h2>
                        <p className="muted" style={{ margin: 0 }}>Entra para continuar con tu simulación</p>
                    </div>

                    <form onSubmit={handleSubmit} className="grid" style={{ gap: 12 }}>
                        <div className="grid" style={{ gap: 6 }}>
                            <label className="muted" htmlFor="email">Correo electrónico</label>
                            <input
                                id="email"
                                className="input"
                                type="email"
                                placeholder="tu@email.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>

                        <div className="grid" style={{ gap: 6 }}>
                            <label className="muted" htmlFor="password">Contraseña</label>
                            <div className="input-wrap">
                                <input
                                    id="password"
                                    className="input"
                                    type={showPassword ? 'text' : 'password'}
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <button
                                    type="button"
                                    className="icon-btn"
                                    aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                                    onClick={() => setShowPassword(s => !s)}
                                >
                                    {showPassword ? (
                                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-10-8-10-8a21.83 21.83 0 0 1 5.06-7.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 10 8 10 8a21.83 21.83 0 0 1-3.22 4.88"/>
                                            <line x1="1" y1="1" x2="23" y2="23" />
                                        </svg>
                                    ) : (
                                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M1 12s3-8 11-8 11 8 11 8-3 8-11 8-11-8-11-8Z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                        </svg>
                                    )}
                                </button>
                            </div>
                        </div>

                        {errorMessage && (
                            <div className="card" style={{ borderColor: 'rgba(239,68,68,.35)', background: 'rgba(127,29,29,.15)' }}>
                                <p style={{ color: '#fecaca', margin: 0 }}>{errorMessage}</p>
                            </div>
                        )}

                        <button className="btn primary" type="submit" disabled={isSubmitting}>
                            {isSubmitting ? 'Ingresando…' : 'Entrar'}
                        </button>
                    </form>

                    <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
                        <span className="muted">¿No tienes cuenta?</span>
                        <Link to="/register">Regístrate</Link>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Login;
