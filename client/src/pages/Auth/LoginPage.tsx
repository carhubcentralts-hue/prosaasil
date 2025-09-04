import { useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';
import { cn } from '../../shared/utils/cn';

// Placeholder components - we'll move the real ones later
function Button({ children, onClick, disabled, type = "button", className = "" }: any) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "w-full py-2 px-4 rounded-md font-medium transition-colors",
        "bg-primary text-primary-foreground hover:bg-primary/90",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
    >
      {children}
    </button>
  );
}

function Input({ placeholder, type, value, onChange, className = "" }: any) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      className={cn(
        "w-full px-3 py-2 border border-input rounded-md",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent",
        className
      )}
    />
  );
}

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { login, isAuthenticated, user } = useAuth();

  // Redirect if already logged in
  if (isAuthenticated && user) {
    const defaultRoute = user.role === 'admin' || user.role === 'manager' 
      ? '/app/admin/overview' 
      : '/app/business/overview';
    return <Navigate to={defaultRoute} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setLoading(true);
    setError('');

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'שגיאה בהתחברות');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50" dir="rtl">
      <div className="max-w-md w-full space-y-8 p-8">
        {/* Brand */}
        <div className="text-center">
          <div className="mx-auto h-12 w-12 bg-primary rounded-full flex items-center justify-center">
            <span className="text-white font-bold text-xl">ח</span>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            שי דירות ומשרדים
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            מערכת CRM חכמה עם בינה מלאכותית
          </p>
        </div>

        {/* Login Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                כתובת אימייל
              </label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e: any) => setEmail(e.target.value)}
                className="ltr text-left"
              />
            </div>
            
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                סיסמה
              </label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e: any) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="text-red-600 text-sm text-center">
              {error}
            </div>
          )}

          <Button
            type="submit"
            disabled={loading || !email || !password}
          >
            {loading ? 'מתחבר...' : 'התחבר'}
          </Button>

          <div className="text-center">
            <Link 
              to="/forgot" 
              className="text-sm text-primary hover:text-primary/80"
            >
              שכחת סיסמה?
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}