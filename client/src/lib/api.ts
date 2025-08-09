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
  me:    () => api('/api/auth/me'),
  login: (email: string, password: string) =>
           api('/api/auth/login', { method:'POST', body: JSON.stringify({ email, password }) }),
  logout: () => api('/api/auth/logout', { method:'POST' })
};