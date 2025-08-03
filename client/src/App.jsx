import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';
import BusinessViewPage from './pages/BusinessViewPage';
import PrivateRoute from './components/PrivateRoute';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = () => {
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    const name = localStorage.getItem('user_name');
    
    console.log('Auth check:', { token: !!token, role });
    
    if (token && role && name) {
      setIsAuthenticated(true);
      setUserRole(role);
    }
    
    setLoading(false);
  };

  const handleLoginSuccess = () => {
    checkAuthStatus();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">בודק סטטוס התחברות...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="App" dir="rtl">
        <Routes>
          {/* דף התחברות */}
          <Route 
            path="/login" 
            element={
              isAuthenticated ? 
                <Navigate to={userRole === 'admin' ? '/admin/dashboard' : '/business/dashboard'} replace /> : 
                <LoginPage onLoginSuccess={handleLoginSuccess} />
            } 
          />
          
          {/* ניתוב אוטומטי מעמוד הבית */}
          <Route 
            path="/" 
            element={
              isAuthenticated ? 
                <Navigate to={userRole === 'admin' ? '/admin/dashboard' : '/business/dashboard'} replace /> : 
                <Navigate to="/login" replace />
            } 
          />
          
          {/* דפי מנהל */}
          <Route 
            path="/admin/dashboard" 
            element={
              <PrivateRoute requiredRole="admin">
                <AdminDashboard />
              </PrivateRoute>
            } 
          />
          
          <Route 
            path="/admin/business/:id/view" 
            element={
              <PrivateRoute requiredRole="admin">
                <BusinessViewPage />
              </PrivateRoute>
            } 
          />
          
          {/* דפי עסק */}
          <Route 
            path="/business/dashboard" 
            element={
              <PrivateRoute requiredRole="business">
                <BusinessDashboard />
              </PrivateRoute>
            } 
          />
          
          {/* דף לא מורשה */}
          <Route 
            path="/unauthorized" 
            element={
              <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
                <div className="text-center font-hebrew">
                  <h1 className="text-2xl font-bold text-red-600 mb-4">אין הרשאה</h1>
                  <p className="text-gray-600 mb-4">אין לך הרשאה לגשת לדף זה</p>
                  <button 
                    onClick={() => window.location.href = '/'}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                  >
                    חזור לעמוד הבית
                  </button>
                </div>
              </div>
            } 
          />
          
          {/* דף 404 */}
          <Route 
            path="*" 
            element={
              <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
                <div className="text-center font-hebrew">
                  <h1 className="text-2xl font-bold text-gray-900 mb-4">דף לא נמצא</h1>
                  <p className="text-gray-600 mb-4">הדף שחיפשת לא קיים</p>
                  <button 
                    onClick={() => window.location.href = '/'}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                  >
                    חזור לעמוד הבית
                  </button>
                </div>
              </div>
            } 
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;