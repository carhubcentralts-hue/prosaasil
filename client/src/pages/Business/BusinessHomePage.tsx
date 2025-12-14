import React, { useState, useMemo } from 'react';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { useNavigate } from 'react-router-dom';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
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
  Loader2,
  CalendarDays,
  Filter
} from 'lucide-react';
import { Card, StatCard, Badge } from '../../shared/components/ui/Card';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { QuickManagementActions } from '../../shared/components/ui/ManagementCard';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { cn } from '../../shared/utils/cn';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { useBusinessDashboard, type TimeFilter, type DateRange } from '../../features/business/hooks';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';

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

// BUILD 183: RecentActivityCard removed per user request - not needed in overview

export function BusinessHomePage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('today');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>({
    from: new Date(),
    to: new Date()
  });
  
  // Memoize date range for API calls
  const apiDateRange = useMemo(() => {
    if (timeFilter === 'custom') {
      return dateRange;
    }
    return undefined;
  }, [timeFilter, dateRange]);
  
  // Fetch real dashboard data with time filter
  const { stats, isLoadingStats, statsError, activity, isLoadingActivity, activityError, refetch } = useBusinessDashboard(timeFilter, apiDateRange);

  const handleTimeFilterChange = (filter: TimeFilter) => {
    setTimeFilter(filter);
    if (filter === 'custom') {
      setShowDatePicker(true);
    } else {
      setShowDatePicker(false);
    }
  };

  const handleDateRangeChange = (from: Date, to: Date) => {
    setDateRange({ from, to });
  };

  const getFilterLabel = () => {
    switch (timeFilter) {
      case 'today': return 'היום';
      case '7days': return '7 ימים';
      case '30days': return '30 ימים';
      case 'custom': return 'טווח מותאם';
      default: return 'היום';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900">
            <span className="text-black">Pro</span><span className="text-blue-600">SaaS</span> 🚀
          </h1>
          <div className="flex flex-col md:flex-row md:items-center gap-4 mt-2">
            <p className="text-slate-600">
              היום: {new Date().toLocaleDateString('he-IL', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}
            </p>
            <div className="flex gap-2 flex-wrap">
              <button 
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${timeFilter === 'today' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
                onClick={() => handleTimeFilterChange('today')}
                data-testid="filter-today"
              >
                היום
              </button>
              <button 
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${timeFilter === '7days' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
                onClick={() => handleTimeFilterChange('7days')}
                data-testid="filter-7days"
              >
                7 ימים
              </button>
              <button 
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${timeFilter === '30days' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
                onClick={() => handleTimeFilterChange('30days')}
                data-testid="filter-30days"
              >
                30 ימים
              </button>
              <button 
                className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-colors ${timeFilter === 'custom' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'}`}
                onClick={() => handleTimeFilterChange('custom')}
                data-testid="filter-custom"
              >
                <CalendarDays className="h-3 w-3" />
                טווח מותאם
              </button>
            </div>
          </div>

          {/* Custom Date Range Picker */}
          {showDatePicker && (
            <div className="mt-4 p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
              <h4 className="text-sm font-medium text-slate-900 mb-3 flex items-center gap-2">
                <Filter className="h-4 w-4" />
                בחר טווח תאריכים
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-600 mb-1">מתאריך</label>
                  <input
                    type="date"
                    value={dateRange.from.toISOString().split('T')[0]}
                    onChange={(e) => handleDateRangeChange(new Date(e.target.value), dateRange.to)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    data-testid="input-date-from"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">עד תאריך</label>
                  <input
                    type="date"
                    value={dateRange.to.toISOString().split('T')[0]}
                    onChange={(e) => handleDateRangeChange(dateRange.from, new Date(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    data-testid="input-date-to"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => {
                    setShowDatePicker(false);
                    setTimeFilter('today');
                  }}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  data-testid="button-cancel-date"
                >
                  ביטול
                </button>
                <button
                  onClick={() => {
                    setShowDatePicker(false);
                    refetch();
                  }}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors"
                  data-testid="button-apply-date"
                >
                  החל
                </button>
              </div>
            </div>
          )}
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
            title={`שיחות ${getFilterLabel()}`}
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
            title={`צ'אטים ${getFilterLabel()}`}
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

        {/* BUILD 183: Removed Recent Activity section per user request */}
      </div>
    </div>
  );
}