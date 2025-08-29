import React from "react";

export default function Button(
  { children, className = "", loading, ...props }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & {loading?: boolean}
){
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold rounded-xl transition-all duration-300 transform hover:scale-[1.02] shadow-xl focus:ring-4 focus:ring-blue-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none ${className}`}
    >
      {loading ? "טוען…" : children}
    </button>
  );
}