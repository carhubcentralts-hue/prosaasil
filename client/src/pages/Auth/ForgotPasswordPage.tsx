import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../../features/auth/api';
import { Button } from '../../shared/components/Button';
import { Input } from '../../shared/components/Input';
import { Card, CardContent } from '../../shared/components/Card';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await authApi.forgot({ email });
      setIsSubmitted(true);
    } catch (error) {
      // Always show success message to prevent email enumeration
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
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
            נשלח לינק לאיפוס סיסמה
          </h2>
        </div>

        <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-gray-600 mb-6">
                אם הכתובת <strong>{email}</strong> קיימת במערכת, 
                נשלח אליך לינק לאיפוס סיסמה תוך מספר דקות.
              </p>
              <p className="text-sm text-gray-500 mb-6">
                לא קיבלת אימייל? בדוק בתיקיית הספאם או נסה שוב.
              </p>
              <div className="space-y-3">
                <Button
                  onClick={() => {
                    setIsSubmitted(false);
                    setEmail('');
                  }}
                  variant="secondary"
                  className="w-full"
                  data-testid="button-try-again"
                >
                  נסה שוב
                </Button>
                <Link to="/login">
                  <Button variant="ghost" className="w-full" data-testid="button-back-to-login">
                    חזור להתחברות
                  </Button>
                </Link>
              </div>
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
          שכחת סיסמה?
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          הכנס את כתובת האימייל שלך ונשלח לך לינק לאיפוס סיסמה
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <Card>
          <CardContent className="py-8">
            <form onSubmit={handleSubmit} className="space-y-6">
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

              <Button
                type="submit"
                className="w-full"
                isLoading={isLoading}
                disabled={!email}
                data-testid="button-send-reset"
              >
                {isLoading ? 'שולח...' : 'שלח לינק לאיפוס'}
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