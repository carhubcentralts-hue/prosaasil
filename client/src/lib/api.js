const API_BASE = 'http://localhost:5001';

export const auth = {
  async login(email, password) {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Login failed');
    }
    
    return data;
  },

  async me() {
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      credentials: 'include',
    });
    
    const data = await response.json();
    return data;
  },

  async logout() {
    const response = await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    
    const data = await response.json();
    return data;
  }
};

export const api = {
  async getCustomers() {
    const response = await fetch(`${API_BASE}/api/crm/customers`, {
      credentials: 'include',
    });
    
    const data = await response.json();
    return data;
  },

  async getCalls() {
    const response = await fetch(`${API_BASE}/api/calls`, {
      credentials: 'include',
    });
    
    const data = await response.json();
    return data;
  },

  async getWhatsAppConversations() {
    const response = await fetch(`${API_BASE}/api/whatsapp/conversations`, {
      credentials: 'include',
    });
    
    const data = await response.json();
    return data;
  }
};