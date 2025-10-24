import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from "react-router-dom";
import { createPortfolio } from "../services/api";

function CreatePortfolio({ onSuccess, onCancel }) {
    const [form, setForm] = useState({
        name: '',
        description: '',
        initial_deposit: ''
    });
    const [error, setError] = useState('');
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

        setError('');
        setIsSubmitting(true);
        
        abortControllerRef.current = new AbortController();

        try {
            const payload = {
                name: form.name.trim(),
                description: form.description.trim() || undefined
            };

            const amt = parseFloat(form.initial_deposit);
            if (!amt || amt <= 0) {
                throw new Error('El depósito inicial es obligatorio y debe ser mayor que 0.');
            }
            payload.initial_deposit = amt;

            const response = await createPortfolio(payload);

            if (onSuccess) {
                onSuccess(response);
            } else {
                navigate('/dashboard');
            }
        } catch (err) {
            if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
                console.log('Request was intentionally canceled');
                return;
            }
            
            const errorMessage = err.response?.data?.initial_deposit?.[0] ||
                                 err.response?.data?.detail || 
                                 err.response?.data?.error ||
                                 err.response?.data?.name?.[0] ||
                                 err.message ||
                                 'Error al crear el portafolio. Inténtalo de nuevo.';
            setError(errorMessage);
        } finally {
            setIsSubmitting(false);
            abortControllerRef.current = null;
        }
    };

    const handleCancel = () => {
        if (onCancel) {
            onCancel();
        }
        navigate('/dashboard');
    };

    return (
        <div className="card" style={{ width: '100%', maxWidth: 480, padding: 24 }}>
            <div style={{ textAlign: 'center', marginBottom: 12 }}>
                <h2 style={{ margin: '0 0 6px' }}>Crear Portafolio</h2>
                <p className="muted" style={{ margin: 0 }}>Configura tu nuevo portafolio manual</p>
            </div>

            <form onSubmit={handleSubmit} className="grid" style={{ gap: 12 }}>
                <div className="grid" style={{ gap: 6 }}>
                    <label className="muted" htmlFor="name">Nombre del portafolio</label>
                    <input
                        id="name"
                        className="input"
                        type="text"
                        placeholder="Mi portafolio"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        maxLength={100}
                        required
                    />
                </div>

                <div className="grid" style={{ gap: 6 }}>
                    <label className="muted" htmlFor="description">Descripción (opcional)</label>
                    <textarea
                        id="description"
                        className="input"
                        placeholder="Describe tu estrategia o objetivos..."
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                        rows={3}
                        style={{ resize: 'vertical', minHeight: '80px' }}
                    />
                </div>

                <div className="grid" style={{ gap: 6 }}>
                    <label className="muted" htmlFor="initial_deposit">Depósito inicial</label>
                    <input
                        id="initial_deposit"
                        className="input no-spin"
                        type="number"
                        placeholder="0.00"
                        value={form.initial_deposit}
                        onChange={(e) => setForm({ ...form, initial_deposit: e.target.value })}
                        min="0.01"
                        step="0.01"
                        required
                    />
                    <p className="muted" style={{ fontSize: '12px', margin: 0 }}>
                        Cantidad en efectivo para empezar a invertir (obligatorio)
                    </p>
                </div>

                {error && (
                    <div className="card" style={{ borderColor: 'rgba(239,68,68,.35)', background: 'rgba(127,29,29,.15)' }}>
                        <p style={{ color: '#fecaca', margin: 0 }}>{error}</p>
                    </div>
                )}

                <div className="row" style={{ gap: 12, marginTop: 4 }}>
                    <button
                        type="button"
                        className="btn"
                        onClick={handleCancel}
                        disabled={isSubmitting}
                        style={{ flex: 1 }}
                    >
                        Cancelar
                    </button>
                    <button
                        className="btn primary"
                        type="submit"
                        disabled={isSubmitting || !form.name.trim() || !(parseFloat(form.initial_deposit) > 0)}
                        style={{ flex: 1 }}
                    >
                        {isSubmitting ? 'Creando...' : 'Crear Portafolio'}
                    </button>
                </div>
            </form>
        </div>
    );
}

export default CreatePortfolio;
