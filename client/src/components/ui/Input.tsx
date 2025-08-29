import React from "react";
import cn from "classnames";

export default function Input(
  {label, error, ...props}:
  React.InputHTMLAttributes<HTMLInputElement> & {label?:string; error?:string}
){
  return (
    <div className="space-y-1">
      {label && <label className="text-sm">{label}</label>}
      <input
        {...props}
        className={cn(
          "w-full px-3 py-2 border rounded-xl min-h-[44px] bg-white",
          error ? "border-red-400" : "border-gray-300",
          "focus:outline-none focus:ring-2 focus:ring-accent-500"
        )}
      />
      {error && <div className="text-xs text-red-600">{error}</div>}
    </div>
  );
}