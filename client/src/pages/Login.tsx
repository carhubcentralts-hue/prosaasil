import React, { useState } from 'react';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

interface LoginProps {
  onLogin: (user: User) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ 
          username: email, // Send as username to match backend
          password 
        }),
      });

      const data = await response.json();

      if (response.ok && data.success && data.user) {
        onLogin(data.user);
      } else {
        setError(data.error || 'שגיאה בהתחברות');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('שגיאה בהתחברות לשרת');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      direction: 'rtl',
      fontFamily: 'Assistant, Arial, sans-serif'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        padding: '2rem',
        background: 'white',
        borderRadius: '20px',
        boxShadow: '0 20px 50px rgba(0,0,0,0.1)',
        margin: '1rem'
      }}>
        <div style={{
          textAlign: 'center',
          marginBottom: '2rem'
        }}>
          <h1 style={{
            fontSize: '1.8rem',
            fontWeight: '700',
            color: '#2d3748',
            marginBottom: '0.5rem'
          }}>
            AgentLocator CRM
          </h1>
          <p style={{
            color: '#718096',
            fontSize: '0.9rem'
          }}>
            מערכת ניהול לקוחות עם בינה מלאכותית
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{
              display: 'block',
              marginBottom: '0.5rem',
              fontWeight: '600',
              color: '#4a5568'
            }}>
              שם משתמש
            </label>
            <input
              type="text"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="הכנס שם משתמש"
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '2px solid #e2e8f0',
                borderRadius: '12px',
                fontSize: '1rem',
                direction: 'ltr',
                textAlign: 'left'
              }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{
              display: 'block',
              marginBottom: '0.5rem',
              fontWeight: '600',
              color: '#4a5568'
            }}>
              סיסמה
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="הכנס סיסמה"
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '2px solid #e2e8f0',
                borderRadius: '12px',
                fontSize: '1rem',
                direction: 'ltr',
                textAlign: 'left'
              }}
            />
          </div>

          {error && (
            <div style={{
              color: '#e53e3e',
              background: '#fed7d7',
              padding: '0.75rem',
              borderRadius: '8px',
              marginBottom: '1.5rem',
              fontSize: '0.9rem',
              textAlign: 'center'
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: loading ? '#cbd5e0' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              fontSize: '1rem',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.3s ease'
            }}
          >
            {loading ? 'מתחבר...' : 'כניסה למערכת'}
          </button>
        </form>

        <div style={{
          marginTop: '2rem',
          padding: '1rem',
          background: '#f7fafc',
          borderRadius: '12px',
          fontSize: '0.85rem',
          color: '#4a5568'
        }}>
          <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>
            פרטי התחברות:
          </div>
          <div>admin / admin (מנהל מערכת)</div>
          <div>shai / shai123 (שי דירות ומשרדים)</div>
        </div>
      </div>
    </div>
  );
}