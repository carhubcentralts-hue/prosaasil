import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  Eye, 
  EyeOff,
  User,
  Lock,
  Loader,
  AlertCircle,
  CheckCircle
} from 'lucide-react';

const LoginPage = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const navigate = useNavigate();

  // בדיקה אם המשתמש כבר מחובר
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    
    if (token && role) {
      // הפנה לדשבורד המתאים
      if (role === 'admin') {
        navigate('/admin/dashboard');
      } else if (role === 'business') {
        navigate('/business/dashboard');
      }
    }
  }, [navigate]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // נקה שגיאות כשהמשתמש מתחיל להקליד
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.username || !formData.password) {
      setError('נא למלא את כל השדות');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('Attempting login with:', { username: formData.username });
      
      const response = await axios.post('/api/login', {
        username: formData.username,
        password: formData.password
      });

      console.log('Login response:', response.data);

      const { token, role, name } = response.data;

      // שמור פרטי התחברות
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user_role', role);
      localStorage.setItem('user_name', name);

      setSuccess(`התחברות מוצלחת! ברוך הבא ${name}`);

      // המתן רגע ואז נווט
      setTimeout(() => {
        if (role === 'admin') {
          navigate('/admin/dashboard');
        } else if (role === 'business') {
          navigate('/business/dashboard');  
        } else {
          navigate('/dashboard');
        }
      }, 1500);

    } catch (error) {
      console.error('Login error:', error);
      
      if (error.response?.status === 401) {
        setError('שם משתמש או סיסמה שגויים');
      } else if (error.response?.status === 400) {
        setError('נתונים לא תקינים');
      } else {
        setError('שגיאה בהתחברות. נסה שוב');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center" dir="rtl">
      <div className="max-w-md w-full mx-4">
        {/* לוגו וכותרת */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl mx-auto mb-4 flex items-center justify-center">
            <User className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2 font-hebrew">
            ברוך הבא למערכת AgentLocator
          </h1>
          <p className="text-gray-600 font-hebrew">
            מערכת ניהול AI מתקדמת לעסקים
          </p>
        </div>

        {/* טופס התחברות */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* שדה שם משתמש */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2 font-hebrew">
                שם משתמש
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  className="block w-full pr-10 pl-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  placeholder="הכנס שם משתמש"
                  disabled={loading}
                />
              </div>
            </div>

            {/* שדה סיסמה */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2 font-hebrew">
                סיסמה
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  className="block w-full pr-10 pl-10 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  placeholder="הכנס סיסמה"
                  disabled={loading}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 left-0 pl-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={loading}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5 text-gray-400 hover:text-gray-600" />
                  ) : (
                    <Eye className="h-5 w-5 text-gray-400 hover:text-gray-600" />
                  )}
                </button>
              </div>
            </div>

            {/* הודעות שגיאה והצלחה */}
            {error && (
              <div className="flex items-center p-3 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-500 ml-2" />
                <span className="text-red-700 font-hebrew text-sm">{error}</span>
              </div>
            )}

            {success && (
              <div className="flex items-center p-3 bg-green-50 border border-green-200 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-500 ml-2" />
                <span className="text-green-700 font-hebrew text-sm">{success}</span>
              </div>
            )}

            {/* כפתור התחברות */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-hebrew"
            >
              {loading ? (
                <>
                  <Loader className="animate-spin -ml-1 mr-2 h-4 w-4" />
                  מתחבר...
                </>
              ) : (
                'התחבר למערכת'
              )}
            </button>
          </form>
        </div>

        {/* פרטי התחברות לדוגמה */}
        <div className="mt-6 bg-gray-50 rounded-lg p-4 border border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-3 font-hebrew">פרטי התחברות לדוגמה:</h3>
          <div className="space-y-2 text-xs text-gray-600 font-hebrew">
            <div>
              <strong>מנהל מערכת:</strong> admin / admin123
            </div>
            <div>
              <strong>עסק לדוגמה:</strong> business1 / biz1234
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;