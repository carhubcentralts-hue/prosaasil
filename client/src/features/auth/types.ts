import { User, Tenant } from '../../types/api';

export interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  impersonating?: boolean;
  original_user?: User | null;
}

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
}

export type UserRole = 'admin' | 'manager' | 'business';