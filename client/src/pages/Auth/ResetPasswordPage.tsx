import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { authApi } from '../../features/auth/api';
import { Button } from '../../shared/components/Button';
import { Input } from '../../shared/components/Input';
import { Card, CardContent } from '../../shared/components/Card';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    // 🔍 DEBUG: Log token from URL to help diagnose token issues
    console.log('RESET TOKEN FROM URL:', token);
    console.log('RESET TOKEN LENGTH:', token ? token.length : 0);
    console.log('URL SEARCH PARAMS:', window.location.search);
    
    if (!token) {
      setError('טוקן איפוס לא תקין או חסר');
    }
  }, [token]);

  const validatePassword = (pwd: string): string | null => {
    if (pwd.length < 8) {
      return 'סיסמה חייבת להכיל לפחות 8 תווים';
    }
    if (!/(?=.*[a-z])/.test(pwd)) {
      return 'סיסמה חייבת להכיל לפחות אות קטנה אחת באנגלית';
    }
    if (!/(?=.*[A-Z])/.test(pwd)) {
      return 'סיסמה חייבת להכיל לפחות אות גדולה אחת באנגלית';
    }
    if (!/(?=.*\d)/.test(pwd)) {
      return 'סיסמה חייבת להכיל לפחות ספרה אחת';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('טוקן איפוס לא תקין');
      return;
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError('סיסמאות לא תואמות');
      return;
    }

    setIsLoading(true);

    try {
      // 🔍 DEBUG: Log what we're sending to the server
      console.log('SUBMITTING RESET - Token first 8 chars:', token.substring(0, 8));
      console.log('SUBMITTING RESET - Token last 8 chars:', token.substring(token.length - 8));
      console.log('SUBMITTING RESET - Token length:', token.length);
      
      await authApi.reset({ token, password });
      setIsSuccess(true);
      
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err) {
      setError('טוקן איפוס לא תקין או פג תוקף. אנא בקש לינק חדש.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8" dir="rtl">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="flex justify-center">
            <div className="w-16 h-16 bg-green-100 rounded-lg flex items-center justify-center">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
          <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
            סיסמה עודכנה בהצלחה!
          </h2>
        </div>

        <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-gray-600 mb-6">
                הסיסמה שלך עודכנה בהצלחה. אתה מועבר להתחברות...
              </p>
              <Link to="/login">
                <Button className="w-full" data-testid="button-go-to-login">
                  התחבר עכשיו
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8" dir="rtl">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-2xl">ש</span>
          </div>
        </div>
        <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
          איפוס סיסמה
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          הכנס סיסמה חדשה לחשבון שלך
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
                label="סיסמה חדשה"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="הכנס סיסמה חדשה"
                helperText="לפחות 8 תווים, אות גדולה, אות קטנה וספרה"
                data-testid="input-password"
              />

              <Input
                label="אישור סיסמה"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                placeholder="הכנס שוב את הסיסמה החדשה"
                data-testid="input-confirm-password"
              />

              <Button
                type="submit"
                className="w-full"
                isLoading={isLoading}
                disabled={!password || !confirmPassword || !token}
                data-testid="button-reset-password"
              >
                {isLoading ? 'מעדכן...' : 'עדכן סיסמה'}
              </Button>

              <div className="text-center">
                <Link 
                  to="/login" 
                  className="text-sm font-medium text-blue-600 hover:text-blue-500"
                  data-testid="link-back-to-login"
                >
                  חזור להתחברות
                </Link>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}