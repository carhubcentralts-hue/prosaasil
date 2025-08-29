// API client with credentials support
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
    ...options,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    // Response might not be JSON
  }

  if (!response.ok) {
    throw new Error(data?.message || data?.error || 'שגיאת שרת');
  }

  return data || {};
}

export const api = {
  login: (email, password) => 
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
    
  forgot: (email) => 
    request('/api/auth/forgot', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
    
  reset: (token, password) => 
    request('/api/auth/reset', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    }),
};