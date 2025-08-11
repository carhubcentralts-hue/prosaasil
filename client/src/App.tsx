import React from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';
import './index.css';

function AppContent() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
      }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '15px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🔄</div>
          <div>טוען...</div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  // Route based on user role
  if (user.role === 'admin') {
    return <AdminDashboard />;
  } else if (user.role === 'business') {
    return <BusinessDashboard />;
  }

  // Fallback
  return <LoginPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}