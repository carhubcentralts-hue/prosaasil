import React, { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import AuthCard from "../components/AuthCard";
import PasswordInput from "../components/ui/PasswordInput";
import Button from "../components/ui/Button";
import { Toast } from "../components/ui/Toast";
import { api } from "../lib/api";

export default function Reset(){
  const [sp] = useSearchParams();
  const token = sp.get("token") || "";
  const [p1,setP1] = useState(""); const [p2,setP2]=useState("");
  const [msg,setMsg] = useState<string|null>(null);
  const [err,setErr] = useState<string|null>(null);
  const [loading,setLoading] = useState(false);

  const submit = async (e:React.FormEvent)=>{
    e.preventDefault(); setErr(null);
    if(p1.length < 8) return setErr("סיסמה חייבת 8+");
    if(p1 !== p2) return setErr("הסיסמאות אינן תואמות");
    setLoading(true);
    try{
      await api.reset(token, p1);
      setMsg("הסיסמה עודכנה! מעביר למסך התחברות…");
      setTimeout(()=> location.href="/auth/login", 1200);
    }catch(e:any){ setErr(e.message || "טוקן לא תקף/פג"); }
    finally{ setLoading(false); }
  };

  return (
    <AuthCard title="איפוס סיסמה">
      <form onSubmit={submit} className="space-y-3" dir="rtl">
        {msg && <Toast kind="success">{msg}</Toast>}
        {err && <Toast kind="error">{err}</Toast>}
        <PasswordInput label="סיסמה חדשה" value={p1} onChange={e=>setP1(e.target.value)} />
        <PasswordInput label="אימות סיסמה" value={p2} onChange={e=>setP2(e.target.value)} />
        <Button loading={loading}>שמור סיסמה חדשה</Button>
        <div className="text-sm text-center"><Link to="/login" className="text-blue-600">חזרה להתחברות</Link></div>
      </form>
    </AuthCard>
  );
}