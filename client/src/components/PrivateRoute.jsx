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
    console.log('🚫 PrivateRoute: Role mismatch, redirecting to unauthorized');
    return <Navigate to="/unauthorized" replace />;
  }

  console.log('✅ PrivateRoute: Access granted');
  return children;
};

export default PrivateRoute;