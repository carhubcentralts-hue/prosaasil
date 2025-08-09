import React, { useState } from 'react';
import './styles/tokens.css';

const LoginPage = () => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      const data = await response.json();

      if (data.success) {
        // Store user data and redirect based on role
        localStorage.setItem('user', JSON.stringify(data.user));
        
        if (data.user.role === 'admin') {
          window.location.href = '/admin';
        } else {
          window.location.href = '/business';
        }
      } else {
        setError('שם משתמש או סיסמה שגויים');
      }
    } catch (err) {
      setError('שגיאה בהתחברות. נסה שוב.');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    setCredentials({
      ...credentials,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="max-w-md w-full mx-4">
        {/* Login Card */}
        <div className="card p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              שי דירות ומשרדים בע״מ
            </h1>
            <p className="text-gray-600">
              מערכת ניהול לקוחות עם AI
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-600 text-sm">{error}</p>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="username" className="form-label">
                שם משתמש
              </label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="form-input"
                value={credentials.username}
                onChange={handleInputChange}
                placeholder="הזן שם משתמש"
              />
            </div>

            <div className="form-group">
              <label htmlFor="password" className="form-label">
                סיסמה
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="form-input"
                value={credentials.password}
                onChange={handleInputChange}
                placeholder="הזן סיסמה"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full py-3 text-lg"
            >
              {loading ? 'מתחבר...' : 'התחבר'}
            </button>
          </form>

          {/* Demo Credentials */}
          <div className="mt-8 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-semibold text-gray-700 mb-2">פרטי התחברות:</h3>
            <div className="text-sm text-gray-600 space-y-1">
              <p><strong>מנהל:</strong> admin / admin123</p>
              <p><strong>עסק:</strong> business / business123</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-gray-500 text-sm">
            © 2025 מערכת ניהול לקוחות עם AI
          </p>
        </div>
      </div>
    </div>
  );
};

const App = () => {
  return <LoginPage />;
};

export default App;