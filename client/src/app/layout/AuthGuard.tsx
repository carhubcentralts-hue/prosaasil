import { useEffect } from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // Don't show loading screen - proceed with auth check
  // The auth system is designed to never show loading screens
  // If user is not authenticated, redirect to login immediately

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return (
      <Navigate 
        to="/login" 
        state={{ from: location }} 
        replace 
      />
    );
  }

  return <>{children}</>;
}