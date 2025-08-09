import React, { useState, useEffect } from 'react';
import './styles/tokens.css';

const App = () => {
  const [businessData, setBusinessData] = useState({
    name: "שי דירות ומשרדים בע״מ",
    phone: "+972-3-555-7777",
    type: "נדלן ותיווך",
    prompt: "אני עוזר AI לחברת שי דירות ומשרדים בע״מ. אני כאן לעזור עם פניות לגבי נכסים, השכרות, מכירות ושירותי נדלן. איך אוכל לעזור לך היום?"
  });

  const [stats, setStats] = useState({
    totalCalls: 127,
    todaysCalls: 8,
    totalCustomers: 45,
    whatsappMessages: 23
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 text-center">
            AgentLocator CRM - מערכת ניהול לקוחות מתקדמת
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Business Info Card */}
        <div className="card p-8 mb-8">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {businessData.name}
            </h2>
            <p className="text-lg text-gray-600">{businessData.type}</p>
            <p className="text-gray-600">{businessData.phone}</p>
          </div>

          {/* AI Prompt Display */}
          <div className="bg-blue-50 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              פרומפט AI לעסק:
            </h3>
            <p className="text-gray-700 leading-relaxed">
              {businessData.prompt}
            </p>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="card p-6 text-center">
            <div className="text-3xl mb-2">📞</div>
            <div className="text-2xl font-bold text-gray-900">{stats.todaysCalls}</div>
            <div className="text-sm text-gray-600">שיחות היום</div>
          </div>

          <div className="card p-6 text-center">
            <div className="text-3xl mb-2">📈</div>
            <div className="text-2xl font-bold text-gray-900">{stats.totalCalls}</div>
            <div className="text-sm text-gray-600">סה״כ שיחות</div>
          </div>

          <div className="card p-6 text-center">
            <div className="text-3xl mb-2">👥</div>
            <div className="text-2xl font-bold text-gray-900">{stats.totalCustomers}</div>
            <div className="text-sm text-gray-600">לקוחות</div>
          </div>

          <div className="card p-6 text-center">
            <div className="text-3xl mb-2">💬</div>
            <div className="text-2xl font-bold text-gray-900">{stats.whatsappMessages}</div>
            <div className="text-sm text-gray-600">הודעות WhatsApp</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="card p-6 hover:shadow-md transition-shadow cursor-pointer">
            <div className="text-center">
              <div className="text-4xl mb-4">📞</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                מערכת שיחות
              </h3>
              <p className="text-gray-600 text-sm mb-4">
                ניהול שיחות נכנסות ויוצאות עם AI בעברית
              </p>
              <div className="px-4 py-2 bg-green-100 text-green-800 rounded-lg text-sm">
                פעיל
              </div>
            </div>
          </div>

          <div className="card p-6 hover:shadow-md transition-shadow cursor-pointer">
            <div className="text-center">
              <div className="text-4xl mb-4">💬</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                WhatsApp Business
              </h3>
              <p className="text-gray-600 text-sm mb-4">
                ניהול הודעות WhatsApp עם לקוחות
              </p>
              <div className="px-4 py-2 bg-green-100 text-green-800 rounded-lg text-sm">
                פעיל
              </div>
            </div>
          </div>

          <div className="card p-6 hover:shadow-md transition-shadow cursor-pointer">
            <div className="text-center">
              <div className="text-4xl mb-4">👥</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                CRM לקוחות
              </h3>
              <p className="text-gray-600 text-sm mb-4">
                ניהול לקוחות ומעקב אחר פעילות
              </p>
              <div className="px-4 py-2 bg-green-100 text-green-800 rounded-lg text-sm">
                פעיל
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="text-center mt-12 text-gray-500">
          <p>© 2025 AgentLocator CRM - מערכת ניהול לקוחות מתקדמת עם AI</p>
          <p className="text-sm mt-2">נבנה במיוחד עבור שי דירות ומשרדים בע״מ</p>
        </footer>
      </main>
    </div>
  );
};

export default App;