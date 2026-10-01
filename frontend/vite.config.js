import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // GitHub Pages serves the site from /<repo>/; local development stays at /.
  base: process.env.VITE_BASE || '/',
  server: {
    port: 5173,
    // The frontend calls /api/* and Vite forwards it to FastAPI. This keeps
    // the browser on a single origin in development, so there is no CORS
    // dance and no API base URL hard-coded into the bundle.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
