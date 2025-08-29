import React from "react";
import Brand from "./Brand.jsx";

export default function AuthCard({title, children}){
  return (
    <div className="min-h-screen bg-gradient-elegant flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Glass morphism card */}
        <div className="bg-white/95 backdrop-blur-sm rounded-3xl shadow-elegant border border-white/20 p-8 space-y-6 transform hover:scale-[1.02] transition-all duration-300">
          
          {/* Header with brand */}
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <Brand/>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-brand-900 mb-2">{title}</h1>
              <p className="text-brand-600 text-sm">כניסה למערכת ניהול נדל״ן</p>
            </div>
          </div>

          {/* Content */}
          <div className="space-y-5">
            {children}
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-gray-100">
            <p className="text-xs text-brand-500 text-center">
              מערכת מאובטחת © 2024 שי דירות ומשרדים בע״מ
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}