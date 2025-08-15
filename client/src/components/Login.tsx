import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetMessage, setResetMessage] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showResetForm, setShowResetForm] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בהתחברות');
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // TODO: Implement forgot password API call
      console.log('Forgot password for:', resetEmail);
      setResetMessage('קישור איפוס נשלח למייל שלך');
      setShowResetForm(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בשליחת איפוס סיסמא');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      // TODO: Implement reset password API call
      console.log('Reset password with token:', resetToken);
      setResetMessage('סיסמא שונתה בהצלחה! אתה יכול להתחבר עכשיו');
      setShowForgotPassword(false);
      setShowResetForm(false);
      setResetToken('');
      setNewPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה באיפוס סיסמא');
    } finally {
      setIsLoading(false);
    }
  };

  if (showForgotPassword) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div>
            <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900" dir="rtl">
              איפוס סיסמא
            </h2>
            <p className="mt-2 text-center text-sm text-gray-600" dir="rtl">
              מערכת ניהול שיחות עברית AI
            </p>
          </div>

          {!showResetForm ? (
            <form className="mt-8 space-y-6" onSubmit={handleForgotPassword} dir="rtl">
              <div>
                <label htmlFor="reset-email" className="block text-sm font-medium text-gray-700">
                  כתובת אימייל
                </label>
                <input
                  id="reset-email"
                  name="email"
                  type="email"
                  required
                  value={resetEmail}
                  onChange={(e) => setResetEmail(e.target.value)}
                  className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="דוא״ל"
                  data-testid="input-reset-email"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded" data-testid="text-error">
                  {error}
                </div>
              )}

              {resetMessage && (
                <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded" data-testid="text-success">
                  {resetMessage}
                </div>
              )}

              <div className="flex flex-col space-y-3">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                  data-testid="button-send-reset"
                >
                  {isLoading ? 'שולח...' : 'שלח קישור איפוס'}
                </button>

                <button
                  type="button"
                  onClick={() => setShowForgotPassword(false)}
                  className="text-indigo-600 hover:text-indigo-500 text-sm font-medium"
                  data-testid="button-back-to-login"
                >
                  חזור להתחברות
                </button>
              </div>
            </form>
          ) : (
            <form className="mt-8 space-y-6" onSubmit={handleResetPassword} dir="rtl">
              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
                  סיסמא חדשה
                </label>
                <input
                  id="new-password"
                  name="password"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="הכנס סיסמא חדשה (לפחות 6 תווים)"
                  data-testid="input-new-password"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded" data-testid="text-error">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                data-testid="button-reset-password"
              >
                {isLoading ? 'מעדכן...' : 'עדכן סיסמא'}
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg border border-gray-200 shadow-lg p-8">
          <div className="text-center mb-6">
            <div className="mb-4">
              <span className="text-5xl">🏢</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2" dir="rtl">
              שי דירות ומשרדים בע״מ
            </h1>
            <h2 className="text-lg font-semibold text-gray-700 mb-4" dir="rtl">
              מערכת ניהול מתקדמת
            </h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="text-sm text-blue-800 space-y-2" dir="rtl">
                <div className="flex items-center justify-center gap-2">
                  <span>🔒</span>
                  <span>מערכת אבטחה מתקדמת</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <span>📞</span>
                  <span>ניהול שיחות חכם</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <span>🌐</span>
                  <span>תמיכה מלאה בעברית</span>
                </div>
              </div>
            </div>
            
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm font-medium text-blue-900 mb-2" dir="rtl">
                מערכת ניהול מתקדמת לנדל"ן
              </div>
              <div className="text-xs text-blue-700 space-y-1" dir="rtl">
                <div>✓ ניהול לידים ותוכנית מכירות</div>
                <div>✓ מערכת שיחות אוטומטית</div>
                <div>✓ דוחות ואנליטיקה מתקדמת</div>
              </div>
            </div>
          </div>

          <form className="space-y-6" onSubmit={handleLogin} dir="rtl">
          <div className="space-y-4">
            <div>
              <label htmlFor="email-address" className="block text-sm font-medium text-gray-700">
                כתובת אימייל
              </label>
              <input
                id="email-address"
                name="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                placeholder="דוא״ל"
                data-testid="input-email"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                סיסמא
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                placeholder="סיסמא"
                data-testid="input-password"
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded" data-testid="text-error">
              {error}
            </div>
          )}

          <div className="flex flex-col space-y-3">
            <button
              type="submit"
              disabled={isLoading}
              className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
              data-testid="button-login"
            >
              {isLoading ? 'מתחבר...' : 'התחבר למערכת'}
            </button>

            <button
              type="button"
              onClick={() => setShowForgotPassword(true)}
              className="text-blue-600 hover:text-blue-500 text-sm font-medium transition-colors"
              data-testid="button-forgot-password"
            >
              שכחת סיסמא?
            </button>
          </div>
          </form>
        </div>
      </div>
    </div>
  );
}