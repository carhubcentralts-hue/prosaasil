import React, { useState } from "react";
import Input from "./Input";

export default function PasswordInput(
  props: React.InputHTMLAttributes<HTMLInputElement> & {label?:string; error?:string}
){
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input {...props} type={show ? "text" : "password"} />
      <button type="button"
        onClick={()=>setShow(v=>!v)}
        className="absolute left-2 top-1/2 -translate-y-1/2 text-sm opacity-70">
        {show ? "הסתר" : "הצג"}
      </button>
    </div>
  );
}