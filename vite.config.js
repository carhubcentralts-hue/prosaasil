import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react()],
  root: './client',
  build: {
    outDir: '../dist',
    assetsDir: 'assets',
  },
  server: {
    host: '0.0.0.0',
    port: 3000,  // Frontend on port 3000
    proxy: {
      '/api': process.env.NODE_ENV === 'production' 
        ? '' // Same domain in production
        : 'http://localhost:5000',  // Backend on port 5000 in dev
      '/webhook': process.env.NODE_ENV === 'production' 
        ? '' 
        : 'http://localhost:5000',
      '/ws': {
        target: process.env.NODE_ENV === 'production' 
          ? `wss://${process.env.REPLIT_DEV_DOMAIN || 'localhost:5000'}` 
          : 'http://localhost:5000',
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