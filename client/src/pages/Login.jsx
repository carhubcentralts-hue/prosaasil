import { useState } from "react";
import { Link } from "react-router-dom";
import AuthCard from "../components/AuthCard.jsx";
import Input from "../components/ui/Input.jsx";
import PasswordInput from "../components/ui/PasswordInput.jsx";
import Button from "../components/ui/Button.jsx";
import { Toast } from "../components/ui/Toast.jsx";
import { api } from "../lib/api.js";

export default function Login(){
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [err,setErr]=useState(null);
  const [loading,setLoading]=useState(false);

  const submit=async(e)=>{
    e.preventDefault(); setErr(null);
    if(!/^\S+@\S+\.\S+$/.test(email)) return setErr("אימייל לא חוקי");
    if(password.length<8) return setErr("סיסמה חייבת 8+ תווים");
    setLoading(true);
    try{
      const { user } = await api.login(email.trim().toLowerCase(), password);
      const target = (user && ["admin","superadmin"].includes(user.role)) ? "/app/admin" : "/app/biz";
      location.href = target; // ניתוב אחרי התחברות
    }catch(e){ setErr(e.message || "שם משתמש או סיסמה שגויים"); }
    finally{ setLoading(false); }
  };

  return (
    <AuthCard title="התחברות">
      <form onSubmit={submit} className="space-y-3" dir="rtl">
        {err && <Toast kind="error">{err}</Toast>}
        <Input label="אימייל" dir="ltr" type="email" placeholder="name@example.com"
               value={email} onChange={e=>setEmail(e.target.value)} />
        <PasswordInput label="סיסמה" placeholder="••••••••"
               value={password} onChange={e=>setPassword(e.target.value)} />
        <Button loading={loading}>התחבר</Button>
        <div className="flex justify-between text-sm">
          <span className="text-accent-500 cursor-pointer">שכחתי סיסמה</span>
          <a href="/" className="opacity-70">דף הבית</a>
        </div>
      </form>
    </AuthCard>
  );
}