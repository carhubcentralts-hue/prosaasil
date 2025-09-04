import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import { authApi } from './api';
import { AuthContextType, AuthState } from './types';
import { User, Business } from '../../types/api';

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    business: null,
    permissions: {},
    isLoading: true,
  });

  const refreshAuth = async () => {
    try {
      setState(prev => ({ ...prev, isLoading: true }));
      const response = await authApi.getCurrentUser();
      
      setState({
        user: response.user,
        business: response.business || null,
        permissions: response.permissions || {},
        isLoading: false,
      });
    } catch (error) {
      console.error('Auth refresh failed:', error);
      setState({
        user: null,
        business: null,
        permissions: {},
        isLoading: false,
      });
    }
  };

  const login = async (email: string, password: string) => {
    try {
      const response = await authApi.login({ email, password });
      
      setState({
        user: response.user,
        business: response.business || null,
        permissions: response.permissions || {},
        isLoading: false,
      });
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout API failed:', error);
    } finally {
      setState({
        user: null,
        business: null,
        permissions: {},
        isLoading: false,
      });
    }
  };

  useEffect(() => {
    refreshAuth();
  }, []);

  const value: AuthContextType = {
    user: state.user,
    business: state.business,
    permissions: state.permissions,
    isLoading: state.isLoading,
    isAuthenticated: !!state.user,
    login,
    logout,
    refreshAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}