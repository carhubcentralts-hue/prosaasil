/**
 * Page Guard - Protects routes based on page permissions
 * הנחיית-על: בקרת גישה לדפים
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useUserContext } from './useUserContext';

interface PageGuardProps {
  pageKey: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function PageGuard({ pageKey, children, fallback }: PageGuardProps) {
  const { context, loading, canAccessPage } = useUserContext();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!context) {
    return <Navigate to="/login" replace />;
  }

  if (!canAccessPage(pageKey)) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return <Navigate to="/app/forbidden" replace />;
  }

  return <>{children}</>;
}

/**
 * Hook version of PageGuard for conditional rendering
 */
export function usePageGuard(pageKey: string) {
  const { context, loading, canAccessPage } = useUserContext();

  return {
    canAccess: canAccessPage(pageKey),
    loading,
    isAuthenticated: !!context,
  };
}
