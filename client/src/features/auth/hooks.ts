import React, { createContext, useContext, useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { authApi } from './api';
import { AuthContextType, AuthState } from './types';

// 🎯 Advanced Context with proper typing  
const AuthContext = createContext<AuthContextType | null>(null);

export function useAuthState(): AuthState & {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
} {
  const [state, setState] = useState<AuthState>({
    user: null,
    tenant: null,
    isLoading: false, // Start as false to prevent loading screen
    isAuthenticated: false,
  });

  // 🔥 Advanced optimization: Stable ref for lifecycle management
  const isMountedRef = useRef(true);
  const isInitializedRef = useRef(false);

  const refetch = useCallback(async () => {
    if (!isMountedRef.current) return; // Prevent memory leaks
    
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await authApi.me();
      if (!isMountedRef.current) return; // Check again after async
      
      setState({
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      if (!isMountedRef.current) return;
      
      setState({
        user: null,
        tenant: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []); // 🎯 Empty deps - stable function

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await authApi.login({ email, password });
      console.log('🔍 Login response:', response);
      
      const newState = {
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
      };
      
      setState(newState);
      console.log('🔄 Auth state updated:', newState);
    } catch (error) {
      console.error('❌ Login error:', error);
      setState(prev => ({ ...prev, isLoading: false }));
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      await authApi.logout();
    } catch (error) {
      // Continue with logout even if API call fails
    } finally {
      setState({
        user: null,
        tenant: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []);

  // 🚀 Conditional initialization - no refetch on auth pages
  useEffect(() => {
    if (!isInitializedRef.current) {
      isInitializedRef.current = true;
      
      // Only refetch if we're in protected routes
      const currentPath = window.location.pathname;
      if (currentPath.startsWith('/app/')) {
        console.log('🔄 Refetching auth state for protected route:', currentPath);
        refetch();
      } else {
        console.log('🚫 Skipping refetch on auth page:', currentPath);
      }
    }
    
    return () => {
      isMountedRef.current = false; // Cleanup
    };
  }, []); // 🎯 Run only once - no dependencies

  // 🎯 Stable return object to prevent unnecessary re-renders
  return useMemo(() => ({
    ...state,
    login,
    logout,
    refetch
  }), [state.user, state.tenant, state.isLoading, state.isAuthenticated, login, logout, refetch]);
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

// 🚀 Simple and stable AuthProvider
export const AuthProvider = React.memo(({ children }: { children: React.ReactNode }) => {
  const authState = useAuthState();
  
  return React.createElement(
    AuthContext.Provider,
    { value: authState },
    children
  );
});

AuthProvider.displayName = 'AuthProvider';

export { AuthContext };