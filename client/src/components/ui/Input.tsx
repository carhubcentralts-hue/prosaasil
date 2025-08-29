import React from "react";

export default function Input(
  {label, error, ...props}:
  React.InputHTMLAttributes<HTMLInputElement> & {label?:string; error?:string}
){
  return (
    <div className="space-y-2">
      {label && <label className="block text-sm font-medium text-gray-700">{label}</label>}
      <input
        {...props}
        className={`w-full px-4 py-3 border rounded-xl transition-all duration-200 text-right bg-gray-50 hover:bg-white focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
          error ? "border-red-400 bg-red-50" : "border-gray-300"
        }`}
      />
      {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
    </div>
  );
}