import React, { useState } from "react";
import AuthCard from "../components/AuthCard";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import { Toast } from "../components/ui/Toast";
import { api } from "../lib/api";
import { Link } from "react-router-dom";

export default function Forgot(){
  const [email,setEmail] = useState("");
  const [sent,setSent] = useState(false);
  const [err,setErr] = useState<string|null>(null);
  const [loading,setLoading] = useState(false);

  const submit = async (e:React.FormEvent)=>{
    e.preventDefault(); setErr(null); setLoading(true);
    try{ await api.forgot(email.trim().toLowerCase()); setSent(true); }
    catch(e:any){ setErr("שגיאה בשליחה, נסה שוב"); }
    finally{ setLoading(false); }
  };

  return (
    <AuthCard title="שחזור סיסמה">
      <form onSubmit={submit} className="space-y-3" dir="rtl">
        {err && <Toast kind="error">{err}</Toast>}
        {sent
          ? <Toast kind="success">אם האימייל קיים — נשלח קישור איפוס.</Toast>
          : <>
              <Input label="אימייל" dir="ltr" type="email" placeholder="name@example.com"
                     value={email} onChange={e=>setEmail(e.target.value)} />
              <Button loading={loading}>שלח קישור איפוס</Button>
            </>
        }
        <div className="text-sm text-center"><Link to="/login" className="text-blue-600">חזרה להתחברות</Link></div>
      </form>
    </AuthCard>
  );
}