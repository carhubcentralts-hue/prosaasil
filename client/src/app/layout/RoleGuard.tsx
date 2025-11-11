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

  // When impersonating, treat the user as having 'business' role
  const effectiveRole = impersonating ? 'business' : user?.role;

  // Check if user has required role (considering impersonation)
  if (!user || !effectiveRole || !roles.includes(effectiveRole)) {
    // Redirect to appropriate home page based on effective role
    const homeRoute = (effectiveRole === 'admin' || effectiveRole === 'manager') && !impersonating
      ? '/app/admin/overview'
      : '/app/business/overview';
    
    return <Navigate to={homeRoute} replace />;
  }

  return <>{children}</>;
}