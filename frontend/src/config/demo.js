// Keep the public frontend in preview mode while the hosted API is paused.
// Set VITE_DEMO_PAUSED=false at build time when the backend is available again.
export const isDemoPaused = (environment) =>
  environment.PROD && environment.VITE_DEMO_PAUSED !== 'false';

export const DEMO_PAUSED = isDemoPaused(import.meta.env);
