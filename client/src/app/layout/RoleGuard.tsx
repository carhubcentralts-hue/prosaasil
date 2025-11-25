import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';
import { UserRole } from '../../features/auth/types';

interface RoleGuardProps {
  roles: UserRole[];
  children: React.ReactNode;
}

export function RoleGuard({ roles, children }: RoleGuardProps) {
  const { user, isLoading, impersonating } = useAuth();

  // Show minimal loading - redirect immediately
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="flex items-center gap-3 text-slate-600">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="text-sm">בודק הרשאות...</span>
        </div>
      </div>
    );
  }

  // BUILD 144: When system_admin is impersonating, grant 'owner' effective role
  // This allows access to all business-scoped pages while impersonating
  const effectiveRole = (impersonating && user?.role === 'system_admin') 
    ? 'owner'  // ✅ owner is a valid role that has access to business pages
    : user?.role;

  // Check if user has required role (considering impersonation)
  if (!user || !effectiveRole || !roles.includes(effectiveRole)) {
    // Redirect to appropriate home page based on actual role
    const homeRoute = user?.role === 'system_admin' && !impersonating
      ? '/app/admin/overview'
      : '/app/business/overview';
    
    return <Navigate to={homeRoute} replace />;
  }

  return <>{children}</>;
}