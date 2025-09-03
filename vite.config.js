import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  root: './client',
  build: {
    outDir: '../dist',
    assetsDir: 'assets',
  },
  server: {
    host: '0.0.0.0',
    port: 3000,  // Frontend on port 3000
    proxy: {
      '/api': 'http://localhost:5000',  // Backend on port 5000
      '/webhook': 'http://localhost:5000',
      '/ws': {
        target: 'http://localhost:5000',
        ws: true
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  }
})