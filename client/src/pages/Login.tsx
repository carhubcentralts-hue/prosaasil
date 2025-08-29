import React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import AuthCard from "../components/AuthCard";
import Input from "../components/ui/Input";
import PasswordInput from "../components/ui/PasswordInput";
import Button from "../components/ui/Button";
import { Toast } from "../components/ui/Toast";
import { api } from "../lib/api";
import { Link } from "react-router-dom";

const schema = z.object({
  email: z.string().email("אימייל לא חוקי"),
  password: z.string().min(8, "סיסמה חייבת 8+")
});

export default function Login(){
  const {register, handleSubmit, formState:{errors, isSubmitting}, setError} =
    useForm<{email:string; password:string}>({resolver: zodResolver(schema)});

  const onSubmit = async (v:{email:string; password:string})=>{
    try{
      const { user } = await api.login(v.email.trim().toLowerCase(), v.password);
      // ניתוב לפי תפקיד
      const target = ["admin","superadmin"].includes(user?.role) ? "/app/admin" : "/app/biz";
      location.href = target;
    } catch(e:any){ setError("password", { message: e.message || "פרטי התחברות שגויים" }); }
  };

  return (
    <AuthCard title="התחברות">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" dir="rtl">
        { (errors.email || errors.password) && <Toast kind="error">בדוק את השדות המסומנים</Toast> }
        <Input label="אימייל" dir="ltr" type="email" placeholder="name@example.com"
               error={errors.email?.message} {...register("email")} />
        <PasswordInput label="סיסמה" placeholder="••••••••"
               error={errors.password?.message} {...register("password")} />
        <Button loading={isSubmitting}>התחבר</Button>
        <div className="flex justify-between text-sm">
          <Link to="/forgot" className="text-blue-600">שכחתי סיסמה</Link>
          <a href="/" className="opacity-70">דף הבית</a>
        </div>
      </form>
    </AuthCard>
  );
}