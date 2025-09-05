import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthState } from '../../features/auth/hooks';
import { Button } from '../../shared/components/Button';
import { Input } from '../../shared/components/Input';
import { Card, CardContent } from '../../shared/components/Card';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      await login(email, password);
      
      // Role-based redirect
      const { user } = await import('../../features/auth/hooks').then(module => 
        module.useAuthState()
      );
      
      // Navigate based on role or return to attempted page
      if (from !== '/app/admin/overview') {
        navigate(from, { replace: true });
      } else {
        // Default navigation based on role will be handled by route protection
        navigate('/app/admin/overview', { replace: true });
      }
    } catch (err) {
      setError('אימייל או סיסמה שגויים');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8" dir="rtl">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Brand */}
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-2xl">ש</span>
          </div>
        </div>
        <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
          התחברות למערכת
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          שי דירות ומשרדים - מערכת ניהול לידים
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <Card>
          <CardContent className="py-8">
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

              <Input
                label="כתובת אימייל"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="example@company.com"
                data-testid="input-email"
              />

              <Input
                label="סיסמה"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="הכנס סיסמה"
                data-testid="input-password"
              />

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

              <Button
                type="submit"
                className="w-full"
                isLoading={isLoading}
                disabled={!email || !password}
                data-testid="button-login"
              >
                {isLoading ? 'מתחבר...' : 'התחבר'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-gray-500">
            © 2025 שי דירות ומשרדים בע״מ. כל הזכויות שמורות.
          </p>
        </div>
      </div>
    </div>
  );
}