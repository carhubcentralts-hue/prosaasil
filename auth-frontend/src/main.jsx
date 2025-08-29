import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Set VITE_API_BASE if not already set
if (!import.meta.env.VITE_API_BASE) {
  const baseUrl = window.location.protocol + '//' + window.location.host;
  window.__VITE_API_BASE__ = baseUrl;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
