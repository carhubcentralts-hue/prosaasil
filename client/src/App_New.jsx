import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage_New';
import AdminDashboard from './pages/AdminDashboard_New';
import BusinessDashboard from './pages/BusinessDashboard_New';
import './styles/tokens.css';

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      // Check if user is stored in localStorage
      const userData = localStorage.getItem('user');
      if (userData) {
        const parsedUser = JSON.parse(userData);
        
        // Verify with server
        const response = await fetch('/auth/me');
        if (response.ok) {
          const serverUser = await response.json();
          setUser(serverUser);
        } else {
          // Invalid session, clear localStorage
          localStorage.removeItem('user');
        }
      }
    } catch (err) {
      console.error('Auth check error:', err);
      localStorage.removeItem('user');
    } finally {
      setLoading(false);
    }
  };

  // Protected Route Component
  const ProtectedRoute = ({ children, requiredRole = null }) => {
    if (loading) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p>טוען...</p>
          </div>
        </div>
      );
    }

    if (!user) {
      return <Navigate to="/login" replace />;
    }

    if (requiredRole && user.role !== requiredRole) {
      // Redirect based on user role
      if (user.role === 'admin') {
        return <Navigate to="/admin-dashboard" replace />;
      } else {
        return <Navigate to="/business-dashboard" replace />;
      }
    }

    return children;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען מערכת AgentLocator...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="App">
        <Routes>
          {/* Public Routes */}
          <Route 
            path="/login" 
            element={
              user ? (
                user.role === 'admin' ? 
                  <Navigate to="/admin-dashboard" replace /> : 
                  <Navigate to="/business-dashboard" replace />
              ) : (
                <LoginPage />
              )
            } 
          />

          {/* Protected Admin Routes */}
          <Route 
            path="/admin-dashboard" 
            element={
              <ProtectedRoute requiredRole="admin">
                <AdminDashboard />
              </ProtectedRoute>
            } 
          />

          {/* Protected Business Routes */}
          <Route 
            path="/business-dashboard" 
            element={
              <ProtectedRoute requiredRole="business">
                <BusinessDashboard />
              </ProtectedRoute>
            } 
          />

          {/* Default Route */}
          <Route 
            path="/" 
            element={
              user ? (
                user.role === 'admin' ? 
                  <Navigate to="/admin-dashboard" replace /> : 
                  <Navigate to="/business-dashboard" replace />
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />

          {/* Catch all other routes */}
          <Route 
            path="*" 
            element={
              <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
                  <p className="text-gray-600 mb-6">הדף שחיפשת לא נמצא</p>
                  <button 
                    onClick={() => window.location.href = '/'}
                    className="btn btn-primary"
                  >
                    חזור לדף הבית
                  </button>
                </div>
              </div>
            } 
          />
        </Routes>
      </div>
    </Router>
  );
};

export default App;