// Keep the public frontend in preview mode while the hosted API is paused.
// Set VITE_DEMO_PAUSED=false at build time when the backend is available again.
export const DEMO_PAUSED = import.meta.env.PROD && import.meta.env.VITE_DEMO_PAUSED !== 'false';
