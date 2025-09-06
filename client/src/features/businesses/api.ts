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
  }): Promise<{ businesses: Business[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.pageSize) searchParams.set('pageSize', params.pageSize.toString());
    if (params?.query) searchParams.set('query', params.query);
    if (params?.status) searchParams.set('status', params.status);

    return http.get(`/api/admin/businesses?${searchParams}`);
  }

  // Get single business details
  async getBusiness(id: number): Promise<Business> {
    return http.get(`/api/admin/business/${id}`);
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

  // Impersonate business  
  async impersonate(id: number): Promise<ImpersonationData> {
    // First try direct fetch with proper credentials
    const response = await fetch(`/api/admin/login-as-business/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'include', // Important for cookies
      body: JSON.stringify({
        _idempotencyKey: this.generateIdempotencyKey()
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Impersonation failed:', response.status, errorText);
      throw new Error(`שגיאה בהתחזות: ${response.status}`);
    }

    return response.json();
  }

  // Exit impersonation
  async exitImpersonation(): Promise<BusinessActionResponse> {
    const response = await fetch('/admin/stop-impersonate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'include' // Important for cookies
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Exit impersonation failed:', response.status, errorText);
      throw new Error(`שגיאה ביציאה מהתחזות: ${response.status}`);
    }

    return response.json();
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