import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';
import AdminBusinessControlPage from './pages/AdminBusinessControlPage';
import AdvancedBusinessDashboard from './components/AdvancedBusinessDashboard';
import BusinessViewPage from './pages/BusinessViewPage';
import AdminCRMAdvanced from './pages/AdminCRMAdvanced';
import BusinessCRMAdvanced from './pages/BusinessCRMAdvanced';
import PrivateRoute from './components/PrivateRoute';

// דף לא מורשה חכם
const UnauthorizedPage = () => {
  const handleRedirect = () => {
    const role = localStorage.getItem('user_role');
    const adminTakeover = localStorage.getItem('admin_takeover_mode');
    
    console.log('🚫 Unauthorized page - role:', role, 'admin takeover:', adminTakeover);
    
    // אם אנחנו במצב השתלטות מנהל, חזור למנהל
    if (adminTakeover === 'true') {
      const originalToken = localStorage.getItem('original_admin_token');
      if (originalToken) {
        localStorage.removeItem('admin_takeover_mode');
        localStorage.setItem('auth_token', originalToken);
        localStorage.setItem('user_role', 'admin');
        localStorage.setItem('user_name', 'מנהל');
        localStorage.removeItem('original_admin_token');
        localStorage.removeItem('business_id');
        window.location.href = '/admin/dashboard';
        return;
      }
    }
    
    // אחרת, הפנה לפי התפקיד
    if (role === 'admin') {
      window.location.href = '/admin/dashboard';
    } else if (role === 'business') {
      window.location.href = '/business/dashboard';
    } else {
      window.location.href = '/login';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
      <div className="text-center font-hebrew">
        <h1 className="text-2xl font-bold text-red-600 mb-4">אין הרשאה</h1>
        <p className="text-gray-600 mb-4">אין לך הרשאה לגשת לדף זה</p>
        <button 
          onClick={handleRedirect}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          חזור לדף המתאים
        </button>
      </div>
    </div>
  );
};

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

  console.log('🌐 App: Current location:', window.location.pathname);

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
          
          {/* ניתוב להשתלטות על עסק */}
          <Route 
            path="/admin/business-control/:id" 
            element={
              <PrivateRoute requiredRole="admin">
                <AdminBusinessControlPage />
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
          
          {/* דשבורד עסק מתקדם */}
          <Route 
            path="/business/advanced" 
            element={
              <PrivateRoute requiredRole="business">
                <AdvancedBusinessDashboard />
              </PrivateRoute>
            } 
          />
          
          {/* דף צפייה בעסק למנהל */}
          <Route 
            path="/admin/business/:id/view" 
            element={
              <PrivateRoute requiredRole="admin">
                <BusinessViewPage />
              </PrivateRoute>
            } 
          />
          
          {/* CRM מתקדם למנהל */}
          <Route 
            path="/admin/crm/advanced" 
            element={
              <PrivateRoute requiredRole="admin">
                <AdminCRMAdvanced />
              </PrivateRoute>
            } 
          />
          
          {/* CRM מתקדם לעסק */}
          <Route 
            path="/business/crm/advanced" 
            element={
              <PrivateRoute requiredRole="business">
                <BusinessCRMAdvanced />
              </PrivateRoute>
            } 
          />
          
          {/* דף לא מורשה - עם טיפול חכם */}
          <Route 
            path="/unauthorized" 
            element={
              <UnauthorizedPage />
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