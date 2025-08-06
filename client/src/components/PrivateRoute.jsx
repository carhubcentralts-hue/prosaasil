import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const PrivateRoute = ({ children, requiredRole = null }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  console.log('PrivateRoute check:', { 
    user: !!user, 
    loading, 
    requiredRole, 
    userRole: user?.role,
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

  if (requiredRole && user.role !== requiredRole) {
    // Redirect based on user role
    const redirectPath = user.role === 'admin' ? '/admin/dashboard' : '/business/dashboard';
    return <Navigate to={redirectPath} replace />;
  }

  return children;
};

export default PrivateRoute;