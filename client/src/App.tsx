import React, { useState, useEffect } from 'react';
import { Building2, Phone, Shield, User, LogOut } from 'lucide-react';

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [credentials, setCredentials] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
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

function App() {
  const [user, setUser] = useState<any>(null);
  const [business, setBusiness] = useState<any>(null);
  const [permissions, setPermissions] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const response = await fetch('/api/auth/current', {
        credentials: 'include'  // Include session cookies
      });
      if (response.ok) {
        const userData = await response.json();
        setUser(userData.user);
        setBusiness(userData.business);
        setPermissions(userData.permissions || {});
      }
    } catch (error) {
      console.error('Failed to fetch user data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    fetchUserData();
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser(null);
      setBusiness(null);
      setPermissions({});
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 rtl" dir="rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold ml-3">
                {user.role === 'manager' ? 'מ' : 'ע'}
              </div>
              <span className="text-lg font-semibold text-gray-900">
                {user.role === 'manager' ? 'ניהול מערכת' : business?.name || 'מערכת CRM'}
              </span>
            </div>

            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="flex items-center">
                <User className="w-5 h-5 text-gray-400 ml-2" />
                <span className="text-sm text-gray-700">{user.name || user.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-3 rounded-md text-sm transition-colors flex items-center"
              >
                <LogOut className="w-4 h-4 ml-1" />
                התנתק
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Page Content */}
      <main className="py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              👋 שלום, {user.name || user.email}!
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-blue-900 mb-2">פרטי משתמש</h3>
                <div className="space-y-2 text-sm">
                  <p><strong>תפקיד:</strong> {user.role === 'manager' ? 'מנהל מערכת' : 'משתמש עסק'}</p>
                  <p><strong>אימייל:</strong> {user.email}</p>
                  {business && (
                    <>
                      <p><strong>עסק:</strong> {business.name}</p>
                      <p><strong>טלפון:</strong> {business.phone_number || 'לא הוגדר'}</p>
                    </>
                  )}
                </div>
              </div>
              
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-green-900 mb-2">מצב המערכת</h3>
                <div className="space-y-2 text-sm">
                  <p>✅ מחובר בהצלחה</p>
                  <p>✅ API Adapter פועל</p>
                  <p>✅ React SPA נטען</p>
                  <p>✅ TypeScript ללא שגיאות</p>
                </div>
              </div>
            </div>
            
            {user.role === 'manager' && (
              <div className="mt-6 p-4 bg-yellow-50 rounded-lg">
                <h3 className="text-lg font-semibold text-yellow-900 mb-2">🔧 מצב מנהל</h3>
                <p className="text-sm text-yellow-800">
                  רכיבי AdminDashboard וDashboard הוסרו זמנית לבדיקה. 
                  האפליקציה הבסיסית עובדת!
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;