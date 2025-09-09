export interface Business {
  id: number;
  name: string;
  business_type: string;
  phone: string;
  whatsapp: string | null;
  status: 'active' | 'inactive' | 'suspended';
  created_at: string;
  updated_at?: string;
  users?: number;
  // Additional fields for edit functionality
  domain?: string;
  defaultPhoneE164?: string;
  whatsappJid?: string;
  timezone?: string;
  address?: string;
  is_active?: boolean;
  whatsapp_id?: string;
  stats?: {
    users: number;
    leads: number;
    unread: number;
    callsToday: number;
    waToday: number;
  };
}

export interface BusinessUser {
  id: number;
  name: string;
  email: string;
  role: string;
  lastLogin: string;
  businessId: number;
  isActive: boolean;
}

export interface BusinessEditData {
  name: string;
  domain: string;
  defaultPhoneE164: string;
  whatsappJid: string;
  timezone?: string;
  businessHours?: {
    [key: string]: Array<{ from: string; to: string; }>;
  };
  address?: string;
}

export interface ImpersonationData {
  tenantUser: BusinessUser;
  tenant: Business;
  originalUser: any;
}

export interface BusinessActionResponse {
  ok: boolean;
  message?: string;
  data?: any;
}

export interface BusinessCapabilities {
  canEdit: boolean;
  canImpersonate: boolean;
  canSuspend: boolean;
  canResume: boolean;
  canDelete: boolean;
  canResetPassword: boolean;
  canViewUsers: boolean;
  canManageUsers: boolean;
}

export type BusinessAction = 
  | 'edit' 
  | 'impersonate' 
  | 'suspend' 
  | 'resume' 
  | 'delete' 
  | 'resetPassword' 
  | 'view';

export interface BusinessActionHandlers {
  editBusiness: (id: number, data: BusinessEditData) => Promise<BusinessActionResponse>;
  resetPassword: (id: number, userId?: number) => Promise<BusinessActionResponse>;
  impersonate: (id: number) => Promise<ImpersonationData>;
  exitImpersonation: () => Promise<BusinessActionResponse>;
  suspend: (id: number) => Promise<BusinessActionResponse>;
  resume: (id: number) => Promise<BusinessActionResponse>;
  softDelete: (id: number) => Promise<BusinessActionResponse>;
  getCapabilities: (userRole: string) => BusinessCapabilities;
}