import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Im Dev-Betrieb leitet Vite API-Aufrufe an das FastAPI-Backend weiter.
const backend = process.env.TESSERACT_BACKEND_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': { target: backend, changeOrigin: true }
    }
  }
});
