import React, { useState, useEffect } from 'react';
import Login from './pages/Login';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';
import './index.css';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Auth check response:', data);
        if (data.success && data.user) {
          setUser(data.user);
        }
      } else {
        console.log('Auth check failed with status:', response.status);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (userData: User) => {
    console.log('Login successful, setting user:', userData);
    setUser(userData);
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      console.log('Logout successful');
    } catch (error) {
      console.error('Logout error:', error);
    }
    setUser(null);
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        fontFamily: 'Assistant, Arial, sans-serif',
        direction: 'rtl'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '4rem', marginBottom: '1rem', animation: 'pulse 2s infinite' }}>⏳</div>
          <div style={{ fontSize: '1.8rem', fontWeight: '600' }}>טוען מערכת AgentLocator...</div>
          <div style={{ fontSize: '1.1rem', opacity: 0.8, marginTop: '0.5rem' }}>
            מערכת CRM מתקדמת עם בינה מלאכותית
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Render role-based dashboard
  if (user.role === 'admin') {
    return <AdminDashboard user={user} onLogout={handleLogout} />;
  } else {
    return <BusinessDashboard user={user} onLogout={handleLogout} />;
  }
}