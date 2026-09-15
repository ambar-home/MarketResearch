import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward /api/* to FastAPI during local development
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // SMA scan can take a few minutes for full Nifty 100
        timeout: 600_000,
        proxyTimeout: 600_000,
      },
    },
  },
})
