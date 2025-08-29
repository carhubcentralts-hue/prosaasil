import React from "react";

export default function Button({children, loading, className="", ...props}){
  return (
    <button {...props}
      disabled={props.disabled || loading}
      className={`w-full min-h-[44px] rounded-2xl px-4 py-2 bg-brand-900 text-white hover:opacity-95 disabled:opacity-60 transition shadow-soft focus:outline-none focus:ring-2 focus:ring-accent-500 ${className}`}>
      {loading ? "טוען…" : children}
    </button>
  );
}