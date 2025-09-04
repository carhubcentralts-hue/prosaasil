const BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:5000";

async function post(url:string, body:any){
  const r = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    credentials: "include", // לצרף קוקיות HttpOnly מהשרת
    body: JSON.stringify(body)
  });
  const data = await r.json().catch(()=> ({}));
  if(!r.ok){ const msg = data?.error || "שגיאת שרת"; throw new Error(msg); }
  return data;
}

export const api = {
  login: (email:string, password:string)=> post("/api/ui/login", {email, password}),
  forgot: (email:string)=> post("/api/auth/forgot", {email}),
  reset: (token:string, password:string)=> post("/api/auth/reset", {token, password}),
};