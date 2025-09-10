import { ApiError } from '../types/api';

// FE - fetch מרוכז לפי ההנחיות המדויקות
export async function apiFetch(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {})
  headers.set('Accept','application/json')
  const method = (options.method || 'GET').toUpperCase()
  if (!['GET','HEAD','OPTIONS'].includes(method)) {
    headers.set('Content-Type','application/json')
    headers.set('X-Requested-With','XMLHttpRequest')
    const token = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/)?.[1]
    if (token) headers.set('X-CSRFToken', decodeURIComponent(token))
  }
  return fetch(url, { ...options, headers, credentials:'include' })
}

class HttpClient {
  private baseURL = '/';

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint.startsWith('/') ? endpoint.slice(1) : endpoint}`;
    
    try {
      const response = await apiFetch(url, options);
      
      if (!response.ok) {
        let errorData: ApiError;
        try {
          errorData = await response.json();
        } catch {
          console.error('FE Error:', response.status, await response.text()); // לוגים ברורים לפי ההנחיות
          errorData = {
            error: 'HTTP_ERROR',
            message: `Request failed with status ${response.status}`,
          };
        }
        throw new Error(errorData.message || errorData.error);
      }

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