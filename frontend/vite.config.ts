/// <reference types="vitest" />
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// In development the Vite server proxies /api to the FastAPI backend, so the browser sees ONE
// origin. That keeps the HttpOnly session cookie first-party (no CORS, SameSite=Lax works).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const backend = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    resolve: { alias: { '@': '/src' } },
    server: { port: 5173, host: true, proxy: { '/api': { target: backend, changeOrigin: false } } },
    preview: { port: 4173, proxy: { '/api': { target: backend, changeOrigin: false } } },
    build: { sourcemap: false, chunkSizeWarningLimit: 900 },
    test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'], css: false },
  };
});
