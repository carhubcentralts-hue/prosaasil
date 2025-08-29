import React, { useState, useEffect } from "react";

export default function EliteLoginApp() {
  const [currentMode, setCurrentMode] = useState<'login' | 'forgot'>('login');
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Floating background animation
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const { clientX, clientY } = e;
      const x = (clientX / window.innerWidth) * 100;
      const y = (clientY / window.innerHeight) * 100;
      
      const bg = document.querySelector('.floating-bg') as HTMLElement;
      if (bg) {
        bg.style.background = `radial-gradient(600px circle at ${x}% ${y}%, rgba(59, 130, 246, 0.15), transparent 40%)`;
      }
    };
    
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    
    // Validation
    if (!email.includes('@')) {
      setError("כתובת האימייל לא תקינה");
      setIsLoading(false);
      return;
    }
    
    if (password.length < 6) {
      setError("סיסמה חייבת להכיל לפחות 6 תווים");
      setIsLoading(false);
      return;
    }

    try {
      await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate API
      
      // Demo authentication
      if (email === "admin@maximus.co.il" && password === "admin123") {
        setSuccess("התחברות הצליחה! מפנה למערכת...");
        setTimeout(() => window.location.href = "/admin", 1500);
      } else if (email === "manager@shai-realestate.co.il" && password === "business123456") {
        setSuccess("התחברות הצליחה! מפנה למערכת...");
        setTimeout(() => window.location.href = "/business", 1500);
      } else {
        setError("פרטי התחברות שגויים. בדוק את האימייל והסיסמה");
      }
    } catch {
      setError("שגיאת תקשורת. נסה שוב");
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    
    if (!email.includes('@')) {
      setError("כתובת האימייל לא תקינה");
      setIsLoading(false);
      return;
    }

    try {
      await new Promise(resolve => setTimeout(resolve, 1500));
      setSuccess("קישור לאיפוס סיסמה נשלח לאימייל שלך");
      setTimeout(() => setCurrentMode('login'), 3000);
    } catch {
      setError("שגיאה בשליחת האימייל. נסה שוב");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Animated Background */}
      <div className="floating-bg fixed inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900"></div>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-700/20 via-transparent to-purple-900/20"></div>
      
      {/* Animated Geometric Shapes */}
      <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-gradient-to-r from-blue-400/10 to-purple-400/10 rounded-full animate-pulse"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-gradient-to-l from-indigo-400/10 to-cyan-400/10 rounded-full animate-pulse delay-1000"></div>
      
      {/* Main Container */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          
          {/* Elite Header */}
          <div className="text-center mb-12">
            <div className="relative mb-8">
              <div className="w-24 h-24 bg-gradient-to-br from-blue-500 via-purple-500 to-indigo-600 rounded-3xl flex items-center justify-center mx-auto shadow-2xl border-2 border-white/20 backdrop-blur-sm">
                <svg className="w-14 h-14 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
                </svg>
              </div>
              <div className="absolute -inset-4 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full opacity-20 animate-ping"></div>
            </div>
            <h1 className="text-5xl font-black text-white mb-3 tracking-tight">AgentLocator</h1>
            <p className="text-blue-200 text-xl font-medium">מערכת CRM מתקדמת לנדל״ן</p>
            <div className="w-24 h-1 bg-gradient-to-r from-blue-400 to-purple-400 mx-auto mt-4 rounded-full"></div>
          </div>

          {/* Elite Login Card */}
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-600/30 to-purple-600/30 rounded-3xl blur-xl"></div>
            <div className="relative bg-white/95 backdrop-blur-xl rounded-3xl border border-white/30 shadow-2xl p-10">
              
              {/* Mode Toggle */}
              <div className="flex mb-8 bg-gray-100 rounded-2xl p-1">
                <button
                  onClick={() => {setCurrentMode('login'); setError(''); setSuccess('');}}
                  className={`flex-1 py-3 px-4 rounded-xl font-semibold transition-all duration-300 ${
                    currentMode === 'login' 
                      ? 'bg-white text-blue-600 shadow-lg' 
                      : 'text-gray-600 hover:text-blue-600'
                  }`}
                >
                  התחברות
                </button>
                <button
                  onClick={() => {setCurrentMode('forgot'); setError(''); setSuccess('');}}
                  className={`flex-1 py-3 px-4 rounded-xl font-semibold transition-all duration-300 ${
                    currentMode === 'forgot' 
                      ? 'bg-white text-purple-600 shadow-lg' 
                      : 'text-gray-600 hover:text-purple-600'
                  }`}
                >
                  שחזור סיסמה
                </button>
              </div>

              {/* Status Messages */}
              {error && (
                <div className="mb-6 p-4 bg-gradient-to-r from-red-50 to-pink-50 border border-red-200 rounded-2xl animate-fadeIn">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-xs">✕</span>
                    </div>
                    <p className="text-red-800 font-medium">{error}</p>
                  </div>
                </div>
              )}
              
              {success && (
                <div className="mb-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-2xl animate-fadeIn">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-xs">✓</span>
                    </div>
                    <p className="text-green-800 font-medium">{success}</p>
                  </div>
                </div>
              )}

              {/* Login Form */}
              {currentMode === 'login' && (
                <form onSubmit={handleLogin} className="space-y-6" dir="rtl">
                  <div className="space-y-2">
                    <label className="block text-sm font-bold text-gray-800 mb-3">
                      כתובת אימייל
                    </label>
                    <div className="relative">
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@company.co.il"
                        className="w-full px-6 py-4 border-2 border-gray-200 rounded-2xl text-right bg-white/80 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 text-lg placeholder:text-gray-400"
                        required
                        dir="ltr"
                      />
                      <div className="absolute left-4 top-1/2 -translate-y-1/2">
                        <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-bold text-gray-800 mb-3">
                      סיסמה
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••••"
                        className="w-full px-6 py-4 border-2 border-gray-200 rounded-2xl text-right bg-white/80 focus:bg-white focus:outline-none focus:ring-4 focus:ring-blue-200 focus:border-blue-400 transition-all duration-300 text-lg"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 transition-colors"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          {showPassword ? (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                          ) : (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          )}
                        </svg>
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-5 px-6 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 text-white font-bold rounded-2xl transition-all duration-500 transform hover:scale-[1.02] hover:shadow-2xl focus:ring-4 focus:ring-blue-300 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none text-lg relative overflow-hidden group"
                  >
                    {isLoading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin"></div>
                        מתחבר למערכת...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                        </svg>
                        התחבר למערכת
                      </div>
                    )}
                    <div className="absolute inset-0 bg-white/20 transform scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left"></div>
                  </button>
                </form>
              )}

              {/* Forgot Password Form */}
              {currentMode === 'forgot' && (
                <form onSubmit={handleForgotPassword} className="space-y-6" dir="rtl">
                  <div className="text-center mb-6">
                    <h3 className="text-xl font-bold text-gray-800">שחזור סיסמה</h3>
                    <p className="text-gray-600 mt-2">נשלח לך קישור לאיפוס סיסמה</p>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="block text-sm font-bold text-gray-800 mb-3">
                      כתובת האימייל שלך
                    </label>
                    <div className="relative">
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@company.co.il"
                        className="w-full px-6 py-4 border-2 border-gray-200 rounded-2xl text-right bg-white/80 focus:bg-white focus:outline-none focus:ring-4 focus:ring-purple-200 focus:border-purple-400 transition-all duration-300 text-lg placeholder:text-gray-400"
                        required
                        dir="ltr"
                      />
                      <div className="absolute left-4 top-1/2 -translate-y-1/2">
                        <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-5 px-6 bg-gradient-to-r from-purple-600 via-pink-600 to-indigo-600 hover:from-purple-700 hover:via-pink-700 hover:to-indigo-700 text-white font-bold rounded-2xl transition-all duration-500 transform hover:scale-[1.02] hover:shadow-2xl focus:ring-4 focus:ring-purple-300 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none text-lg relative overflow-hidden group"
                  >
                    {isLoading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin"></div>
                        שולח איפוס...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                        שלח קישור איפוס
                      </div>
                    )}
                    <div className="absolute inset-0 bg-white/20 transform scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left"></div>
                  </button>
                </form>
              )}

              {/* Demo Credentials */}
              {currentMode === 'login' && (
                <div className="mt-8 pt-6 border-t border-gray-200">
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-700 mb-4">פרטי התחברות לדמו:</p>
                    <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-2xl p-4 border border-gray-200">
                      <div className="space-y-2 text-left font-mono text-sm">
                        <div className="flex items-center justify-between p-2 bg-white rounded-lg border">
                          <span className="text-blue-600 font-semibold">מנהל</span>
                          <span className="text-gray-600">admin@maximus.co.il / admin123</span>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-white rounded-lg border">
                          <span className="text-purple-600 font-semibold">עסק</span>
                          <span className="text-gray-600">manager@shai-realestate.co.il / business123456</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Elite Footer */}
          <div className="text-center mt-10">
            <p className="text-blue-200 text-sm font-medium">© 2025 AgentLocator - טכנולוגיה מתקדמת לנדל״ן</p>
          </div>
        </div>
      </div>
    </div>
  );
}