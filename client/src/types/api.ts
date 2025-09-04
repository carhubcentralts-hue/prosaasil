// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// User & Auth Types
export interface User {
  id: number;
  email: string;
  name: string;
  role: 'admin' | 'manager' | 'business';
  business_id?: number;
  enabled: boolean;
  created_at: string;
}

export interface Business {
  id: number;
  name: string;
  phone?: string;
  email?: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  business?: Business;
  permissions?: Record<string, boolean>;
}

// Dashboard Types
export interface DashboardStats {
  calls: {
    today: number;
    last7d: number;
    avgHandleSec: number;
  };
  whatsapp: {
    today: number;
    last7d: number;
    unread: number;
  };
  revenue: {
    thisMonth: number;
    ytd: number;
  };
}

export interface DashboardActivity {
  items: Array<{
    ts: string;
    type: 'whatsapp' | 'call';
    leadId: number;
    preview: string;
    provider: string;
  }>;
}

export interface SystemStatus {
  twilio: { up: boolean };
  baileys: { up: boolean };
  db: { up: boolean };
  latency: {
    stt: number;
    ai: number;
    tts: number;
  };
}

// Form Types
export interface LoginForm {
  email: string;
  password: string;
  remember?: boolean;
}

export interface ForgotPasswordForm {
  email: string;
}

export interface ResetPasswordForm {
  token: string;
  newPassword: string;
  confirmPassword: string;
}