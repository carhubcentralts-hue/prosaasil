import React, { useState, FormEvent } from "react";
import { auth } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>){
    e.preventDefault(); 
    setErr("");
    try { 
      await auth.login(email, password); 
      setUser({email}); 
    }
    catch { 
      setErr("האימייל או הסיסמה שגויים"); 
    }
  }

  return (
    <div style={{
      minHeight:"100vh", 
      display:"grid", 
      placeItems:"center", 
      direction:"rtl",
      backgroundColor: "#f5f5f5"
    }}>
      <form onSubmit={onSubmit} style={{
        width: "100%", 
        maxWidth: 380, 
        padding: 24, 
        borderRadius: 16,
        boxShadow: "0 10px 30px rgba(0,0,0,.08)", 
        background: "#fff"
      }}>
        <h1 style={{marginBottom:16, fontWeight:700}}>התחברות</h1>
        <label style={{display:"block", marginBottom:8}}>אימייל</label>
        <input 
          value={email} 
          onChange={(e)=>setEmail(e.target.value)} 
          type="email" 
          required
          style={{
            width:"100%", 
            padding:12, 
            marginBottom:12, 
            borderRadius:10, 
            border:"1px solid #ddd",
            boxSizing: "border-box"
          }}
        />
        <label style={{display:"block", marginBottom:8}}>סיסמה</label>
        <input 
          value={password} 
          onChange={(e)=>setPassword(e.target.value)} 
          type="password" 
          required
          style={{
            width:"100%", 
            padding:12, 
            marginBottom:16, 
            borderRadius:10, 
            border:"1px solid #ddd",
            boxSizing: "border-box"
          }}
        />
        {err && <div style={{color:"#c00", marginBottom:12}}>{err}</div>}
        <button type="submit" style={{
          width:"100%", 
          padding:12, 
          borderRadius:10, 
          border:"none", 
          fontWeight:700, 
          cursor:"pointer",
          backgroundColor: "#007bff",
          color: "white"
        }}>כניסה</button>
      </form>
    </div>
  );
}