import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';
import { Eye, EyeOff, Building2, Mail, Lock, ArrowLeft } from 'lucide-react';
import { cn } from '../../shared/utils/cn';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuth();
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
      
      console.log('✅ Login successful, waiting for session to stabilize...');
      // 🔧 FIX: Wait a moment for session cookie to be fully set
      await new Promise(resolve => setTimeout(resolve, 100));
      
      console.log('✅ Session stable, navigating to dashboard...');
      navigate('/app/admin/overview', { replace: true });
    } catch (err) {
      setError('אימייל או סיסמה שגויים');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex" dir="rtl">
      {/* Desktop Side Panel */}
      <div className="hidden lg:flex lg:flex-1 lg:flex-col lg:justify-center lg:px-20 xl:px-24 gradient-brand">
        <div className="mx-auto w-full max-w-sm text-white">
          <div className="mb-8">
            <Building2 className="h-12 w-12 mb-6" />
            <h1 className="text-3xl font-semibold mb-4">
              מערכת הניהול
            </h1>
            <p className="text-lg opacity-90">
              דור חדש של שירות לקוח
              <br />
              עם AI מתקדם
            </p>
          </div>
          
          <div className="space-y-4 text-sm opacity-80">
            <div className="flex items-center">
              <div className="w-2 h-2 bg-white rounded-full mr-3"></div>
              שיחות טלפון בזמן אמת
            </div>
            <div className="flex items-center">
              <div className="w-2 h-2 bg-white rounded-full mr-3"></div>
              WhatsApp אוטומטי
            </div>
            <div className="flex items-center">
              <div className="w-2 h-2 bg-white rounded-full mr-3"></div>
              לידים בקליק
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Header */}
      <div className="lg:hidden w-full p-4 absolute top-0 z-10">
        <div className="flex items-center">
          <Building2 className="h-8 w-8 text-blue-600 mr-3" />
          <div className="text-slate-900">
            <div className="font-semibold text-lg">שי דירות ומשרדים</div>
            <div className="text-xs text-slate-500">מערכת ניהול לקוחות</div>
          </div>
        </div>
      </div>

      {/* Login Form */}
      <div className="flex-1 flex flex-col justify-center py-12 px-4 sm:px-6 lg:flex-none lg:px-20 xl:px-24">
        <div className="mx-auto w-full max-w-sm lg:w-96 mt-16 lg:mt-0">
          <div className="text-center lg:text-right mb-8">
            <h2 className="text-2xl font-semibold text-slate-900">
              ברוכים השבים!
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              היכנסו למשטח האישי שלכם
            </p>
          </div>

          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div 
                className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-center"
                role="alert"
                data-testid="error-message"
              >
                <span className="w-1 h-1 bg-red-600 rounded-full mr-2"></span>
                {error}
              </div>
            )}

            {/* Email Field */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">
                כתובת מייל
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={cn(
                    'block w-full pr-10 pl-4 py-3 border rounded-xl transition-colors',
                    'text-slate-900 placeholder-slate-400',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    'border-slate-300 bg-white hover:border-slate-400'
                  )}
                  placeholder="your@email.com"
                  autoComplete="email"
                  dir="ltr"
                  data-testid="input-email"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-slate-700">
                  סיסמה
                </label>
                <Link 
                  to="/forgot" 
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  data-testid="link-forgot-password"
                >
                  שכחת סיסמה?
                </Link>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-slate-400" />
                </div>
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center">
                  <button
                    type="button"
                    className="text-slate-400 hover:text-slate-600 transition-colors"
                    onClick={() => setShowPassword(!showPassword)}
                    data-testid="button-toggle-password"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className={cn(
                    'block w-full pr-10 pl-10 py-3 border rounded-xl transition-colors',
                    'text-slate-900 placeholder-slate-400',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    'border-slate-300 bg-white hover:border-slate-400'
                  )}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  dir="ltr"
                  data-testid="input-password"
                />
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded"
                data-testid="checkbox-remember"
              />
              <label htmlFor="remember-me" className="mr-2 block text-sm text-slate-700">
                זכור אותי
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!email || !password || isLoading}
              className="btn-primary w-full py-3 text-base font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="button-login"
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  מתחבר...
                </div>
              ) : (
                'התחבר'
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-xs text-slate-500">
              © 2025 שי דירות ומשרדים בע״מ • כל הזכויות שמורות
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}