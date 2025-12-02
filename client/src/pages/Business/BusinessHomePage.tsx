import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Users, 
  MessageCircle, 
  Phone, 
  Calendar, 
  Bell,
  TrendingUp,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  Loader2
} from 'lucide-react';
import { Card, StatCard, Badge } from '../../shared/components/ui/Card';
import { QuickManagementActions } from '../../shared/components/ui/ManagementCard';
import { cn } from '../../shared/utils/cn';
import { useBusinessDashboard } from '../../features/business/hooks';

// Removed mock data - now using real API calls

function ProviderStatusCard() {
  return (
    <div className="gradient-brand rounded-xl p-6 text-white mb-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold mb-2">סטטוס מערכת</h3>
          <div className="flex items-center space-x-reverse space-x-4">
            <div className="flex items-center">
              <CheckCircle className="h-4 w-4 text-green-300" />
              <span className="text-sm mr-2">Twilio מחובר</span>
            </div>
            <div className="flex items-center">
              <CheckCircle className="h-4 w-4 text-green-300" />
              <span className="text-sm mr-2">WhatsApp פעיל</span>
            </div>
          </div>
        </div>
        <Activity className="h-12 w-12 text-white opacity-30" />
      </div>
    </div>
  );
}


function QuickActionsCard() {
  const navigate = useNavigate();
  
  const actions = [
    { title: 'לידים', icon: <Users className="h-6 w-6" />, color: 'bg-violet-50 text-violet-600', route: '/app/leads' },
    { title: 'WhatsApp', icon: <MessageCircle className="h-6 w-6" />, color: 'bg-green-50 text-green-600', route: '/app/whatsapp' },
    { title: 'שיחות', icon: <Phone className="h-6 w-6" />, color: 'bg-blue-50 text-blue-600', route: '/app/calls' },
    { title: 'לוח שנה', icon: <Calendar className="h-6 w-6" />, color: 'bg-orange-50 text-orange-600', route: '/app/calendar' }
  ];

  return (
    <Card className="p-6 mb-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">פעולות מהירות</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((action, index) => (
          <button
            key={index}
            className="flex flex-col items-center p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors min-h-[88px]"
            onClick={() => navigate(action.route)}
            data-testid={`quick-action-${action.title}`}
          >
            <div className={cn(
              'p-3 rounded-xl mb-3 transition-transform hover:scale-105',
              action.color
            )}>
              {action.icon}
            </div>
            <span className="text-sm font-medium text-slate-900">{action.title}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function RecentActivityCard({ activity, isLoading, timeFilter }: { activity?: any[], isLoading?: boolean, timeFilter?: 'today' | '7days' }) {
  const navigate = useNavigate();

  const handleOpenActivity = (item: any) => {
    if (item.leadId) {
      navigate(`/app/leads/${item.leadId}`);
    } else if (item.type === 'call') {
      navigate('/app/calls');
    } else if (item.type === 'whatsapp') {
      navigate('/app/whatsapp');
    } else {
      navigate('/app/leads');
    }
  };
  
  const filteredActivity = activity?.filter(item => {
    if (!timeFilter || timeFilter === '7days') return true;
    const itemDate = new Date(item.ts);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return itemDate >= today;
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">פעילות אחרונה</h3>
          <Clock className="h-5 w-5 text-gray-400" />
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="text-gray-600 mr-2">טוען פעילות...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">פעילות אחרונה</h3>
        <Clock className="h-5 w-5 text-gray-400" />
      </div>
      
      <div className="space-y-3">
        {filteredActivity && filteredActivity.length > 0 ? filteredActivity.slice(0, 6).map((item, index) => {
          const time = new Date(item.ts).toLocaleTimeString('he-IL', { 
            hour: '2-digit', 
            minute: '2-digit' 
          });
          
          return (
            <div key={index} className="flex items-start p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className={`w-3 h-3 rounded-full mt-2 ml-3 ${
                item.type === 'call' ? 'bg-blue-500' : 'bg-green-500'
              }`} />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">{time}</span>
                  <Badge variant={item.type === 'call' ? 'neutral' : 'success'}>
                    {item.provider}
                  </Badge>
                </div>
                <p className="text-sm text-gray-600 mt-1">{item.preview}</p>
              </div>
              <button 
                className="text-blue-600 hover:text-blue-800 text-sm font-medium mr-2"
                onClick={() => handleOpenActivity(item)}
                data-testid={`activity-open-${index}`}
              >
                פתח
              </button>
            </div>
          );
        }) : (
          <div className="text-center py-8 text-gray-500">
            <Clock className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>אין פעילות אחרונה</p>
          </div>
        )}
      </div>
      
      {filteredActivity && filteredActivity.length > 0 && (
        <div className="mt-4 text-center">
          <button 
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            onClick={() => navigate('/app/leads')}
            data-testid="activity-see-more"
          >
            ראה עוד פעילות
          </button>
        </div>
      )}
    </div>
  );
}

export function BusinessHomePage() {
  const [timeFilter, setTimeFilter] = useState<'today' | '7days'>('today');
  
  // Fetch real dashboard data
  const { stats, isLoadingStats, statsError, activity, isLoadingActivity, activityError, refetch } = useBusinessDashboard();

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900">
            <span className="text-black">Pro</span><span className="text-blue-600">SaaS</span> 🚀
          </h1>
          <div className="flex items-center gap-4 mt-2">
            <p className="text-slate-600">
              היום: {new Date().toLocaleDateString('he-IL', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}
            </p>
            <div className="flex gap-2">
              <button 
                className={`text-xs px-3 py-1 rounded-md transition-colors ${timeFilter === 'today' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                onClick={() => setTimeFilter('today')}
                data-testid="filter-today"
              >
                היום
              </button>
              <button 
                className={`text-xs px-3 py-1 rounded-md transition-colors ${timeFilter === '7days' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                onClick={() => setTimeFilter('7days')}
                data-testid="filter-7days"
              >
                7 ימים
              </button>
            </div>
          </div>
        </div>

        {/* Provider Status */}
        <ProviderStatusCard />

        {/* Error State */}
        {(statsError || activityError) && (
          <Card className="p-6 mb-6 bg-red-50 border-red-200">
            <div className="flex items-center gap-3 text-red-700">
              <XCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">שגיאה בטעינת נתונים</p>
                <p className="text-sm text-red-600">{statsError?.message || activityError?.message}</p>
                <button 
                  onClick={() => refetch()}
                  className="text-sm underline hover:no-underline mt-1"
                >
                  נסה שוב
                </button>
              </div>
            </div>
          </Card>
        )}

        {/* KPI Cards - Removed monthly income and average call per user request */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard
            title="שיחות היום"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              stats?.calls?.today || 0
            )}
            subtitle={stats?.calls?.last7d ? `${stats.calls.last7d} ב-7 ימים` : undefined}
            icon={<Phone className="h-6 w-6" />}
          />
          <StatCard
            title="צ'אטים היום"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              stats?.whatsapp?.today || 0
            )}
            subtitle={stats?.whatsapp?.last7d ? `${stats.whatsapp.last7d} צ'אטים ב-7 ימים` : undefined}
            icon={<MessageCircle className="h-6 w-6" />}
          />
          <StatCard
            title="צ'אטים שלא נקראו"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              stats?.whatsapp?.unread || 0
            )}
            subtitle="WhatsApp"
            icon={<Bell className="h-6 w-6" />}
          />
        </div>

        {/* Management Actions - User management only */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">ניהול משתמשים</h3>
          <QuickManagementActions />
        </div>

        {/* Quick Actions */}
        <QuickActionsCard />

        {/* Recent Activity */}
        <RecentActivityCard activity={activity} isLoading={isLoadingActivity} timeFilter={timeFilter} />
      </div>
    </div>
  );
}