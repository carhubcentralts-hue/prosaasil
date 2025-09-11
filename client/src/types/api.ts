// API Response Types
export interface User {
  id: number;
  email: string;
  role: 'admin' | 'manager' | 'business';
  name?: string;
  business_id?: number;
}

export interface Tenant {
  id: number;
  name: string;
}

export interface AuthResponse {
  user: User;
  tenant: Tenant;
  impersonating?: boolean;
  original_user?: User;
}

export interface StatusResponse {
  twilio: { up: boolean };
  baileys: { up: boolean };
  db: { up: boolean };
  latency: {
    stt: number;
    ai: number;
    tts: number;
  };
}

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

export interface ActivityItem {
  ts: string;
  type: 'whatsapp' | 'call';
  tenant: string;
  preview: string;
  provider?: string;
}

export interface ActivityResponse {
  items: ActivityItem[];
}

// Request Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
}

// Error Types
export interface ApiError {
  error: string;
  message: string;
}