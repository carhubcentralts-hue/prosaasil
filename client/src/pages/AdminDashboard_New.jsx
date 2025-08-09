import React, { useState, useEffect } from 'react';
import '../styles/tokens.css';

const AdminDashboard = () => {
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState({
    totalBusinesses: 0,
    totalUsers: 0,
    totalCalls: 0,
    activeUsers: 0
  });

  useEffect(() => {
    // Get user from localStorage
    const userData = localStorage.getItem('user');
    if (userData) {
      setUser(JSON.parse(userData));
    }

    // Fetch dashboard stats
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/admin/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/auth/logout', { method: 'POST' });
      localStorage.removeItem('user');
      window.location.href = '/';
    } catch (err) {
      console.error('Logout error:', err);
    }
  };

  const navigationItems = [
    { 
      title: 'ניהול עסקים', 
      description: 'הוספה, עריכה וניהול עסקים במערכת',
      icon: '🏢',
      link: '/admin/businesses'
    },
    { 
      title: 'ניהול משתמשים', 
      description: 'ניהול הרשאות ומשתמשי המערכת',
      icon: '👥',
      link: '/admin/users'
    },
    { 
      title: 'ניתוח שיחות', 
      description: 'ניתוח ודוחות על שיחות במערכת',
      icon: '📞',
      link: '/admin/calls'
    },
    { 
      title: 'הגדרות מערכת', 
      description: 'הגדרות כלליות ותצורת המערכת',
      icon: '⚙️',
      link: '/admin/settings'
    },
    { 
      title: 'אבטחה ולוגים', 
      description: 'ניטור אבטחה ובדיקת לוגי המערכת',
      icon: '🔒',
      link: '/admin/security'
    },
    { 
      title: 'דוחות ואנליטיקה', 
      description: 'דוחות מתקדמים וניתוח נתונים',
      icon: '📊',
      link: '/admin/analytics'
    }
  ];

  if (!user) {
    return <div>טוען...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                דשבורד מנהל - AgentLocator
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">
                שלום, {user.username}
              </span>
              <button 
                onClick={handleLogout}
                className="btn btn-secondary text-sm"
              >
                התנתק
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            ברוך הבא למערכת הניהול
          </h2>
          <p className="text-gray-600">
            מכאן תוכל לנהל את כל העסקים, המשתמשים והתצורות במערכת AgentLocator
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-lg">
                <span className="text-2xl">🏢</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">עסקים פעילים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalBusinesses}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-green-100 rounded-lg">
                <span className="text-2xl">👥</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">משתמשים רשומים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalUsers}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-purple-100 rounded-lg">
                <span className="text-2xl">📞</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">שיחות היום</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalCalls}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-orange-100 rounded-lg">
                <span className="text-2xl">⚡</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">משתמשים פעילים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.activeUsers}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {navigationItems.map((item, index) => (
            <div key={index} className="card p-6 hover:shadow-md transition-shadow cursor-pointer">
              <div className="flex items-start">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <span className="text-3xl">{item.icon}</span>
                </div>
                <div className="mr-4 flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {item.title}
                  </h3>
                  <p className="text-gray-600 text-sm mb-4">
                    {item.description}
                  </p>
                  <button className="btn btn-primary text-sm">
                    עבור לדף ←
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;