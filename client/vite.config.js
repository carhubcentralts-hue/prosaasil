import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',                  // ← חשוב! assets תמיד יהיו /assets/ (לא יחסיים)
  server: {
    host: '0.0.0.0',
    port: 3310,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:5000'
    }
  },
  build: {
    outDir: './dist',         // Build ל-client/dist (נכון!)
    assetsDir: 'assets',
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  }
})