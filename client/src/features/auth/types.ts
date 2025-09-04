import { User, Business } from '../../types/api';

export interface AuthContextType {
  user: User | null;
  business: Business | null;
  permissions: Record<string, boolean>;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

export interface AuthState {
  user: User | null;
  business: Business | null;
  permissions: Record<string, boolean>;
  isLoading: boolean;
}