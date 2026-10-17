import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // AI suggestions are served by server.py so the API key never reaches the browser
    proxy: { '/api': 'http://localhost:8000' },
  },
})
