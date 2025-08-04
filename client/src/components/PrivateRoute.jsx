import React from 'react';
import { Navigate } from 'react-router-dom';

const PrivateRoute = ({ children, requiredRole }) => {
  const token = localStorage.getItem('auth_token');
  const userRole = localStorage.getItem('user_role');

  console.log('🔒 PrivateRoute: Checking access', { token: !!token, userRole, requiredRole });

  if (!token) {
    console.log('🚫 PrivateRoute: No token, redirecting to login');
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && userRole !== requiredRole) {
    console.log('🚫 PrivateRoute: Role mismatch, redirecting to appropriate page');
    
    // הפניה ישירה לדף המתאים במקום unauthorized
    const adminTakeover = localStorage.getItem('admin_takeover_mode');
    if (adminTakeover === 'true') {
      const originalToken = localStorage.getItem('original_admin_token');
      if (originalToken) {
        localStorage.removeItem('admin_takeover_mode');
        localStorage.setItem('auth_token', originalToken);
        localStorage.setItem('user_role', 'admin');
        localStorage.setItem('user_name', 'מנהל');
        localStorage.removeItem('original_admin_token');
        localStorage.removeItem('business_id');
        return <Navigate to="/admin/dashboard" replace />;
      }
    }
    
    if (userRole === 'admin') {
      return <Navigate to="/admin/dashboard" replace />;
    } else if (userRole === 'business') {
      return <Navigate to="/business/dashboard" replace />;
    } else {
      return <Navigate to="/login" replace />;
    }
  }

  console.log('✅ PrivateRoute: Access granted');
  return children;
};

export default PrivateRoute;