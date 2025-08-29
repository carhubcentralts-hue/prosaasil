import React, { useState } from "react";

export default function ProfessionalLoginApp() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate API call
      console.log("התחברות עבור:", email);
      alert("התחברות הצליחה! (דמו)");
    } catch {
      setError("פרטי התחברות שגויים");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Professional Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-2xl">
            <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
            </svg>
          </div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">AgentLocator</h1>
          <p className="text-gray-600 text-lg">מערכת CRM מתקדמת לנדל"ן</p>
        </div>

        {/* Professional Login Card */}
        <div className="bg-white/80 backdrop-blur-md rounded-3xl border border-white/30 shadow-2xl p-8">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">התחברות למערכת</h2>
            <p className="text-gray-600">הזן את פרטי ההתחברות שלך</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-2xl">
              <p className="text-red-800 text-sm font-medium">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6" dir="rtl">
            {/* Professional Email Input */}
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                כתובת אימייל
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full px-4 py-4 border border-gray-300 rounded-2xl text-right bg-gray-50 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 text-lg"
                required
                dir="ltr"
              />
            </div>

            {/* Professional Password Input */}
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                סיסמה
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-4 border border-gray-300 rounded-2xl text-right bg-gray-50 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 text-lg"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-blue-600 hover:text-blue-800 font-medium text-sm transition-colors"
                >
                  {showPassword ? "הסתר" : "הצג"}
                </button>
              </div>
            </div>

            {/* Professional Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-4 px-6 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 text-white font-bold rounded-2xl transition-all duration-300 transform hover:scale-[1.02] shadow-xl focus:ring-4 focus:ring-blue-300 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none text-lg"
            >
              {isLoading ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  מתחבר...
                </div>
              ) : (
                "התחבר למערכת"
              )}
            </button>

            {/* Professional Links */}
            <div className="flex justify-between items-center pt-4 text-sm">
              <a 
                href="#forgot"
                className="text-blue-600 hover:text-blue-800 font-medium transition-colors"
              >
                שכחתי את הסיסמה
              </a>
              <a 
                href="/"
                className="text-gray-500 hover:text-gray-700 transition-colors"
              >
                חזרה לדף הבית
              </a>
            </div>
          </form>

          {/* Demo Credentials */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <div className="text-xs text-gray-500 text-center">
              <p className="mb-2">פרטי התחברות לדמו:</p>
              <div className="bg-gray-50 rounded-xl p-3 text-left font-mono text-xs">
                admin@maximus.co.il / admin123<br/>
                manager@shai-realestate.co.il / business123456
              </div>
            </div>
          </div>
        </div>

        {/* Professional Footer */}
        <div className="text-center mt-8">
          <p className="text-gray-500 text-sm">© 2025 AgentLocator - מערכת CRM מתקדמת לנדל"ן</p>
        </div>
      </div>
    </div>
  );
}