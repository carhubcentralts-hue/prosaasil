import { http } from '../../services/http';
import { Business, BusinessEditData, BusinessUser, BusinessActionResponse, ImpersonationData } from './types';

export class BusinessAPI {
  // Generate idempotency key for safe retries
  private generateIdempotencyKey(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  // Get all businesses with filters
  async getBusinesses(params?: {
    page?: number;
    pageSize?: number;
    query?: string;
    status?: string;
  }): Promise<{ items: Business[]; total: number; page: number; pageSize: number }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.pageSize) searchParams.set('pageSize', params.pageSize.toString());
    if (params?.query) searchParams.set('query', params.query);
    if (params?.status) searchParams.set('status', params.status);

    console.log("🔄 GET /api/admin/businesses - REAL DATA ENDPOINT");
    return http.get(`/api/admin/businesses?${searchParams}`);
  }

  // Get single business details
  async getBusiness(id: number): Promise<Business> {
    return http.get(`/api/admin/business/${id}`);
  }

  // Get business overview (Admin View) - לפי ההנחיות המדויקות
  async getBusinessOverview(id: number): Promise<any> {
    console.log(`🔄 GET /api/admin/businesses/${id}/overview - Admin View (קריא בלבד)`);
    return http.get(`/api/admin/businesses/${id}/overview`);
  }

  // Get business users
  async getBusinessUsers(id: number): Promise<BusinessUser[]> {
    return http.get(`/api/admin/businesses/${id}/users`);
  }

  // Edit business
  async editBusiness(id: number, data: BusinessEditData): Promise<BusinessActionResponse> {
    return http.put(`/api/admin/business/${id}`, {
      ...data,
      _idempotencyKey: this.generateIdempotencyKey()
    });
  }

  // Create new business
  async createBusiness(data: BusinessEditData): Promise<BusinessActionResponse> {
    return http.post('/api/admin/business', {
      ...data,
      _idempotencyKey: this.generateIdempotencyKey()
    });
  }

  // Reset business password (owner or specific user)
  async resetPassword(id: number, password: string): Promise<BusinessActionResponse> {
    return http.post(`/api/admin/business/${id}/change-password`, {
      password,
      _idempotencyKey: this.generateIdempotencyKey()
    });
  }

  // Impersonate business - עם CSRF תקין לפי ההנחיות
  async impersonate(id: number): Promise<{ ok: boolean; tenant_id: number }> {
    console.log(`🔄 Calling impersonate API for business ${id}`);
    return http.post(`/api/admin/businesses/${id}/impersonate`, {});
  }

  // Exit impersonation - עם CSRF תקין לפי ההנחיות
  async exitImpersonation(): Promise<BusinessActionResponse> {
    return http.post('/api/admin/impersonate/exit', {});
  }

  // Suspend business
  async suspend(id: number): Promise<BusinessActionResponse> {
    return http.patch(`/api/admin/businesses/${id}/status`, {
      status: 'suspended',
      _idempotencyKey: this.generateIdempotencyKey()
    });
  }

  // Resume business
  async resume(id: number): Promise<BusinessActionResponse> {
    return http.patch(`/api/admin/businesses/${id}/status`, {
      status: 'active',
      _idempotencyKey: this.generateIdempotencyKey()
    });
  }

  // Soft delete business
  async softDelete(id: number): Promise<BusinessActionResponse> {
    return http.delete(`/api/admin/businesses/${id}`);
  }
}

export const businessAPI = new BusinessAPI();