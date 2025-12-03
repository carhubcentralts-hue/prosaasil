import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react({ jsxRuntime: 'classic' })],
  base: '/',
  server: {
    host: '0.0.0.0',
    port: 3310,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:5000'
    }
  },
  build: {
    target: 'es2019',
    outDir: './dist',
    assetsDir: 'assets',
    sourcemap: true,
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      '@': path.resolve(__dirname, './src'),
      'react': 'react',
      'react-dom': 'react-dom'
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom']
  }
})