// Simple Auth Service without external dependencies
export class AuthService {
  static async forgotPassword(email: string): Promise<{ message: string; resetToken?: string }> {
    const response = await fetch('/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'שגיאה בשליחת איפוס סיסמא');
    }

    return response.json();
  }

  static async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const response = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, newPassword }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'שגיאה באיפוס סיסמא');
    }

    return response.json();
  }
}