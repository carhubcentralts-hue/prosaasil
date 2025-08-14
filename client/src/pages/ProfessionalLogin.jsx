import React, { useState } from 'react';

const ProfessionalLogin = ({ onLogin }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError(''); // Clear error when user types
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok && data.success) {
        onLogin(data.user);
      } else {
        setError(data.error || 'שגיאה בהתחברות');
      }
    } catch (err) {
      setError('שגיאת תקשורת. נסה שוב.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #3b82f6 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      fontFamily: 'Assistant, -apple-system, sans-serif'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '20px',
        padding: '3rem',
        width: '100%',
        maxWidth: '450px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        direction: 'rtl'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <div style={{ 
            fontSize: '3rem', 
            marginBottom: '1rem',
            background: 'linear-gradient(135deg, #1e3a8a, #3b82f6)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            🏢
          </div>
          <h1 style={{ 
            fontSize: '1.75rem', 
            fontWeight: '700', 
            color: '#1e293b',
            margin: '0 0 0.5rem 0'
          }}>
            מערכת ניהול שיחות AI
          </h1>
          <p style={{ 
            color: '#64748b',
            margin: 0,
            fontSize: '1rem'
          }}>
            שי דירות ומשרדים בע״מ
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ 
              display: 'block', 
              fontSize: '0.95rem', 
              fontWeight: '600',
              color: '#374151',
              marginBottom: '0.75rem'
            }}>
              דואר אלקטרוני
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              style={{
                width: '100%',
                padding: '1rem',
                border: '2px solid #e5e7eb',
                borderRadius: '12px',
                fontSize: '1rem',
                outline: 'none',
                transition: 'all 0.2s ease',
                boxSizing: 'border-box',
                backgroundColor: '#f9fafb'
              }}
              onFocus={(e) => {
                e.target.style.borderColor = '#3b82f6';
                e.target.style.backgroundColor = 'white';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = '#e5e7eb';
                e.target.style.backgroundColor = '#f9fafb';
              }}
              placeholder="הזן דואר אלקטרוני"
              required
            />
          </div>

          <div style={{ marginBottom: '2rem' }}>
            <label style={{ 
              display: 'block', 
              fontSize: '0.95rem', 
              fontWeight: '600',
              color: '#374151',
              marginBottom: '0.75rem'
            }}>
              סיסמה
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              style={{
                width: '100%',
                padding: '1rem',
                border: '2px solid #e5e7eb',
                borderRadius: '12px',
                fontSize: '1rem',
                outline: 'none',
                transition: 'all 0.2s ease',
                boxSizing: 'border-box',
                backgroundColor: '#f9fafb'
              }}
              onFocus={(e) => {
                e.target.style.borderColor = '#3b82f6';
                e.target.style.backgroundColor = 'white';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = '#e5e7eb';
                e.target.style.backgroundColor = '#f9fafb';
              }}
              placeholder="הזן סיסמה"
              required
            />
          </div>

          {error && (
            <div style={{
              background: 'linear-gradient(135deg, #fef2f2, #fee2e2)',
              border: '1px solid #fca5a5',
              color: '#dc2626',
              padding: '1rem',
              borderRadius: '12px',
              marginBottom: '1.5rem',
              fontSize: '0.9rem',
              textAlign: 'center',
              fontWeight: '500'
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              background: loading 
                ? '#9ca3af' 
                : 'linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%)',
              color: 'white',
              padding: '1rem',
              border: 'none',
              borderRadius: '12px',
              fontSize: '1.1rem',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              marginBottom: '2rem',
              boxShadow: loading ? 'none' : '0 4px 14px 0 rgba(59, 130, 246, 0.39)'
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.target.style.transform = 'translateY(-2px)';
                e.target.style.boxShadow = '0 8px 25px 0 rgba(59, 130, 246, 0.5)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                e.target.style.transform = 'translateY(0)';
                e.target.style.boxShadow = '0 4px 14px 0 rgba(59, 130, 246, 0.39)';
              }
            }}
          >
            {loading ? 'מתחבר...' : 'כניסה למערכת'}
          </button>
        </form>

        {/* Credentials Helper */}
        <div style={{
          padding: '1.5rem',
          background: 'linear-gradient(135deg, #f0f9ff, #e0f2fe)',
          border: '1px solid #7dd3fc',
          borderRadius: '16px',
          fontSize: '0.85rem',
          color: '#0c4a6e'
        }}>
          <div style={{ 
            marginBottom: '1rem', 
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}>
            🔐 פרטי התחברות למערכת:
          </div>
          <div style={{ lineHeight: '1.6' }}>
            <div><strong>מנהל:</strong> admin@shai.com / admin123</div>
            <div><strong>מנהל ראשי:</strong> admin@shai-realestate.co.il / admin123456</div>
            <div><strong>משתמש עסק:</strong> shai@shai-realestate.co.il / shai123</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfessionalLogin;