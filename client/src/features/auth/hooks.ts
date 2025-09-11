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
    isLoading: true, // FIXED: Show loading during initial auth check
    isAuthenticated: false,
    original_user: null,
  });

  // 🔥 Advanced optimization: Stable ref for lifecycle management
  const isMountedRef = useRef(true);
  const isInitializedRef = useRef(false);

  const refetch = useCallback(async () => {
    if (!isMountedRef.current) return; // Prevent memory leaks
    
    // Don't show loading screen on refetch
    try {
      const response = await authApi.me();
      if (!isMountedRef.current) return; // Check again after async
      
      setState({
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
        impersonating: response.impersonating || false,
        original_user: response.original_user || null,
      });
    } catch (error) {
      if (!isMountedRef.current) return;
      
      setState({
        user: null,
        tenant: null,
        isLoading: false,
        isAuthenticated: false,
        original_user: null,
      });
    }
  }, []); // 🎯 Empty deps - stable function

  const login = useCallback(async (email: string, password: string) => {
    // Show brief loading only during login
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await authApi.login({ email, password });
      console.log('🔍 Login response:', response);
      
      // Refresh CSRF token after login (per guidelines)
      try {
        await authApi.csrf();
        console.log('✅ CSRF token refreshed after login');
      } catch (csrfError) {
        console.warn('⚠️ CSRF refresh failed (non-critical):', csrfError);
      }
      
      const newState = {
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
        impersonating: response.impersonating || false,
        original_user: response.original_user || null,
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
    // No loading screen on logout
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
        original_user: null,
      });
    }
  }, []);

  // 🚀 Automatic session check on initialization
  useEffect(() => {
    if (!isInitializedRef.current) {
      isInitializedRef.current = true;
      
      const checkExistingSession = async () => {
        // Always refresh CSRF token first (critical for first-time login)
        try {
          await authApi.csrf();
          console.log('✅ CSRF token refreshed on bootstrap');
        } catch (csrfError) {
          console.warn('⚠️ CSRF refresh failed (non-critical):', csrfError);
        }
        
        try {
          console.log('🔍 Checking for existing session...');
          const authData = await authApi.me();
          if (!isMountedRef.current) return;
          
          setState({
            user: authData.user,
            tenant: authData.tenant,
            isLoading: false,
            isAuthenticated: true,
            impersonating: authData.impersonating || false,
            original_user: authData.original_user || null
          });
          console.log('✅ Session restored:', { user: authData.user.email, role: authData.user.role });
        } catch (error) {
          if (!isMountedRef.current) return;
          console.log('❌ No valid session found');
          setState(prev => ({ ...prev, isLoading: false }));
        }
      };
      
      checkExistingSession();
      console.log('🟢 Auth system initialized');
    }
    
    return () => {
      isMountedRef.current = false; // Cleanup
    };
  }, []);

  // 🎯 Stable return object to prevent unnecessary re-renders
  return useMemo(() => ({
    ...state,
    login,
    logout,
    refetch
  }), [state.user, state.tenant, state.isLoading, state.isAuthenticated, state.impersonating, state.original_user, login, logout, refetch]);
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