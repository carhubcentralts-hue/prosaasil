import { ApiError } from '../types/api';

class HttpClient {
  private baseURL = '/';

  private getCSRFToken(): string | null {
    // מחפש CSRF token מ-cookie XSRF-TOKEN
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'XSRF-TOKEN') {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  private async ensureCSRFToken(): Promise<void> {
    // אם אין CSRF token, נקבל אחד מהשרת
    if (!this.getCSRFToken()) {
      try {
        await fetch('/api/auth/csrf-token', { credentials: 'include' });
      } catch (error) {
        console.warn('Failed to get CSRF token:', error);
      }
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint.startsWith('/') ? endpoint.slice(1) : endpoint}`;
    
    // וודא שיש CSRF token לפני קריאות POST/PUT/PATCH/DELETE
    if (options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method)) {
      await this.ensureCSRFToken();
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...options.headers as Record<string, string>,
    };

    // הוסף CSRF token לכל הקריאות הלא-GET
    const csrfToken = this.getCSRFToken();
    if (csrfToken && options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method)) {
      headers['X-CSRFToken'] = csrfToken;
    }
    
    const config: RequestInit = {
      credentials: 'include',
      headers,
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      // Handle 401 - FIXED: Don't auto-redirect during auth check
      if (response.status === 401) {
        const currentPath = window.location.pathname;
        
        // Don't auto-redirect for auth endpoints - let the auth system handle it
        const isAuthEndpoint = endpoint.includes('/api/auth/');
        
        if (!isAuthEndpoint && !currentPath.startsWith('/login') && !currentPath.startsWith('/forgot') && !currentPath.startsWith('/reset')) {
          // Only redirect for non-auth API calls
          const navigateToLogin = () => {
            if (typeof window !== 'undefined' && window.location) {
              window.location.href = '/login';
            }
          };
          navigateToLogin();
          throw new Error('Unauthorized');
        }
        // For auth endpoints and login pages, let the normal error handling continue
      }

      if (!response.ok) {
        let errorData: ApiError;
        try {
          errorData = await response.json();
        } catch {
          errorData = {
            error: 'HTTP_ERROR',
            message: `Request failed with status ${response.status}`,
          };
        }
        throw new Error(errorData.message || errorData.error);
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      
      return {} as T;
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Network error occurred');
    }
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, { 
      method: 'DELETE',
      body: data ? JSON.stringify(data) : undefined,
    });
  }
}

export const http = new HttpClient();