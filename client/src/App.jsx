import React from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './pages/Login';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-spinner-container">
        <div className="loading-spinner"></div>
        <p>טוען...</p>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  // Route based on user role
  if (user.role === 'admin') {
    return <AdminDashboard />;
  } else {
    return <BusinessDashboard />;
  }
}

function App() {
  return (
    <AuthProvider>
      <div className="App">
        <AppContent />
      </div>
    </AuthProvider>
  );
}

export default App;