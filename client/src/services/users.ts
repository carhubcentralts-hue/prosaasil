import { http } from './http';

// User Types
export interface User {
  id: number;
  name: string;
  email: string;
  role: 'admin' | 'business_owner' | 'business_agent' | 'read_only';
  business_id: number;
  status: 'active' | 'inactive' | 'pending';
  created_at: string;
  last_login?: string;
}

export interface Business {
  id: number;
  name: string;
  phone_e164?: string;
  status: 'active' | 'inactive';
  created_at: string;
}

// Users Service
class UsersService {
  // Users Management
  async getUsers(params: {
    tenant?: number;
    q?: string;
    role?: string;
    status?: string;
  } = {}): Promise<{ items: User[]; total: number }> {
    const query = new URLSearchParams();
    if (params.tenant) query.set('tenant', params.tenant.toString());
    if (params.q) query.set('q', params.q);
    if (params.role) query.set('role', params.role);
    if (params.status) query.set('status', params.status);
    
    return http.get(`/api/admin/users?${query}`);
  }

  async inviteUser(data: {
    name: string;
    email: string;
    role: string;
    business_id?: number;
  }): Promise<{ ok: boolean; message: string; user_id: number }> {
    return http.post('/api/admin/users', data);
  }

  async updateUser(userId: number, data: {
    name?: string;
    role?: string;
    status?: string;
  }): Promise<User> {
    return http.patch(`/api/admin/users/${userId}`, data);
  }

  async resetPassword(userId: number): Promise<{ ok: boolean; message: string }> {
    return http.post(`/api/admin/users/${userId}/reset-password`, {});
  }

  // Impersonation
  async impersonateBusiness(businessId: number): Promise<{
    ok: boolean;
    tenant: Business;
    original_user: User;
  }> {
    return http.post(`/api/admin/businesses/${businessId}/impersonate`, {});
  }

  async exitImpersonation(): Promise<{ ok: boolean; user: User }> {
    return http.post('/api/admin/impersonate/exit', {});
  }

  // Business Management
  async getBusinesses(): Promise<{ items: Business[]; total: number }> {
    return http.get('/api/admin/businesses');
  }

  async createBusiness(data: {
    name: string;
    phone_e164?: string;
  }): Promise<Business> {
    return http.post('/api/admin/businesses', data);
  }

  async updateBusiness(businessId: number, data: {
    name?: string;
    phone_e164?: string;
    status?: string;
  }): Promise<Business> {
    return http.patch(`/api/admin/businesses/${businessId}`, data);
  }
}

export const usersService = new UsersService();