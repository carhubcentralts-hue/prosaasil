import { useState } from 'react';
import { AuthService } from '../lib/auth';

interface LoginProps {
  onLoginSuccess: (user: any) => void;
}

export function ProfessionalLogin({ onLoginSuccess }: LoginProps) {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForgotPassword, setShowForgotPassword] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError(''); // Clear error when user types
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await AuthService.login(formData.email, formData.password);
      onLoginSuccess(response.user);
    } catch (err: any) {
      setError(err.message || 'שגיאה בהתחברות');
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (email: string) => {
    // This would integrate with your password reset system
    console.log('Password reset requested for:', email);
    setShowForgotPassword(false);
    setError('');
    // Show success message that reset email was sent
  };

  if (showForgotPassword) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-200 flex items-center justify-center p-4">
        <div className="bg-white/95 backdrop-blur-sm border border-white/20 rounded-3xl p-8 w-full max-w-md shadow-2xl">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <span className="text-white text-2xl font-semibold">🔒</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-2">איפוס סיסמה</h1>
            <p className="text-slate-600">הזן את כתובת האימייל שלך ונשלח לך קישור לאיפוס</p>
          </div>

          <form onSubmit={(e) => {
            e.preventDefault();
            const email = (e.target as any).email.value;
            handleForgotPassword(email);
          }} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-2">
                כתובת אימייל
              </label>
              <input
                type="email"
                id="email"
                name="email"
                required
                className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-right"
                placeholder="your.email@company.com"
              />
            </div>

            <div className="space-y-4">
              <button
                type="submit"
                className="w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white py-3 px-4 rounded-xl font-medium hover:from-blue-700 hover:to-blue-800 transition-all duration-200 transform hover:scale-[1.02] shadow-lg"
              >
                שלח קישור לאיפוס
              </button>
              
              <button
                type="button"
                onClick={() => setShowForgotPassword(false)}
                className="w-full text-slate-600 py-2 px-4 rounded-xl font-medium hover:bg-slate-100 transition-all duration-200"
              >
                חזרה להתחברות
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-200 flex items-center justify-center p-4">
      <div className="bg-white/95 backdrop-blur-sm border border-white/20 rounded-3xl p-8 w-full max-w-md shadow-2xl">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white text-2xl font-semibold">🏢</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-800 mb-2">מערכת CRM</h1>
          <p className="text-slate-600 font-medium">שי דירות ומשרדים בע״מ</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-center text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-2">
              כתובת אימייל
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleInputChange}
              required
              className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-right"
              placeholder="your.email@company.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-2">
              סיסמה
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              required
              className="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-right"
              placeholder="••••••••"
            />
          </div>

          <div className="flex items-center justify-between text-sm">
            <label className="flex items-center">
              <input type="checkbox" className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 ml-2" />
              זכור אותי
            </label>
            <button
              type="button"
              onClick={() => setShowForgotPassword(true)}
              className="text-blue-600 hover:text-blue-700 font-medium"
            >
              שכחת סיסמה?
            </button>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white py-3 px-4 rounded-xl font-medium hover:from-blue-700 hover:to-blue-800 transition-all duration-200 transform hover:scale-[1.02] shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white ml-3"></div>
                מתחבר...
              </div>
            ) : (
              'כניסה למערכת'
            )}
          </button>
        </form>

        {/* Professional Footer */}
        <div className="mt-8 pt-6 border-t border-slate-200 text-center">
          <p className="text-xs text-slate-500">
            מערכת מאובטחת עם הצפנה ברמה הגבוהה ביותר
          </p>
        </div>
      </div>
    </div>
  );
}