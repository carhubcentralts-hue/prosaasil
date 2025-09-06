import { ApiError } from '../types/api';

class HttpClient {
  private baseURL = '/';

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint.startsWith('/') ? endpoint.slice(1) : endpoint}`;
    
    const config: RequestInit = {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      // Handle 401 globally - but only redirect if not already on auth pages
      if (response.status === 401) {
        const currentPath = window.location.pathname;
        if (!currentPath.startsWith('/login') && !currentPath.startsWith('/forgot') && !currentPath.startsWith('/reset')) {
          // Clear auth context and redirect to login
          // Use React Router navigation if possible, fallback to window location
          const navigateToLogin = () => {
            if (typeof window !== 'undefined' && window.location) {
              window.location.href = '/login';
            }
          };
          navigateToLogin();
          throw new Error('Unauthorized');
        }
        // For login pages, let the normal error handling continue to get the real error message
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

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const http = new HttpClient();