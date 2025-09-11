import { http } from '../../services/http';
import { 
  AuthResponse, 
  LoginRequest, 
  ForgotPasswordRequest, 
  ResetPasswordRequest 
} from '../../types/api';

export const authApi = {
  // Get current user info
  me: () => http.get<AuthResponse>('/api/auth/me'),
  
  // Get CSRF token (for refreshing token after login/bootstrap)
  csrf: () => http.get<{ csrfToken: string }>('/api/auth/csrf'),
  
  // Login user
  login: (data: LoginRequest) => 
    http.post<AuthResponse>('/api/auth/login', data),
  
  // Logout user
  logout: () => http.post<{ ok: boolean }>('/api/auth/logout'),
  
  // Forgot password
  forgot: (data: ForgotPasswordRequest) => 
    http.post<{ ok: boolean }>('/api/auth/forgot', data),
  
  // Reset password
  reset: (data: ResetPasswordRequest) => 
    http.post<{ ok: boolean }>('/api/auth/reset', data),
};