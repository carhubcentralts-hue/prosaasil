// Simple API client for login functionality
export const api = {
  async login(email, password) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'שגיאת התחברות' }));
      throw new Error(error.message || 'שם משתמש או סיסמה שגויים');
    }

    return await response.json();
  }
};