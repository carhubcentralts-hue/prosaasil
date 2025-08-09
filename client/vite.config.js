import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': 'http://localhost:5000',
      '/webhook': 'http://localhost:5000',
      '/socket.io': { target: 'http://localhost:5000', ws: true }
    }
  }
})