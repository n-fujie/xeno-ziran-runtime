import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const backend = process.env.XZR_BACKEND ?? 'http://127.0.0.1:3011';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: { chunkSizeWarningLimit: 2500, sourcemap: false },
  test: { environment: 'node' },
});
