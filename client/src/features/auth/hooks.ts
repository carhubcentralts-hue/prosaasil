import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { authApi } from './api';
import { AuthContextType, AuthState } from './types';

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuthState(): AuthState & {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
} {
  const [state, setState] = useState<AuthState>({
    user: null,
    tenant: null,
    isLoading: true,
    isAuthenticated: false,
  });

  const refetch = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await authApi.me();
      setState({
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setState({
        user: null,
        tenant: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await authApi.login({ email, password });
      setState({
        user: response.user,
        tenant: response.tenant,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
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

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { ...state, login, logout, refetch };
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export { AuthContext };