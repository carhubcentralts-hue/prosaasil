import React, { useState, useEffect } from 'react';
import '../styles/tokens.css';

const BusinessDashboard = () => {
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState({
    totalCalls: 0,
    totalCustomers: 0,
    whatsappMessages: 0,
    todayCalls: 0
  });

  useEffect(() => {
    // Get user from localStorage
    const userData = localStorage.getItem('user');
    if (userData) {
      setUser(JSON.parse(userData));
    }

    // Fetch business stats
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/business/stats');
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

  const businessFeatures = [
    { 
      title: 'CRM מתקדם', 
      description: 'ניהול לקוחות ועסקאות',
      icon: '👥',
      link: '/business/crm',
      enabled: true
    },
    { 
      title: 'מערכת שיחות', 
      description: 'ניהול שיחות נכנסות ויוצאות',
      icon: '📞',
      link: '/business/calls',
      enabled: true
    },
    { 
      title: 'WhatsApp Business', 
      description: 'ניהול הודעות WhatsApp',
      icon: '💬',
      link: '/business/whatsapp',
      enabled: true
    },
    { 
      title: 'חתימות דיגיטליות', 
      description: 'יצירת וניהול חתימות',
      icon: '✍️',
      link: '/business/signatures',
      enabled: false
    },
    { 
      title: 'הצעות מחיר', 
      description: 'יצירת הצעות מחיר מקצועיות',
      icon: '📋',
      link: '/business/proposals',
      enabled: false
    },
    { 
      title: 'חשבוניות', 
      description: 'ניהול חשבוניות ותשלומים',
      icon: '🧾',
      link: '/business/invoices',
      enabled: false
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
                דשבורד עסק - AgentLocator
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
            ברוך הבא למערכת הניהול שלך
          </h2>
          <p className="text-gray-600">
            נהל את הלקוחות, השיחות וההודעות שלך במקום אחד
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-lg">
                <span className="text-2xl">📞</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">שיחות היום</p>
                <p className="text-2xl font-bold text-gray-900">{stats.todayCalls}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-green-100 rounded-lg">
                <span className="text-2xl">👥</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">לקוחות פעילים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalCustomers}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-purple-100 rounded-lg">
                <span className="text-2xl">💬</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">הודעות WhatsApp</p>
                <p className="text-2xl font-bold text-gray-900">{stats.whatsappMessages}</p>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center">
              <div className="p-2 bg-orange-100 rounded-lg">
                <span className="text-2xl">📈</span>
              </div>
              <div className="mr-4">
                <p className="text-sm font-medium text-gray-600">סה״כ שיחות</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalCalls}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {businessFeatures.map((feature, index) => (
            <div 
              key={index} 
              className={`card p-6 transition-all ${
                feature.enabled 
                  ? 'hover:shadow-md cursor-pointer' 
                  : 'opacity-50 cursor-not-allowed'
              }`}
            >
              <div className="flex items-start">
                <div className={`p-3 rounded-lg ${
                  feature.enabled ? 'bg-blue-50' : 'bg-gray-100'
                }`}>
                  <span className="text-3xl">{feature.icon}</span>
                </div>
                <div className="mr-4 flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {feature.title}
                    </h3>
                    {!feature.enabled && (
                      <span className="px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded">
                        בקרוב
                      </span>
                    )}
                  </div>
                  <p className="text-gray-600 text-sm mb-4">
                    {feature.description}
                  </p>
                  <button 
                    className={`btn text-sm ${
                      feature.enabled 
                        ? 'btn-primary' 
                        : 'btn-secondary cursor-not-allowed'
                    }`}
                    disabled={!feature.enabled}
                  >
                    {feature.enabled ? 'עבור לדף ←' : 'לא זמין'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="mt-12">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">פעולות מהירות</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="card p-4 text-right hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <span className="text-2xl mr-3">➕</span>
                <div>
                  <p className="font-semibold text-gray-900">הוסף לקוח חדש</p>
                  <p className="text-sm text-gray-600">יצירת לקוח חדש במערכת</p>
                </div>
              </div>
            </button>

            <button className="card p-4 text-right hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <span className="text-2xl mr-3">📊</span>
                <div>
                  <p className="font-semibold text-gray-900">צפה בדוחות</p>
                  <p className="text-sm text-gray-600">דוחות ואנליטיקה מתקדמת</p>
                </div>
              </div>
            </button>

            <button className="card p-4 text-right hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <span className="text-2xl mr-3">⚙️</span>
                <div>
                  <p className="font-semibold text-gray-900">הגדרות</p>
                  <p className="text-sm text-gray-600">הגדרות עסק ותצורות</p>
                </div>
              </div>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default BusinessDashboard;