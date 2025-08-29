import React from "react";

export default function AuthCard({title, children}:{title:string; children:React.ReactNode}){
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white/95 backdrop-blur-sm border border-white/20 rounded-3xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <span className="text-white text-2xl font-bold">🏢</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">{title}</h1>
          <p className="text-gray-500 text-sm">מערכת CRM מתקדמת</p>
        </div>
        {children}
        <div className="text-xs text-gray-400 text-center mt-6">© AgentLocator - מערכת מתקדמת לניהול לקוחות</div>
      </div>
    </div>
  );
}