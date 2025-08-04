import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';

const PrivateRoute = ({ children, requiredRole }) => {
  const token = localStorage.getItem('auth_token');
  const userRole = localStorage.getItem('user_role');
  const adminTakeover = localStorage.getItem('admin_takeover_mode');

  console.log('🔒 PrivateRoute: Checking access', { 
    token: !!token, 
    userRole, 
    requiredRole, 
    adminTakeover: adminTakeover === 'true' 
  });

  // אם אין טוכן, הפנה להתחברות
  if (!token) {
    console.log('🚫 PrivateRoute: No token, redirecting to login');
    return <Navigate to="/login" replace />;
  }

  // אם יש role mismatch
  if (requiredRole && userRole !== requiredRole) {
    console.log('🚫 PrivateRoute: Role mismatch - need:', requiredRole, 'have:', userRole);
    console.log('🔍 PrivateRoute: Admin takeover mode:', adminTakeover);
    
    // במקרה של השתלטות מנהל - הפנה ישירות לדשבורד עסק
    if (adminTakeover === 'true' && userRole === 'business') {
      console.log('🔄 PrivateRoute: FIXED - Admin takeover active, forcing redirect to business dashboard');
      // Force immediate redirect without React Router delays
      setTimeout(() => {
        window.location.href = '/business/dashboard';
      }, 100);
      return <div>מעביר לדשבורד העסק...</div>; // Show message while redirecting
    }
    
    // הפנה לדף המתאים לפי התפקיד
    if (userRole === 'admin') {
      console.log('🔄 PrivateRoute: Redirecting admin to admin dashboard');
      return <Navigate to="/admin/dashboard" replace />;
    } else if (userRole === 'business') {
      console.log('🔄 PrivateRoute: Redirecting business to business dashboard');
      return <Navigate to="/business/dashboard" replace />;
    } else {
      console.log('🔄 PrivateRoute: Unknown role, redirecting to login');
      return <Navigate to="/login" replace />;
    }
  }

  console.log('✅ PrivateRoute: Access granted');
  return children;
};

export default PrivateRoute;