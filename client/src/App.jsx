import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import BusinessDashboard from './pages/BusinessDashboard';
import AdminDashboard from './pages/AdminDashboard';
import BusinessViewPage from './pages/BusinessViewPage';
import LoginPage from './pages/LoginPage';
import PrivateRoute from './components/PrivateRoute';
import './index.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // בדיקה אם משתמש מחובר
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    
    console.log('Auth check:', { token: !!token, role });
    
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
    } else {
      setIsAuthenticated(false);
      setUserRole(null);
    }
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600 font-hebrew">טוען מערכת...</p>
        </div>
      </div>
    );
  }

  // אם לא מחובר - הצג רק דף התחברות
  if (!isAuthenticated) {
    return (
      <div className="App">
        <Router>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </Router>
      </div>
    );
  }

  // אם מחובר - הצג את המערכת המתאימה
  return (
    <div className="App">
      <Router>
        <Routes>
          {/* דשבורד מנהל */}
          <Route 
            path="/admin/dashboard" 
            element={
              userRole === 'admin' ? 
                <AdminDashboard /> : 
                <Navigate to="/login" replace />
            } 
          />
          
          {/* דשבורד עסק - גם עבור עסקים וגם עבור מנהלים במצב השתלטות */}
          <Route 
            path="/business/dashboard" 
            element={
              (userRole === 'business' || userRole === 'admin') ? 
                <BusinessDashboard /> : 
                <Navigate to="/login" replace />
            } 
          />
          
          {/* דף צפייה בעסק ספציפי - רק למנהלים */}
          <Route 
            path="/business/:businessId/dashboard" 
            element={
              userRole === 'admin' ? 
                <BusinessViewPage /> : 
                <Navigate to="/login" replace />
            } 
          />
          
          {/* נתיב ברירת מחדל - ניווט לפי תפקיד */}
          <Route 
            path="/" 
            element={
              userRole === 'admin' ? 
                <Navigate to="/admin/dashboard" replace /> :
                userRole === 'business' ?
                <Navigate to="/business/dashboard" replace /> :
                <Navigate to="/login" replace />
            } 
          />
          
          {/* התחברות - הפניה לדשבורד אם כבר מחובר */}
          <Route 
            path="/login"
            element={<Navigate to="/" replace />}
          />
          
          {/* כל שאר הנתיבים */}
          <Route 
            path="*" 
            element={<Navigate to="/" replace />}
          />
        </Routes>
      </Router>
    </div>
  );
}

export default App;
