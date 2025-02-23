import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import dotenv from 'dotenv';

dotenv.config();

const keyPath = process.env.VITE_SSL_KEY_PATH
const certPath = process.env.VITE_SSL_CERT_PATH

if (!keyPath || !certPath) {
  throw new Error("SSL key or cert path is missing. Check your .env file.");
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    https: { // Enable HTTPS for frontend
      key: fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    },
    proxy: {
      '/api': {
        target: 'https://localhost:8000', // Your HTTPS Django backend
        changeOrigin: true,
        secure: false, // Required for self-signed certs
      },
    },
  },
});