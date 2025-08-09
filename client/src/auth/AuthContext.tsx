import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { auth } from "../lib/api";

type User = { email: string } | null;
const Ctx = createContext<{ user: User, setUser: (u: User)=>void }>({ 
  user: null, 
  setUser: ()=>{} 
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(null);
  
  useEffect(()=>{ 
    auth.me()
      .then((u: any)=>setUser(u.email ? u : null))
      .catch(()=>setUser(null)); 
  },[]);
  
  return (
    <Ctx.Provider value={{user,setUser}}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = ()=> useContext(Ctx);