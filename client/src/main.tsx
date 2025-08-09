import React from 'react'
import ReactDOM from 'react-dom/client'
import Login from './pages/Login'
import { AuthProvider } from './auth/AuthContext'
import './index.css'

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </React.StrictMode>
  );
}