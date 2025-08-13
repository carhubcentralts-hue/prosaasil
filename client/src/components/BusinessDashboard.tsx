import { useAuth } from '../hooks/useAuth';

interface BusinessDashboardProps {
  onBack: () => void;
}

export function BusinessDashboard({ onBack }: BusinessDashboardProps) {
  const { user } = useAuth();

  const stats = [
    { title: 'שיחות היום', value: '24', icon: '📞', color: 'blue' },
    { title: 'הודעות WhatsApp', value: '67', icon: '💬', color: 'green' },
    { title: 'לקוחות חדשים', value: '8', icon: '👥', color: 'purple' },
    { title: 'פגישות שנקבעו', value: '5', icon: '📅', color: 'orange' },
  ];

  const recentActivities = [
    { time: '09:45', type: 'call', message: 'שיחה נכנסת מ-054-123-4567' },
    { time: '09:30', type: 'whatsapp', message: 'הודעת WhatsApp חדשה מדוד כהן' },
    { time: '09:15', type: 'appointment', message: 'נקבעה פגישה עם משה לוי ליום ראשון' },
    { time: '09:00', type: 'lead', message: 'ליד חדש עבור דירת 3 חדרים בתל אביב' },
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'call': return '📞';
      case 'whatsapp': return '💬';
      case 'appointment': return '📅';
      case 'lead': return '🎯';
      default: return '📋';
    }
  };

  const getStatColor = (color: string) => {
    switch (color) {
      case 'blue': return 'bg-blue-50 border-blue-200 text-blue-600';
      case 'green': return 'bg-green-50 border-green-200 text-green-600';
      case 'purple': return 'bg-purple-50 border-purple-200 text-purple-600';
      case 'orange': return 'bg-orange-50 border-orange-200 text-orange-600';
      default: return 'bg-gray-50 border-gray-200 text-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8" dir="rtl">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold text-gray-900">דאשבורד עסק</h1>
            <button
              onClick={onBack}
              className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 transition-colors"
              data-testid="button-back"
            >
              חזור לתפריט ראשי
            </button>
          </div>
          <p className="text-gray-600">
            שלום {user?.firstName} {user?.lastName} • שי דירות ומשרדים בע״מ
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <div
              key={index}
              className={`border rounded-lg p-6 ${getStatColor(stat.color)}`}
              data-testid={`stat-${stat.title.replace(/\s+/g, '-')}`}
            >
              <div className="text-center">
                <div className="text-4xl mb-2">{stat.icon}</div>
                <div className="text-3xl font-bold">{stat.value}</div>
                <div className="font-medium" dir="rtl">{stat.title}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recent Activity */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4" dir="rtl">פעילות אחרונה</h2>
            <div className="space-y-4">
              {recentActivities.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-start space-x-3 space-x-reverse p-3 bg-gray-50 rounded-lg"
                  data-testid={`activity-${index}`}
                >
                  <div className="text-2xl">{getActivityIcon(activity.type)}</div>
                  <div className="flex-1" dir="rtl">
                    <div className="text-sm text-gray-900">{activity.message}</div>
                    <div className="text-xs text-gray-500">{activity.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4" dir="rtl">פעולות מהירות</h2>
            <div className="grid grid-cols-1 gap-4">
              <button
                className="flex items-center justify-center space-x-2 space-x-reverse p-4 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                data-testid="button-new-call"
                dir="rtl"
              >
                <span className="text-2xl">📞</span>
                <span className="font-medium text-blue-800">יצירת שיחה חדשה</span>
              </button>

              <button
                className="flex items-center justify-center space-x-2 space-x-reverse p-4 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                data-testid="button-new-whatsapp"
                dir="rtl"
              >
                <span className="text-2xl">💬</span>
                <span className="font-medium text-green-800">שליחת הודעת WhatsApp</span>
              </button>

              <button
                className="flex items-center justify-center space-x-2 space-x-reverse p-4 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-colors"
                data-testid="button-new-customer"
                dir="rtl"
              >
                <span className="text-2xl">👥</span>
                <span className="font-medium text-purple-800">הוספת לקוח חדש</span>
              </button>

              <button
                className="flex items-center justify-center space-x-2 space-x-reverse p-4 bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors"
                data-testid="button-new-appointment"
                dir="rtl"
              >
                <span className="text-2xl">📅</span>
                <span className="font-medium text-orange-800">קביעת פגישה</span>
              </button>
            </div>
          </div>
        </div>

        {/* Business Info */}
        <div className="mt-8 bg-gray-50 border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4" dir="rtl">פרטי העסק</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" dir="rtl">
            <div className="text-center p-4">
              <div className="text-lg font-semibold text-gray-900">שי דירות ומשרדים בע״מ</div>
              <div className="text-sm text-gray-600">שם העסק</div>
            </div>
            <div className="text-center p-4">
              <div className="text-lg font-semibold text-gray-900">נדל״ן</div>
              <div className="text-sm text-gray-600">תחום פעילות</div>
            </div>
            <div className="text-center p-4">
              <div className="text-lg font-semibold text-gray-900">+972-50-123-4567</div>
              <div className="text-sm text-gray-600">טלפון</div>
            </div>
            <div className="text-center p-4">
              <div className="text-lg font-semibold text-gray-900">תל אביב</div>
              <div className="text-sm text-gray-600">מיקום</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}