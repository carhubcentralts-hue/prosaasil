export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const auth = {
  me: () => api('/api/auth/me'),
  login: (email: string, password: string) =>
    api('/api/auth/login', { 
      method: 'POST', 
      body: JSON.stringify({ email, password }) 
    }),
  logout: () => api('/api/auth/logout', { method: 'POST' }),
  check: () => api('/api/auth/check')
};

export const crm = {
  getCustomers: (page = 1, limit = 25) => 
    api(`/api/crm/customers?page=${page}&limit=${limit}`),
  addCustomer: (data: any) => 
    api('/api/crm/customers', { method: 'POST', body: JSON.stringify(data) }),
  updateCustomer: (id: number, data: any) => 
    api(`/api/crm/customers/${id}`, { method: 'PUT', body: JSON.stringify(data) })
};

export const calls = {
  getCalls: (page = 1, limit = 25) => 
    api(`/api/calls?page=${page}&limit=${limit}`),
  getCall: (id: number) => 
    api(`/api/calls/${id}`),
  getTranscription: (id: number) => 
    api(`/api/calls/${id}/transcription`)
};

export const whatsapp = {
  getConversations: () => api('/api/whatsapp/conversations'),
  sendMessage: (to: string, message: string) => 
    api('/api/whatsapp/send', { 
      method: 'POST', 
      body: JSON.stringify({ to, message }) 
    }),
  getQR: () => api('/api/whatsapp/qr')
};

export const business = {
  getBusinesses: () => api('/api/admin/businesses'),
  createBusiness: (data: any) => 
    api('/api/admin/businesses', { method: 'POST', body: JSON.stringify(data) }),
  updateBusiness: (id: number, data: any) => 
    api(`/api/admin/businesses/${id}`, { method: 'PUT', body: JSON.stringify(data) })
};