import React, { useState } from "react";

export default function ModernLogin() {
  const [mode, setMode] = useState<'login' | 'forgot'>('login');
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<'success' | 'error' | ''>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    if (mode === 'login') {
      // Validate inputs
      if (!email.includes('@')) {
        setMessage("כתובת האימייל לא תקינה");
        setMessageType('error');
        setLoading(false);
        return;
      }
      if (password.length < 6) {
        setMessage("סיסמה חייבת להכיל לפחות 6 תווים");
        setMessageType('error');
        setLoading(false);
        return;
      }

      // Real API login
      try {
        const response = await fetch('/api/ui/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
          setMessage("התחברות הצליחה!");
          setMessageType('success');
          
          // Redirect based on user role to server-side pages
          setTimeout(() => {
            if (data.user.role === 'admin') {
              window.location.href = '/ui/admin/overview';
            } else {
              window.location.href = '/ui/biz/contacts';
            }
          }, 1000);
        } else {
          setMessage(data.error || "פרטי התחברות שגויים");
          setMessageType('error');
        }
      } catch (error) {
        setMessage("שגיאת רשת - נסה שוב");
        setMessageType('error');
      }
    } else {
      // Forgot password
      if (!email.includes('@')) {
        setMessage("כתובת האימייל לא תקינה");
        setMessageType('error');
        setLoading(false);
        return;
      }
      
      await new Promise(resolve => setTimeout(resolve, 1200));
      setMessage("קישור איפוס נשלח לאימייל שלך");
      setMessageType('success');
      setTimeout(() => setMode('login'), 2000);
    }
    
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        
        {/* Header */}
        <div className="text-center">
          <div className="flex items-center justify-center w-16 h-16 mx-auto bg-indigo-600 rounded-lg mb-6">
            <span className="text-white text-2xl font-bold">AL</span>
          </div>
          <h2 className="text-3xl font-extrabold text-gray-900">AgentLocator</h2>
          <p className="mt-2 text-gray-600">מערכת CRM מקצועית</p>
        </div>

        {/* Mode Toggle */}
        <div className="flex rounded-lg bg-gray-100 p-1">
          <button
            onClick={() => {setMode('login'); setMessage(''); setMessageType('');}}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
              mode === 'login'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            התחברות
          </button>
          <button
            onClick={() => {setMode('forgot'); setMessage(''); setMessageType('');}}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
              mode === 'forgot'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            שחזור סיסמה
          </button>
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            
            {/* Email Field */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                כתובת אימייל
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="appearance-none relative block w-full px-3 py-3 border border-gray-300 rounded-lg placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 text-right"
                placeholder="your@email.com"
                dir="ltr"
              />
            </div>

            {/* Password Field (only in login mode) */}
            {mode === 'login' && (
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  סיסמה
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="appearance-none relative block w-full px-3 py-3 border border-gray-300 rounded-lg placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 text-right"
                  placeholder="••••••••"
                />
              </div>
            )}
          </div>

          {/* Status Message */}
          {message && (
            <div className={`p-4 rounded-lg ${
              messageType === 'success' 
                ? 'bg-green-50 border border-green-200' 
                : 'bg-red-50 border border-red-200'
            }`}>
              <p className={`text-sm font-medium text-center ${
                messageType === 'success' ? 'text-green-800' : 'text-red-800'
              }`}>
                {message}
              </p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <div className="flex items-center">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white ml-2"></div>
                {mode === 'login' ? 'מתחבר...' : 'שולח...'}
              </div>
            ) : (
              mode === 'login' ? 'התחבר' : 'שלח קישור איפוס'
            )}
          </button>

          {/* Demo Credentials (only in login mode) */}
          {mode === 'login' && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-50 text-gray-500">פרטי דמו</span>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-xs">
                <div className="bg-white p-3 rounded border text-center font-mono">
                  <div className="font-bold text-indigo-600">מנהל:</div>
                  admin@maximus.co.il / admin123
                </div>
                <div className="bg-white p-3 rounded border text-center font-mono">
                  <div className="font-bold text-purple-600">עסק:</div>
                  manager@shai-realestate.co.il / business123456
                </div>
              </div>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="text-center">
          <p className="text-xs text-gray-500">© 2025 AgentLocator</p>
        </div>
      </div>
    </div>
  );
}