import React, { useState } from 'react';
import { Building2, Phone, Shield } from 'lucide-react';

function LoginPage({ onLogin }) {
  const [credentials, setCredentials] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (response.ok) {
        onLogin();
      } else {
        const errorData = await response.json();
        setError(errorData.message || 'שגיאה בהתחברות');
      }
    } catch (error) {
      setError('שגיאה בחיבור לשרת');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center rtl" dir="rtl">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            מערכת CRM עברית
          </h1>
          <p className="text-gray-600">
            התחבר לחשבון שלך כדי להמשיך
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-600 text-center">{error}</p>
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              כתובת אימייל
            </label>
            <input
              id="email"
              type="email"
              required
              value={credentials.email}
              onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="הזן כתובת אימייל"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
              סיסמה
            </label>
            <input
              id="password"
              type="password"
              required
              value={credentials.password}
              onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="הזן סיסמה"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-2 px-4 rounded-md text-white font-medium ${
              loading 
                ? 'bg-gray-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500'
            } transition-colors`}
          >
            {loading ? 'מתחבר...' : 'התחבר'}
          </button>
        </form>

        {/* Demo Credentials */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-600 text-center mb-4">
            חשבונות לדוגמה:
          </p>
          <div className="space-y-3 text-xs">
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="flex items-center mb-1">
                <Shield className="w-4 h-4 text-blue-600 ml-2" />
                <span className="font-medium">מנהל מערכת</span>
              </div>
              <p>manager@shai-realestate.co.il / business123456</p>
            </div>
            <div className="bg-gray-50 p-3 rounded-md">
              <div className="flex items-center mb-1">
                <Building2 className="w-4 h-4 text-green-600 ml-2" />
                <span className="font-medium">משתמש עסק</span>
              </div>
              <p>business@shai-offices.co.il / shai123</p>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="mt-6 grid grid-cols-3 gap-4 text-center">
          <div className="text-gray-600">
            <Phone className="w-6 h-6 mx-auto mb-1" />
            <p className="text-xs">שיחות AI</p>
          </div>
          <div className="text-gray-600">
            <Building2 className="w-6 h-6 mx-auto mb-1" />
            <p className="text-xs">ניהול CRM</p>
          </div>
          <div className="text-gray-600">
            <Shield className="w-6 h-6 mx-auto mb-1" />
            <p className="text-xs">וואטסאפ</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;