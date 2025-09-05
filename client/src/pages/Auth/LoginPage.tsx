import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthState } from '../../features/auth/hooks';
import { Eye, EyeOff } from 'lucide-react';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuthState();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/app/admin/overview';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      console.log('🚀 Attempting login with:', { email, passwordLength: password.length });
      await login(email, password);
      
      console.log('✅ Login successful, redirecting...');
      // Simple redirect to overview - role routing handled by guards
      navigate('/app/admin/overview', { replace: true });
    } catch (err) {
      setError('אימייל או סיסמה שגויים');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="mx-auto w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg">
            <span className="text-white font-bold text-3xl">ש</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            שי דירות ומשרדים
          </h1>
          <p className="text-gray-600">
            מערכת ניהול לידים
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div 
                  className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm"
                  role="alert"
                  data-testid="error-message"
                >
                  {error}
                </div>
              )}

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">כתובת אימייל</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="example@company.com"
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base transition-all"
                  data-testid="input-email"
                />
              </div>

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">סיסמה</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    placeholder="הכנס סיסמה"
                    className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base transition-all"
                    data-testid="input-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none"
                    data-testid="button-toggle-password"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <input
                    id="remember-me"
                    name="remember-me"
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    data-testid="checkbox-remember"
                  />
                  <label htmlFor="remember-me" className="mr-2 block text-sm text-gray-900">
                    זכור אותי
                  </label>
                </div>

                <div className="text-sm">
                  <Link 
                    to="/forgot" 
                    className="font-medium text-blue-600 hover:text-blue-500"
                    data-testid="link-forgot-password"
                  >
                    שכחת סיסמה?
                  </Link>
                </div>
              </div>

              <button
                type="submit"
                disabled={!email || !password || isLoading}
                className="w-full bg-blue-600 text-white py-3 px-4 rounded-xl font-medium text-base hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="button-login"
              >
                {isLoading ? 'מתחבר...' : 'התחבר'}
              </button>
            </form>
        </div>
        
        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-xs text-gray-500">
            © 2025 שי דירות ומשרדים בע״מ
          </p>
        </div>
      </div>
    </div>
  );
}