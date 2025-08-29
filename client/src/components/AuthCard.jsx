import React from "react";
import Brand from "./Brand.jsx";

export default function AuthCard({title, children}){
  return (
    <div className="min-h-screen grid place-items-center px-4"
         style={{ background: "radial-gradient(80% 60% at 50% -10%, #e0e7ff 0%, transparent 60%)" }}>
      <div className="w-full max-w-md bg-white rounded-2xl shadow-soft p-6 space-y-5">
        <div className="flex items-center justify-between">
          <Brand/>
          <div className="text-sm opacity-60">כניסה למערכת</div>
        </div>
        <div className="text-2xl font-bold">{title}</div>
        {children}
        <div className="text-[11px] opacity-60 text-center pt-2">© שי דירות ומשרדים</div>
      </div>
    </div>
  );
}