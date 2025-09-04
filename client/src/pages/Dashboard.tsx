import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  MessageCircle, 
  Users, 
  TrendingUp,
  Calendar,
  AlertCircle,
  Activity,
  DollarSign,
  Clock,
  CheckCircle
} from 'lucide-react';

function Dashboard({ business, permissions }) {
  const [stats, setStats] = useState({});
  const [recentActivity, setRecentActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, [business?.id]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsRes, activityRes] = await Promise.all([
        fetch(`/api/dashboard/stats?business_id=${business?.id}`),
        fetch(`/api/dashboard/activity?business_id=${business?.id}`)
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (activityRes.ok) {
        const activityData = await activityRes.json();
        setRecentActivity(activityData.activities || []);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    {
      name: 'מוקד שיחות',
      description: 'ניהול שיחות נכנסות ויוצאות',
      href: '/calls',
      icon: Phone,
      enabled: permissions.calls_enabled,
      color: 'bg-blue-500',
      stats: stats.calls_today || 0,
      label: 'שיחות היום'
    },
    {
      name: 'וואטסאפ',
      description: 'הודעות ושיחות וואטסאפ',
      href: '/whatsapp',
      icon: MessageCircle,
      enabled: permissions.whatsapp_enabled,
      color: 'bg-green-500',
      stats: stats.whatsapp_messages_today || 0,
      label: 'הודעות היום'
    },
    {
      name: 'ניהול לקוחות',
      description: 'CRM מלא וניהול קשרי לקוחות',
      href: '/crm',
      icon: Users,
      enabled: permissions.crm_enabled,
      color: 'bg-purple-500',
      stats: stats.total_customers || 0,
      label: 'סה"כ לקוחות'
    }
  ];

  const kpiCards = [
    {
      title: 'הכנסות החודש',
      value: stats.monthly_revenue || 0,
      change: '+12%',
      icon: DollarSign,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'לקוחות חדשים',
      value: stats.new_customers_this_month || 0,
      change: '+8%',
      icon: Users,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      title: 'זמן תגובה ממוצע',
      value: `${stats.avg_response_time || 0} דק'`,
      change: '-15%',
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50'
    },
    {
      title: 'שביעות רצון',
      value: `${stats.satisfaction_rate || 0}%`,
      change: '+5%',
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    }
  ];

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          ברוך הבא, {business?.name || 'עסק'}
        </h1>
        <p className="text-gray-600 mt-1">
          סקירה מהירה של הפעילות העסקית שלך
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpiCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 mb-1">
                    {card.title}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">
                    {card.value}
                  </p>
                  <p className={`text-sm ${card.color} mt-1`}>
                    {card.change} מהחודש הקודם
                  </p>
                </div>
                <div className={`${card.bgColor} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${card.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {quickActions.filter(action => action.enabled).map((action) => {
          const Icon = action.icon;
          return (
            <div
              key={action.name}
              className="bg-white rounded-lg shadow hover:shadow-md transition-shadow p-6 cursor-pointer"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`${action.color} p-3 rounded-lg text-white`}>
                  <Icon className="w-6 h-6" />
                </div>
                <div className="text-left">
                  <div className="text-2xl font-bold text-gray-900">
                    {action.stats}
                  </div>
                  <div className="text-sm text-gray-500">
                    {action.label}
                  </div>
                </div>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                {action.name}
              </h3>
              <p className="text-gray-600 text-sm">
                {action.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Feed */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">
              פעילות אחרונה
            </h3>
          </div>
          <div className="p-6">
            {recentActivity.length === 0 ? (
              <div className="text-center py-8">
                <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">אין פעילות אחרונה</p>
              </div>
            ) : (
              <div className="space-y-4">
                {recentActivity.slice(0, 5).map((activity, index) => (
                  <div key={index} className="flex items-start space-x-3 space-x-reverse">
                    <div className="flex-shrink-0">
                      <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                        <Activity className="w-4 h-4 text-blue-600" />
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900">
                        {activity.description}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(activity.timestamp).toLocaleString('he-IL')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">
              סטטיסטיקות מהירות
            </h3>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">שיחות שהתקבלו היום</span>
                <span className="font-semibold">{stats.calls_today || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">הודעות וואטסאפ</span>
                <span className="font-semibold">{stats.whatsapp_messages_today || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">לקוחות פעילים</span>
                <span className="font-semibold">{stats.active_customers || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">משימות פתוחות</span>
                <span className="font-semibold">{stats.open_tasks || 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Disabled Services Notice */}
      {Object.values(permissions).some(enabled => !enabled) && (
        <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="mr-3">
              <h4 className="text-sm font-medium text-yellow-800">
                שירותים לא זמינים
              </h4>
              <p className="text-sm text-yellow-700 mt-1">
                חלק מהשירותים אינם זמינים עבור העסק שלך. פנה למנהל המערכת להפעלתם.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;