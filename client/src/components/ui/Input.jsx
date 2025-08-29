import React from "react";

export default function Input({label, error, ...props}){
  return (
    <div className="space-y-2">
      {label && (
        <label className="block text-sm font-semibold text-brand-700">
          {label}
        </label>
      )}
      <div className="relative">
        <input {...props}
          className={`w-full px-4 py-3.5 border-2 rounded-2xl min-h-[56px] bg-white/80 backdrop-blur-sm font-medium text-brand-900 placeholder-brand-400 transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-accent-100 focus:border-accent-500 focus:bg-white focus:scale-[1.02] ${error?'border-red-400 focus:border-red-500 focus:ring-red-100':'border-gray-200 hover:border-gray-300'}`} />
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