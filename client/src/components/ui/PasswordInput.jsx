import React, { useState } from "react";

export default function PasswordInput({label, error, ...props}){
  const [show,setShow]=useState(false);
  
  return (
    <div className="space-y-2">
      {label && (
        <label className="block text-sm font-semibold text-brand-700">
          {label}
        </label>
      )}
      <div className="relative">
        <input {...props} 
          type={show?"text":"password"}
          className={`w-full px-4 py-3.5 pl-12 border-2 rounded-2xl min-h-[56px] bg-white/80 backdrop-blur-sm font-medium text-brand-900 placeholder-brand-400 transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-accent-100 focus:border-accent-500 focus:bg-white focus:scale-[1.02] ${error?'border-red-400 focus:border-red-500 focus:ring-red-100':'border-gray-200 hover:border-gray-300'}`} />
        
        {/* Password visibility toggle */}
        <button type="button" 
          onClick={()=>setShow(v=>!v)}
          className="absolute left-3 top-1/2 -translate-y-1/2 p-2 text-brand-500 hover:text-brand-700 hover:bg-brand-50 rounded-xl transition-all duration-200">
          {show ? (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L8.464 8.464M9.878 9.878l4.242 4.242m0 0L15.535 15.535M14.12 14.12L8.464 8.464" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          )}
        </button>
        
        {error && (
          <div className="absolute -bottom-1 left-0 flex items-center gap-1 text-xs text-red-600 font-medium">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}