import React, { useState, useMemo } from 'react';
import { 
  Building2, 
  MessageCircle, 
  Phone, 
  Calendar, 
  Bell,
  TrendingUp,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  CalendarDays,
  Filter,
  Loader2
} from 'lucide-react';
import { Card, StatCard, Badge } from '../../shared/components/ui/Card';
import { QuickManagementActions } from '../../shared/components/ui/ManagementCard';
import { cn } from '../../shared/utils/cn';
import { useAdminOverview, getDateRangeForFilter } from '../../features/admin/hooks';

// Removed mock data - now using real API calls

function ProviderStatusCard({ providerStatus }: { providerStatus?: any }) {
  if (!providerStatus) {
    return (
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          <span className="text-slate-600 mr-2">טוען נתוני מערכת...</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-900">סטטוס מערכת</h3>
        <Activity className="h-6 w-6 text-slate-400" />
      </div>
      
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="flex items-center gap-2">
          <Badge variant={providerStatus.twilio?.up ? "success" : "danger"}>
            {providerStatus.twilio?.up ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            Twilio
          </Badge>
          {providerStatus.twilio?.latency && (
            <span className="text-xs text-slate-500 tabular-nums">{providerStatus.twilio.latency}ms</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={providerStatus.baileys?.up ? "success" : "danger"}>
            {providerStatus.baileys?.up ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            Baileys
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={providerStatus.db?.up ? "success" : "danger"}>
            {providerStatus.db?.up ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            Database
          </Badge>
          {providerStatus.db?.latency && (
            <span className="text-xs text-slate-500 tabular-nums">{providerStatus.db.latency}ms</span>
          )}
        </div>

        <div className="text-xs text-slate-600 space-y-1">
          <div className="tabular-nums">STT: {providerStatus.stt || 0}ms</div>
          <div className="tabular-nums">AI: {providerStatus.ai || 0}ms</div>
          <div className="tabular-nums">TTS: {providerStatus.tts || 0}ms</div>
        </div>
      </div>
    </Card>
  );
}


function RecentActivityCard({ recentActivity }: { recentActivity?: any[] }) {
  if (!recentActivity) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">פעילות אחרונה</h3>
          <Clock className="h-5 w-5 text-slate-400" />
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          <span className="text-slate-600 mr-2">טוען פעילות אחרונה...</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-slate-900">פעילות אחרונה</h3>
        <Clock className="h-5 w-5 text-slate-400" />
      </div>
      
      <div className="space-y-3">
        {recentActivity.length > 0 ? recentActivity.map((activity) => (
          <div key={activity.id} className="flex items-start p-3 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
            <div className={cn(
              'w-3 h-3 rounded-full mt-2 ml-3',
              activity.type === 'call' ? 'bg-blue-500' : 'bg-green-500'
            )} />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-900">{activity.tenant}</span>
                <span className="text-xs text-slate-500 tabular-nums">{activity.time}</span>
              </div>
              <p className="text-sm text-slate-600 mt-1">{activity.preview}</p>
            </div>
            <button className="btn-ghost text-xs px-2 py-1">
              פתח
            </button>
          </div>
        )) : (
          <div className="text-center py-8 text-slate-500">
            <Clock className="h-12 w-12 mx-auto mb-4 text-slate-300" />
            <p>אין פעילות אחרונה לטווח הזמן שנבחר</p>
          </div>
        )}
      </div>
      
      {recentActivity.length > 0 && (
        <div className="mt-4 text-center">
          <button className="btn-ghost text-sm">
            ראה עוד פעילות
          </button>
        </div>
      )}
    </Card>
  );
}

export function AdminHomePage() {
  const [timeFilter, setTimeFilter] = useState<'today' | 'week' | 'month' | 'custom'>('today');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [dateRange, setDateRange] = useState({
    from: new Date(),
    to: new Date()
  });

  // Generate API parameters based on current filter
  const apiParams = useMemo(() => {
    try {
      if (timeFilter === 'custom') {
        return getDateRangeForFilter('custom', dateRange.from, dateRange.to);
      }
      return getDateRangeForFilter(timeFilter);
    } catch (error) {
      console.error('Error generating date range:', error);
      return getDateRangeForFilter('today');
    }
  }, [timeFilter, dateRange.from, dateRange.to]);

  // Fetch overview data from API
  const { data: overviewData, isLoading, error, refetch } = useAdminOverview(apiParams);

  const handleTimeFilterChange = (filter: 'today' | 'week' | 'month' | 'custom') => {
    setTimeFilter(filter);
    if (filter === 'custom') {
      setShowDatePicker(true);
    } else {
      setShowDatePicker(false);
      console.log(`מעדכן נתונים עבור: ${filter}`);
    }
  };

  const handleDateRangeChange = (from: Date, to: Date) => {
    setDateRange({ from, to });
    console.log(`מעדכן נתונים עבור טווח: ${from.toDateString()} - ${to.toDateString()}`);
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-semibold text-slate-900">
            מנהל מערכת 👋
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
            
            {/* Time Filter Buttons */}
            <div className="flex flex-wrap gap-2">
              <button 
                onClick={() => handleTimeFilterChange('today')}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  timeFilter === 'today' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                היום
              </button>
              <button 
                onClick={() => handleTimeFilterChange('week')}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  timeFilter === 'week' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                7 ימים
              </button>
              <button 
                onClick={() => handleTimeFilterChange('month')}
                className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  timeFilter === 'month' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                30 ימים
              </button>
              <button 
                onClick={() => handleTimeFilterChange('custom')}
                className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                  timeFilter === 'custom' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
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
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">עד תאריך</label>
                  <input
                    type="date"
                    value={dateRange.to.toISOString().split('T')[0]}
                    onChange={(e) => handleDateRangeChange(dateRange.from, new Date(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => setShowDatePicker(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  ביטול
                </button>
                <button
                  onClick={() => {
                    setShowDatePicker(false);
                    handleDateRangeChange(dateRange.from, dateRange.to);
                  }}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors"
                >
                  החל
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Provider Status */}
        <ProviderStatusCard providerStatus={overviewData?.provider_status} />

        {/* Error State */}
        {error && (
          <Card className="p-6 mb-6 bg-red-50 border-red-200">
            <div className="flex items-center gap-3 text-red-700">
              <XCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">שגיאה בטעינת נתונים</p>
                <p className="text-sm text-red-600">{error.message}</p>
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

        {/* KPI Row 1 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <StatCard
            title="עסקים (פעילים/סה״כ)"
            value={isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              `${overviewData?.active_businesses || 0}/${overviewData?.total_businesses || 0}`
            )}
            icon={<Building2 className="h-6 w-6" />}
          />
          <StatCard
            title="הודעות WhatsApp"
            value={isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              overviewData?.whatsapp_count || 0
            )}
            subtitle={`טווח: ${timeFilter === 'today' ? 'היום' : timeFilter === 'week' ? '7 ימים' : timeFilter === 'month' ? '30 ימים' : 'מותאם'}`}
            icon={<MessageCircle className="h-6 w-6" />}
          />
        </div>

        {/* Management Actions */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">פעולות ניהול</h3>
          <QuickManagementActions />
        </div>

        {/* KPI Row 2 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <StatCard
            title="שיחות"
            value={isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              overviewData?.calls_count || 0
            )}
            subtitle={`טווח: ${timeFilter === 'today' ? 'היום' : timeFilter === 'week' ? '7 ימים' : timeFilter === 'month' ? '30 ימים' : 'מותאם'}`}
            icon={<Phone className="h-6 w-6" />}
          />
          <StatCard
            title="ממוצע משך שיחה"
            value={isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : overviewData?.avg_call_duration ? (
              `${overviewData.avg_call_duration} דקות`
            ) : (
              'אין נתונים'
            )}
            subtitle={overviewData?.calls_count ? `מתוך ${overviewData.calls_count} שיחות` : ''}
            icon={<Clock className="h-6 w-6" />}
          />
        </div>

        {/* Recent Activity */}
        <RecentActivityCard recentActivity={overviewData?.recent_activity} />
      </div>
    </div>
  );
}