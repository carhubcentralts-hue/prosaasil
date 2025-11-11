import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react({ jsxRuntime: 'classic' })], // ✅ CRITICAL: Classic runtime for Safari
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
    target: 'es2019',         // ✅ Safari compatibility - transpile for older browsers
    outDir: './dist',         // Build ל-client/dist (נכון!)
    assetsDir: 'assets',
    sourcemap: true,          // ✅ Enable sourcemaps for debugging
  },
  resolve: {
    dedupe: ['react', 'react-dom'], // ✅ CRITICAL: Force single React instance
    alias: {
      '@': '/src',
      'react': 'react',           // ✅ Pin React - prevent aliasing
      'react-dom': 'react-dom'    // ✅ Pin React-DOM
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom'] // ✅ Pre-bundle React for consistency
  }
})