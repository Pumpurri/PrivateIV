import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from "react-router-dom";
import { registerUser } from "../services/api";
import DatePicker from "./DatePicker";
import { useAuth } from "../contexts/AuthContext";

function Register() {
    const [form, setForm] = useState({
        email: '',
        password: '',
        confirmPassword: '',
        fullName: '',
        dob: ''
    });
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [pwIssues, setPwIssues] = useState({ required: [], recommended: [] });
    const navigate = useNavigate();
    const { login } = useAuth();

    function assessPassword(pw, email, fullName) {
        const required = [];
        const recommended = [];
        const trimmedEmail = (email || '').trim().toLowerCase();
        const nameParts = (fullName || '').toLowerCase().split(/\s+/).filter(p => p.length >= 3);
        const emailLocal = trimmedEmail.split('@')[0] || '';

        // Base rules should be visible from the start
        if (!pw) {
            required.push('Mínimo 8 caracteres');
            required.push('Mezcla letras y números');
            return { required, recommended };
        }

        if (pw.length < 8) required.push('Mínimo 8 caracteres');

        if (!(/[a-zA-Z]/.test(pw) && /\d/.test(pw))) {
            required.push('Mezcla letras y números');
        }

        const lowerPw = pw.toLowerCase();
        const similarToEmail = Boolean(emailLocal) && lowerPw.includes(emailLocal);
        const similarToName = nameParts.some(p => lowerPw.includes(p));
        if (similarToEmail || similarToName) required.push('No similar a tu correo/nombre');

        return { required, recommended };
    }

    // Re-evaluate password rules when email or full name changes
    useEffect(() => {
        if (form.password) {
            setPwIssues(assessPassword(form.password, form.email, form.fullName));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [form.email, form.fullName]);

    // Initialize checklist on mount
    useEffect(() => {
        setPwIssues(assessPassword(form.password, form.email, form.fullName));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            // Simple frontend validation for password match
            if (form.password !== form.confirmPassword) {
                setError('Las contraseñas no coinciden');
                setIsSubmitting(false);
                return;
            }
            const pwCheck = assessPassword(form.password, form.email, form.fullName);
            if (pwCheck.required.length > 0) {
                setPwIssues(pwCheck);
                setError('La contraseña no cumple los requisitos');
                setIsSubmitting(false);
                return;
            }
            await registerUser({
                email: form.email.trim().toLowerCase(),
                password: form.password,
                full_name: form.fullName.trim(),
                dob: form.dob
            });
            // Update auth state immediately (no need for additional API call)
            login();
            navigate('/dashboard');
        } catch (err) {
            // Prefer structured field errors from DRF serializers
            const data = err.response?.data;
            let msg = '';
            if (typeof data === 'string') {
                msg = data;
            } else if (data?.detail || data?.error) {
                msg = data.detail || data.error;
            } else if (data && typeof data === 'object') {
                // Join first error per field: { email: ["Email already in use."] }
                const parts = [];
                Object.entries(data).forEach(([field, val]) => {
                    const first = Array.isArray(val) ? val[0] : String(val);
                    parts.push(`${field}: ${first}`);
                });
                msg = parts.join(' | ');
            }
            setError(msg || 'No se pudo completar el registro. Inténtalo de nuevo.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="app-page" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
            {/* Contenido centrado */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '22px 20px 32px' }}>
                <div className="card" style={{ width: '100%', maxWidth: 480, padding: 24 }}>
                    <div style={{ textAlign: 'center', marginBottom: 2 }}>
                        <h2 style={{ margin: '0 0 6px' }}>Regístrate</h2>
                        <p className="muted" style={{ margin: 0 }}>Crea tu cuenta para empezar a simular</p>
                    </div>

                <form onSubmit={handleSubmit} className="grid" style={{ gap: 12 }}>
                    <div className="grid" style={{ gap: 6 }}>
                        <label className="muted" htmlFor="email">Correo electrónico</label>
                        <input id="email" className="input" type="email" placeholder="tu@email.com" value={form.email}
                            onChange={e => setForm({ ...form, email: e.target.value })} required />
                    </div>

                    <div className="row" style={{ gap: 12 }}>
                        <div className="grid" style={{ gap: 6, flex: 1 }}>
                            <label className="muted" htmlFor="password">Contraseña</label>
                            <div className="input-wrap">
                                <input id="password" className="input" type={showPassword ? 'text' : 'password'} placeholder="••••••••" value={form.password}
                                    onChange={e => {
                                        const val = e.target.value;
                                        setForm({ ...form, password: val });
                                        setPwIssues(assessPassword(val, form.email, form.fullName));
                                    }} required />
                                <button type="button" className="icon-btn" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                                    onClick={() => setShowPassword(s => !s)}>
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
                        <div className="grid" style={{ gap: 6, flex: 1 }}>
                            <label className="muted" htmlFor="confirmPassword">Verificar contraseña</label>
                            <input id="confirmPassword" className="input" type={showPassword ? 'text' : 'password'} placeholder="••••••••" value={form.confirmPassword}
                                onChange={e => setForm({ ...form, confirmPassword: e.target.value })} required />
                        </div>
                    </div>

                    {pwIssues.required.length > 0 && (
                        <div className="card" style={{ background: 'rgba(12,20,39,.85)', fontSize: 12, padding: 12 }}>
                            <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'grid', gap: 4 }}>
                                {pwIssues.required.map((r, idx) => (
                                    <li key={idx} style={{ color: '#fecaca' }}>✗ {r}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="grid" style={{ gap: 6 }}>
                        <label className="muted" htmlFor="fullname">Nombre completo</label>
                        <input id="fullname" className="input" type="text" placeholder="Nombre y apellido" value={form.fullName}
                            onChange={e => setForm({ ...form, fullName: e.target.value })} required />
                    </div>

                    <div className="grid" style={{ gap: 6 }}>
                        <DatePicker
                          id="dob"
                          label="Fecha de nacimiento"
                          value={form.dob}
                          max={new Date().toISOString().split('T')[0]}
                          onChange={(iso) => setForm({ ...form, dob: iso })}
                        />
                    </div>

                    {error && <div className="card" style={{ borderColor: 'rgba(239,68,68,.35)', background: 'rgba(127,29,29,.15)' }}>
                        <p style={{ color: '#fecaca', margin: 0 }}>{error}</p>
                    </div>}

                    <button className="btn primary" type="submit" disabled={
                        isSubmitting ||
                        !form.email || !form.fullName || !form.dob ||
                        form.password !== form.confirmPassword ||
                        pwIssues.required.length > 0
                    }>
                        {isSubmitting ? 'Creando cuenta…' : 'Regístrate'}
                    </button>
                </form>

                <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
                    <span className="muted">¿Ya tienes cuenta?</span>
                    <Link to="/login">Inicia sesión</Link>
                </div>
                </div>
            </div>
        </div>
    );
}
export default Register;
