import React, { useState, useEffect } from 'react';
import { useNavigate } from "react-router-dom";
import { registerUser } from "../services/api"; 

function Register() {
    const [form, setForm] = useState({ 
        email: '', 
        password: '', 
        fullName: '', 
        dob: '' 
    });
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        try {
            await registerUser({
                email: form.email,
                password: form.password,
                full_name: form.fullName,
                dob: form.dob
            });
            navigate('/dashboard');
        } catch (err) {
            const errorMessage = err.response?.data?.detail || 
                               err.response?.data?.error ||
                               'Registration failed. Please try again.';
            setError(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div>
            <h2>Register</h2>
            <form onSubmit={handleSubmit}>
                <input type="email" placeholder="Email" value={form.email}
                onChange={e => setForm({...form, email: e.target.value})} required />
                
                <input type="password" placeholder="Password" value={form.password}
                onChange={e => setForm({...form, password: e.target.value})} required />
                
                <input type="text" placeholder="Full Name" value={form.fullName}
                onChange={e => setForm({...form, fullName: e.target.value})} required />
                
                <input type="date" max={new Date().toISOString().split('T')[0]} 
                value={form.dob} onChange={e => setForm({...form, dob: e.target.value})} required />
                
                <button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? 'Registering...' : 'Register'}
                </button>
            </form>
            {error && <p style={{ color: 'red' }}>{error}</p>}
        </div>
    );
}
export default Register;