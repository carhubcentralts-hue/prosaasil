let csrfToken: string | null = null;

// Auto-refresh CSRF token on 403
export async function refreshCSRF(): Promise<void> {
  try {
    const response = await fetch('/api/auth/csrf', { 
      method: 'GET', 
      credentials: 'include' 
    });
    if (response.ok) {
      const data = await response.json();
      csrfToken = data.csrfToken;
      console.log('✅ CSRF token refreshed');
    }
  } catch (error) {
    console.error('❌ Failed to refresh CSRF token:', error);
  }
}

// Get CSRF token from cookie or cached
function getCSRFToken(): string | null {
  if (csrfToken) return csrfToken;
  
  // Try XSRF-TOKEN first (as configured on server), then fallback to _csrf_token
  let token = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/)?.[1];
  if (!token) {
    token = document.cookie.match(/(?:^|;\s*)_csrf_token=([^;]+)/)?.[1];
  }
  if (token) {
    csrfToken = decodeURIComponent(token);
  }
  return csrfToken;
}

// Enhanced fetch with CSRF and retry logic
export async function apiFetch(url: string, options: RequestInit = {}, retryCount = 0): Promise<Response> {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  
  const method = (options.method || 'GET').toUpperCase();
  
  // Set Content-Type for POST/PUT/PATCH/DELETE requests with JSON body
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    // Only set Content-Type if not already set and we have a body
    if (!headers.get('Content-Type') && options.body) {
      // Don't override if it's FormData, Blob, or URLSearchParams
      const body = options.body;
      if (!(body instanceof FormData) && !(body instanceof Blob) && !(body instanceof URLSearchParams)) {
        headers.set('Content-Type', 'application/json');
      }
    }
    headers.set('X-Requested-With', 'XMLHttpRequest');
  }
  
  // Add CSRF for write operations (excluding specific routes that don't need it)
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && 
      !url.includes('/api/auth/logout') && 
      !url.includes('/api/webhooks/') && 
      !url.includes('/healthz')) {
    
    const token = getCSRFToken();
    if (token) {
      headers.set('X-CSRFToken', token);
    }
  }
  
  const response = await fetch(url, { 
    ...options, 
    headers, 
    credentials: 'include' 
  });
  
  // Handle 403 with CSRF refresh and retry (once only)
  if (response.status === 403 && retryCount === 0) {
    console.log('🔄 403 detected, refreshing CSRF and retrying...');
    // Clear cached token before refresh
    csrfToken = null;
    await refreshCSRF();
    return apiFetch(url, options, 1); // Retry once
  }
  
  return response;
}

class HttpClient {
  private baseURL = '/';

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint.startsWith('/') ? endpoint.slice(1) : endpoint}`;
    
    try {
      const response = await apiFetch(url, options);
      
      if (!response.ok) {
        const raw = await response.text();
        let errorData: any = {};
        
        try {
          errorData = raw ? JSON.parse(raw) : {};
        } catch {
          errorData = { error: raw || 'Unknown error', message: raw || 'Request failed' };
        }
        
        // Ensure proper error shape {error, message, hint?}
        const error = errorData.error || errorData.message || `HTTP ${response.status}`;
        const message = errorData.message || errorData.error || raw || 'Request failed';
        const hint = errorData.hint;
        
        console.error('FE Error:', response.status, { error, message, hint });
        
        // Create structured error
        const apiError = new Error(message);
        (apiError as any).status = response.status;
        (apiError as any).error = error;
        (apiError as any).hint = hint;
        
        throw apiError;
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

  async get<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
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

// Initialize CSRF token on app start (after login)
export async function initializeAuth(): Promise<void> {
  try {
    await refreshCSRF();
  } catch (error) {
    console.warn('Failed to initialize CSRF token:', error);
  }
}