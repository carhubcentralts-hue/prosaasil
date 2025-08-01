import { useQuery } from '@tanstack/react-query';

export default function Dashboard() {
  const { data: healthCheck } = useQuery({
    queryKey: ['/api/health'],
  });

  const stats = [
    {
      title: 'סה"כ לקוחות',
      value: '2,847',
      change: '+12%',
      trend: 'up',
      icon: 'fas fa-users',
      color: 'blue'
    },
    {
      title: 'שיחות היום',
      value: '134',
      change: '+8%',
      trend: 'up',
      icon: 'fas fa-phone',
      color: 'green'
    },
    {
      title: 'הודעות WhatsApp',
      value: '3,562',
      change: '+23%',
      trend: 'up',
      icon: 'fab fa-whatsapp',
      color: 'green'
    },
    {
      title: 'חשבוניות פתוחות',
      value: '₪47,500',
      change: '-5%',
      trend: 'down',
      icon: 'fas fa-file-invoice-dollar',
      color: 'orange'
    }
  ];

  const recentActivities = [
    {
      type: 'call',
      title: 'שיחה חדשה עם יוסי כהן',
      time: 'לפני 5 דקות',
      status: 'completed',
      icon: 'fas fa-phone'
    },
    {
      type: 'whatsapp',
      title: 'הודעת WhatsApp מ-רחל לוי',
      time: 'לפני 12 דקות',
      status: 'pending',
      icon: 'fab fa-whatsapp'
    },
    {
      type: 'invoice',
      title: 'חשבונית #1234 נשלחה',
      time: 'לפני 25 דקות',
      status: 'sent',
      icon: 'fas fa-file-invoice'
    },
    {
      type: 'signature',
      title: 'חוזה נחתם - אבי רוזן',
      time: 'לפני שעה',
      status: 'signed',
      icon: 'fas fa-signature'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">לוח הבקרה</h1>
          <p className="text-gray-600 mt-1">סקירה כללית של פעילות המערכת</p>
        </div>
        <div className="flex items-center space-x-reverse space-x-3">
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            healthCheck?.status === 'OK' 
              ? 'bg-green-100 text-green-800' 
              : 'bg-red-100 text-red-800'
          }`}>
            <i className={`fas ${healthCheck?.status === 'OK' ? 'fa-check-circle' : 'fa-exclamation-circle'} ml-1`}></i>
            {healthCheck?.status === 'OK' ? 'מערכת פעילה' : 'בעיה במערכת'}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
                <div className={`flex items-center mt-2 text-sm ${
                  stat.trend === 'up' ? 'text-green-600' : 'text-red-600'
                }`}>
                  <i className={`fas ${stat.trend === 'up' ? 'fa-arrow-up' : 'fa-arrow-down'} ml-1`}></i>
                  {stat.change} מהחודש הקודם
                </div>
              </div>
              <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                stat.color === 'blue' ? 'bg-blue-100' :
                stat.color === 'green' ? 'bg-green-100' :
                stat.color === 'orange' ? 'bg-orange-100' : 'bg-gray-100'
              }`}>
                <i className={`${stat.icon} text-lg ${
                  stat.color === 'blue' ? 'text-blue-600' :
                  stat.color === 'green' ? 'text-green-600' :
                  stat.color === 'orange' ? 'text-orange-600' : 'text-gray-600'
                }`}></i>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activities */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">פעילות אחרונה</h2>
            <p className="text-sm text-gray-600">עדכונים מהשעות האחרונות</p>
          </div>
          <div className="divide-y divide-gray-200">
            {recentActivities.map((activity, index) => (
              <div key={index} className="p-6 hover:bg-gray-50 transition-colors">
                <div className="flex items-center space-x-reverse space-x-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    activity.type === 'call' ? 'bg-blue-100' :
                    activity.type === 'whatsapp' ? 'bg-green-100' :
                    activity.type === 'invoice' ? 'bg-orange-100' :
                    'bg-purple-100'
                  }`}>
                    <i className={`${activity.icon} ${
                      activity.type === 'call' ? 'text-blue-600' :
                      activity.type === 'whatsapp' ? 'text-green-600' :
                      activity.type === 'invoice' ? 'text-orange-600' :
                      'text-purple-600'
                    }`}></i>
                  </div>
                  <div className="flex-1">
                    <h3 className="text-sm font-medium text-gray-900">{activity.title}</h3>
                    <p className="text-xs text-gray-500 mt-1">{activity.time}</p>
                  </div>
                  <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                    activity.status === 'completed' ? 'bg-green-100 text-green-800' :
                    activity.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    activity.status === 'sent' ? 'bg-blue-100 text-blue-800' :
                    'bg-purple-100 text-purple-800'
                  }`}>
                    {activity.status === 'completed' ? 'הושלם' :
                     activity.status === 'pending' ? 'ממתין' :
                     activity.status === 'sent' ? 'נשלח' : 'נחתם'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-6">
          {/* Quick Stats */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">פעולות מהירות</h3>
            <div className="space-y-3">
              <button className="w-full bg-blue-500 hover:bg-blue-600 text-white py-3 px-4 rounded-lg font-medium transition-colors">
                <i className="fas fa-user-plus ml-2"></i>
                הוסף לקוח חדש
              </button>
              <button className="w-full bg-green-500 hover:bg-green-600 text-white py-3 px-4 rounded-lg font-medium transition-colors">
                <i className="fas fa-phone ml-2"></i>
                התחל שיחה
              </button>
              <button className="w-full bg-teal-500 hover:bg-teal-600 text-white py-3 px-4 rounded-lg font-medium transition-colors">
                <i className="fab fa-whatsapp ml-2"></i>
                שלח WhatsApp
              </button>
              <button className="w-full bg-orange-500 hover:bg-orange-600 text-white py-3 px-4 rounded-lg font-medium transition-colors">
                <i className="fas fa-file-invoice ml-2"></i>
                צור חשבונית
              </button>
            </div>
          </div>

          {/* Today's Schedule */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">לוח זמנים היום</h3>
            <div className="space-y-3">
              <div className="flex items-center space-x-reverse space-x-3 p-3 bg-blue-50 rounded-lg">
                <div className="w-2 h-8 bg-blue-500 rounded-full"></div>
                <div>
                  <p className="text-sm font-medium text-gray-900">פגישה עם דני שמש</p>
                  <p className="text-xs text-gray-600">14:00 - 15:00</p>
                </div>
              </div>
              <div className="flex items-center space-x-reverse space-x-3 p-3 bg-green-50 rounded-lg">
                <div className="w-2 h-8 bg-green-500 rounded-full"></div>
                <div>
                  <p className="text-sm font-medium text-gray-900">שיחת המכירות</p>
                  <p className="text-xs text-gray-600">16:30 - 17:00</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}