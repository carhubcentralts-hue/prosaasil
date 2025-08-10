import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Lock, Eye, EyeOff, Shield, Building, AlertCircle } from 'lucide-react';

const LoginPage = () => {
  const { login, loading } = useAuth();
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const result = await login(formData.email, formData.password);
      if (!result.success) {
        setError(result.error || 'שגיאה בהתחברות');
      }
    } catch (error) {
      setError('שגיאה בחיבור לשרת');
    } finally {
      setIsSubmitting(false);
    }
  };

  const demoAccounts = [
    {
      type: 'admin',
      email: 'admin@example.com',
      password: 'admin123',
      label: 'מנהל מערכת',
      icon: Shield,
      description: 'גישה מלאה לכל העסקים והנתונים'
    },
    {
      type: 'business',
      email: 'shai@example.com', 
      password: 'shai123',
      label: 'שי דירות ומשרדים',
      icon: Building,
      description: 'גישה לנתוני העסק בלבד'
    }
  ];

  const fillDemo = (email, password) => {
    setFormData({ email, password });
    setError('');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gradient-start to-gradient-end relative overflow-hidden">
      {/* רקע אנימציה */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-white rounded-full mix-blend-overlay filter blur-xl opacity-70 animate-pulse"></div>
        <div className="absolute top-3/4 right-1/4 w-64 h-64 bg-blue-300 rounded-full mix-blend-overlay filter blur-xl opacity-70 animate-pulse delay-1000"></div>
      </div>

      <div className="relative z-10 w-full max-w-md mx-4">
        {/* כרטיס התחברות ראשי */}
        <div className="glass-effect rounded-2xl shadow-2xl p-8 backdrop-blur-sm border border-white/20">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full mb-4 shadow-lg">
              <User className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">התחברות למערכת</h1>
            <p className="text-gray-600">AgentLocator - מרכז קריאות AI</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* שדה אימייל */}
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700 text-right">
                כתובת אימייל
              </label>
              <div className="relative">
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className="input-field pr-12 text-right"
                  placeholder="הזן אימייל"
                  disabled={isSubmitting}
                />
                <User className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              </div>
            </div>

            {/* שדה סיסמה */}
            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700 text-right">
                סיסמה
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={formData.password}
                  onChange={handleChange}
                  className="input-field pr-12 pl-12 text-right"
                  placeholder="הזן סיסמה"
                  disabled={isSubmitting}
                />
                <Lock className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  disabled={isSubmitting}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* הודעת שגיאה */}
            {error && (
              <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 animate-fade-in-up">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span className="text-sm">{error}</span>
              </div>
            )}

            {/* כפתור התחברות */}
            <button
              type="submit"
              disabled={isSubmitting || !formData.email || !formData.password}
              className="btn-primary w-full py-4 text-lg font-bold disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden"
            >
              {isSubmitting ? (
                <div className="flex items-center justify-center">
                  <div className="loading-spinner w-5 h-5 ml-3"></div>
                  מתחבר...
                </div>
              ) : (
                'כניסה למערכת'
              )}
            </button>
          </form>
        </div>

        {/* חשבונות דמו */}
        <div className="mt-8 space-y-4">
          <h3 className="text-center text-gray-700 font-semibold">חשבונות דמו להתנסות</h3>
          
          {demoAccounts.map((account, index) => (
            <div
              key={account.type}
              className="glass-effect rounded-xl p-4 border border-white/20 hover:shadow-lg transition-all duration-300 cursor-pointer hover-lift animate-slide-in-right"
              style={{ animationDelay: `${index * 100}ms` }}
              onClick={() => fillDemo(account.email, account.password)}
            >
              <div className="flex items-center space-x-4">
                <div className={`p-2 rounded-lg ${account.type === 'admin' ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'}`}>
                  <account.icon className="w-5 h-5" />
                </div>
                <div className="flex-1 text-right">
                  <h4 className="font-semibold text-gray-800">{account.label}</h4>
                  <p className="text-sm text-gray-600">{account.description}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {account.email} / {account.password}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* תיאור המערכת */}
        <div className="mt-8 text-center">
          <p className="text-gray-600 text-sm leading-relaxed">
            מערכת ניהול קריאות AI עם תמיכה בעברית
            <br />
            מיועד לעסקי נדל"ן ושירותים
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;