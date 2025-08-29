import { useState } from "react";
import Input from "./Input.jsx";
export default function PasswordInput({label, error, ...props}){
  const [show,setShow]=useState(false);
  return (
    <div className="space-y-1 relative">
      {label && <label className="text-sm">{label}</label>}
      <input {...props} type={show?"text":"password"}
        className={`w-full px-3 py-2 border rounded-xl min-h-[44px] bg-white focus:outline-none focus:ring-2 focus:ring-accent-500 ${error?'border-red-400':'border-gray-300'}`} />
      {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
      <button type="button" onClick={()=>setShow(v=>!v)}
        className="absolute left-2 top-8 text-sm opacity-70">{show?"הסתר":"הצג"}</button>
    </div>
  );
}