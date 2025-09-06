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
  
  // Login user
  login: (data: LoginRequest) => 
    http.post<AuthResponse>('/api/ui/login', data),
  
  // Logout user
  logout: () => http.post<{ ok: boolean }>('/api/auth/logout'),
  
  // Forgot password
  forgot: (data: ForgotPasswordRequest) => 
    http.post<{ ok: boolean }>('/api/auth/forgot', data),
  
  // Reset password
  reset: (data: ResetPasswordRequest) => 
    http.post<{ ok: boolean }>('/api/auth/reset', data),
};