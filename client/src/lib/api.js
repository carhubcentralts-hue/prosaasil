const BASE = import.meta.env.VITE_API_BASE ?? "";

async function post(url, body){
  const r = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    credentials: "include",           // חשוב! כדי לקבל/לשלוח session cookies
    body: JSON.stringify(body)
  });
  let data=null; try{ data=await r.json(); }catch(_){}
  if(!r.ok) throw new Error(data?.error || "שגיאת שרת");
  return data || {};
}

export const api = {
  login:  (email, password)=> post("/api/auth/login", {email, password}),
  forgot: (email)=> post("/api/auth/forgot", {email}),
  reset:  (token, password)=> post("/api/auth/reset", {token, password}),
};