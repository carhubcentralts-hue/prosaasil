import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const PrivateRoute = ({ children, requiredRole = null }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  // בדיקת מצב השתלטות אדמין
  const adminTakeoverMode = localStorage.getItem('admin_takeover_mode') === 'true';
  const isAdminInTakeoverMode = user?.role === 'admin' && adminTakeoverMode;

  console.log('PrivateRoute check:', { 
    user: !!user, 
    loading, 
    requiredRole, 
    userRole: user?.role,
    adminTakeoverMode,
    isAdminInTakeoverMode,
    path: location.pathname 
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">טוען...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // אם יש השתלטות אדמין ו-requiredRole הוא 'business', אפשר גישה
  if (requiredRole === 'business' && isAdminInTakeoverMode) {
    console.log('🔑 Admin takeover mode: allowing access to business route');
    return children;
  }

  // אם יש השתלטות אדמין ו-requiredRole הוא 'admin', חזור לדשבורד אדמין
  if (requiredRole === 'admin' && isAdminInTakeoverMode) {
    console.log('🔙 Admin takeover mode: redirecting admin routes to admin dashboard');
    return <Navigate to="/admin/dashboard" replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    // נווט לפי תפקיד המשתמש
    const redirectPath = user.role === 'admin' ? '/admin/dashboard' : '/business/dashboard';
    console.log('🚫 Role mismatch: redirecting to', redirectPath);
    return <Navigate to={redirectPath} replace />;
  }

  return children;
};

export default PrivateRoute;