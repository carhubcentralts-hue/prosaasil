import { ApiError } from '../types/api';

// FE - fetch מרוכז לפי ההנחיות המדויקות
export async function apiFetch(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {})
  headers.set('Accept','application/json')
  const method = (options.method || 'GET').toUpperCase()
  if (!['GET','HEAD','OPTIONS'].includes(method)) {
    headers.set('Content-Type','application/json')
    headers.set('X-Requested-With','XMLHttpRequest')
    // Try both tokens - debug what's actually available
    let token = document.cookie.match(/(?:^|;\s*)_csrf_token=([^;]+)/)?.[1]
    if (!token) {
      token = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/)?.[1]
    }
    if (token) {
      console.log('🔧 Using CSRF token:', token.substring(0, 16) + '...')
      headers.set('X-CSRFToken', decodeURIComponent(token))
    } else {
      console.warn('⚠️ No CSRF token found in cookies!')
    }
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
        // ✅ תיקון: קרא את הbody פעם אחת בלבד למנוע "Body is disturbed or locked"
        const raw = await response.text();
        let msg = `Request failed with status ${response.status}`;
        try {
          const j = raw ? JSON.parse(raw) : null;
          msg = j?.message || j?.error || raw || msg;
        } catch {
          // If parsing fails, use raw text or status message
        }
        console.error('FE Error:', response.status, msg); // לוגים ברורים לפי ההנחיות
        throw new Error(msg);
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