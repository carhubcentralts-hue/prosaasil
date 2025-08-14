// Authentication service for client
export class AuthService {
  static async login(email: string, password: string) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'שגיאה בהתחברות');
    }

    return response.json();
  }

  static async logout() {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include'
    });
  }

  static async getCurrentUser() {
    const response = await fetch('/api/auth/me', {
      credentials: 'include'
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  }

  static async checkAuth() {
    const response = await fetch('/api/auth/check', {
      credentials: 'include'
    });

    if (!response.ok) {
      return { authenticated: false };
    }

    return response.json();
  }
}