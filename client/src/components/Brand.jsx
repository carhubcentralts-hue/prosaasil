import React from "react";

export default function Brand(){
  return (
    <div className="flex items-center gap-3">
      <div className="relative">
        <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-accent-500 to-accent-700 text-white grid place-items-center font-bold text-lg shadow-button">
          שי
        </div>
        <div className="absolute -top-1 -right-1 h-4 w-4 bg-green-400 rounded-full border-2 border-white shadow-sm"></div>
      </div>
      <div>
        <div className="font-bold text-lg text-brand-900">שי דירות ומשרדים</div>
        <div className="text-xs text-brand-600 font-medium">מערכת ניהול מתקדמת</div>
      </div>
    </div>
  );
}