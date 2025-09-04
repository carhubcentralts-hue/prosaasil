import { httpService } from '../../services/http';
import { AuthResponse, LoginForm, ForgotPasswordForm, ResetPasswordForm } from '../../types/api';

export const authApi = {
  // Get current user session
  async getCurrentUser(): Promise<AuthResponse> {
    return httpService.get<AuthResponse>('/auth/me');
  },

  // Login with email and password
  async login(credentials: LoginForm): Promise<AuthResponse> {
    return httpService.post<AuthResponse>('/auth/login', credentials);
  },

  // Logout and clear session
  async logout(): Promise<{ ok: boolean }> {
    return httpService.post<{ ok: boolean }>('/auth/logout');
  },

  // Request password reset
  async forgotPassword(data: ForgotPasswordForm): Promise<{ ok: boolean }> {
    return httpService.post<{ ok: boolean }>('/auth/forgot', data);
  },

  // Reset password with token
  async resetPassword(data: ResetPasswordForm): Promise<{ ok: boolean }> {
    return httpService.post<{ ok: boolean }>('/auth/reset', data);
  },
};