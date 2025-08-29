import React from "react";

export default function Button({children, loading, className="", ...props}){
  return (
    <button {...props}
      disabled={props.disabled || loading}
      className={`w-full min-h-[56px] rounded-2xl px-6 py-4 bg-gradient-to-r from-accent-500 to-accent-600 text-white font-semibold text-lg shadow-button hover:shadow-xl hover:from-accent-600 hover:to-accent-700 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100 transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-accent-100 ${className}`}>
      <div className="flex items-center justify-center gap-2">
        {loading && (
          <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        )}
        {loading ? "מתחבר..." : children}
      </div>
    </button>
  );
}