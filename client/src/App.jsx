import React, { useState } from 'react';

const App = () => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForgot, setShowForgot] = useState(false);

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

  const handleForgotPassword = () => {
    alert('אנא פנה למנהל המערכת לשחזור סיסמה');
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: 'white', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      fontFamily: 'Arial, sans-serif'
    }}>
      <div style={{ 
        maxWidth: '400px', 
        width: '100%', 
        margin: '0 20px'
      }}>
        {/* Login Card */}
        <div style={{
          backgroundColor: 'white',
          padding: '40px',
          borderRadius: '10px',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
          border: '1px solid #e5e5e5'
        }}>
          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: '30px' }}>
            <h1 style={{ 
              fontSize: '28px', 
              fontWeight: 'bold', 
              color: '#333', 
              margin: '0 0 10px 0'
            }}>
              שי דירות ומשרדים בע״מ
            </h1>
            <p style={{ 
              color: '#666', 
              fontSize: '16px',
              margin: '0'
            }}>
              מערכת ניהול לקוחות עם AI
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit}>
            {error && (
              <div style={{
                backgroundColor: '#fee',
                border: '1px solid #fcc',
                borderRadius: '5px',
                padding: '15px',
                marginBottom: '20px'
              }}>
                <p style={{ color: '#c33', fontSize: '14px', margin: '0' }}>{error}</p>
              </div>
            )}

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                fontWeight: 'bold',
                color: '#333'
              }}>
                שם משתמש
              </label>
              <input
                type="text"
                name="username"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '16px',
                  border: '2px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
                value={credentials.username}
                onChange={handleInputChange}
                placeholder="הזן שם משתמש"
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ 
                display: 'block', 
                marginBottom: '8px', 
                fontWeight: 'bold',
                color: '#333'
              }}>
                סיסמה
              </label>
              <input
                type="password"
                name="password"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '16px',
                  border: '2px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
                value={credentials.password}
                onChange={handleInputChange}
                placeholder="הזן סיסמה"
              />
            </div>

            {/* Forgot Password Link */}
            <div style={{ textAlign: 'right', marginBottom: '20px' }}>
              <button
                type="button"
                onClick={handleForgotPassword}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#007bff',
                  textDecoration: 'underline',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                שכחת סיסמה?
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '15px',
                fontSize: '18px',
                fontWeight: 'bold',
                color: 'white',
                backgroundColor: '#007bff',
                border: 'none',
                borderRadius: '5px',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1
              }}
            >
              {loading ? 'מתחבר...' : 'התחבר'}
            </button>
          </form>

          {/* Demo Credentials */}
          <div style={{
            marginTop: '30px',
            padding: '20px',
            backgroundColor: '#f8f9fa',
            borderRadius: '5px'
          }}>
            <h3 style={{ 
              fontWeight: 'bold', 
              color: '#333', 
              fontSize: '16px',
              margin: '0 0 10px 0'
            }}>
              פרטי התחברות לדמו:
            </h3>
            <div style={{ fontSize: '14px', color: '#666' }}>
              <p style={{ margin: '5px 0' }}><strong>מנהל:</strong> admin / admin123</p>
              <p style={{ margin: '5px 0' }}><strong>עסק:</strong> business / business123</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <p style={{ color: '#999', fontSize: '14px', margin: '0' }}>
            © 2025 מערכת ניהול לקוחות עם AI
          </p>
        </div>
      </div>
    </div>
  );
};

export default App;