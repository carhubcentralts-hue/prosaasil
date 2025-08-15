/**
 * Unified API client for all backend requests
 */

const base = (import.meta as any).env?.VITE_API_URL || window.location.origin;

export async function api(path: string, init?: RequestInit) {
  const res = await fetch(base + path, {
    credentials: "include",
    headers: { 
      "Content-Type": "application/json", 
      ...(init?.headers || {}) 
    },
    ...init,
  });
  
  if (!res.ok) {
    throw new Error(await res.text());
  }
  
  return res.headers.get("content-type")?.includes("application/json")
    ? res.json()
    : res.text();
}

// Convenience methods
export const GET = (path: string) => api(path);
export const POST = (path: string, data?: any) => api(path, { method: "POST", body: JSON.stringify(data) });
export const PUT = (path: string, data?: any) => api(path, { method: "PUT", body: JSON.stringify(data) });
export const DELETE = (path: string) => api(path, { method: "DELETE" });