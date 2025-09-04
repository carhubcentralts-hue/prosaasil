import React from "react";
export function Toast({ kind="info", children }:{kind?: "info"|"error"|"success"; children:React.ReactNode}){
  const map:any = { info:"bg-blue-50 text-blue-700", error:"bg-red-50 text-red-700", success:"bg-green-50 text-green-700" };
  return <div className={`p-2 rounded-xl text-sm ${map[kind]}`}>{children}</div>;
}