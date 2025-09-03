import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  root: './client',
  build: {
    outDir: '../dist',
    assetsDir: 'assets',
  },
  server: {
    host: '0.0.0.0',
    port: 5000,
  },
  preview: {
    host: '0.0.0.0',
    port: 5000,
  },
})