import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  Phone, 
  PhoneIncoming, 
  PhoneOutgoing, 
  MessageSquare, 
  Calendar, 
  CheckCircle, 
  Users, 
  Clock,
  TrendingUp,
  FileText,
  RefreshCw,
  Mail,
  Filter,
  X
} from 'lucide-react';
import { http } from '../../services/http';
import { formatDate, formatDateOnly } from '../../shared/utils/format';
import { MultiStatusSelect } from '../../shared/components/ui/MultiStatusSelect';
import { LeadStatusConfig } from '../../shared/types/status';

// Local UI Components
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
);

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive" | "info";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800",
    info: "bg-blue-100 text-blue-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

interface BusinessStats {
  // Call stats
  total_calls: number;
  inbound_calls: number;
  outbound_calls: number;
  answered_calls: number;
  missed_calls: number;
  total_call_duration: number; // in seconds
  
  // Message stats
  total_messages: number;
  whatsapp_messages: number;
  emails_sent: number;
  
  // Lead stats
  total_leads: number;
  new_leads: number;
  qualified_leads: number;
  converted_leads: number;
  
  // Task/Meeting stats
  total_tasks: number;
  pending_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  total_meetings: number;
  upcoming_meetings: number;
  
  // Summary stats
  total_summaries: number;
}

// API Response interfaces for type safety
interface CallCountsResponse {
  active_total: number;
  active_outbound: number;
}

interface LeadsResponse {
  total: number;
  items?: Array<{ id: number }>;
}

interface RemindersResponse {
  reminders: Array<{
    id: number;
    completed_at: string | null;
    due_at: string;
  }>;
}

interface AppointmentsResponse {
  appointments: Array<{
    id: number;
    start_time: string;
  }>;
}

interface EmailsResponse {
  total?: number;
  emails?: Array<{ id: number }>;
}

interface StatCardProps {
  icon: React.ReactNode;
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: { value: number; isPositive: boolean };
  color?: string;
}

function StatCard({ icon, title, value, subtitle, trend, color = "blue" }: StatCardProps) {
  const colorClasses: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    purple: "bg-purple-50 text-purple-600",
    orange: "bg-orange-50 text-orange-600",
    red: "bg-red-50 text-red-600",
    indigo: "bg-indigo-50 text-indigo-600",
    pink: "bg-pink-50 text-pink-600"
  };

  return (
    <Card className="p-4 md:p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className={`p-3 rounded-xl ${colorClasses[color]}`}>
          {icon}
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-sm ${trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
            <TrendingUp className={`w-4 h-4 ${!trend.isPositive ? 'rotate-180' : ''}`} />
            <span>{Math.abs(trend.value)}%</span>
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl md:text-3xl font-bold text-gray-900 mt-1">{value}</p>
        {subtitle && (
          <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
        )}
      </div>
    </Card>
  );
}

export function StatisticsPage() {
  const [stats, setStats] = useState<BusinessStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  
  // Filter state
  const [statuses, setStatuses] = useState<LeadStatusConfig[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    loadStatuses();
  }, []);

  useEffect(() => {
    loadStats();
  }, [selectedStatuses, dateFrom, dateTo]);

  const formatDateDisplay = (dateStr: string): string => {
    // Format YYYY-MM-DD to DD/MM/YYYY for Hebrew display
    return dateStr.split('-').reverse().join('/');
  };

  const loadStatuses = async () => {
    try {
      const response = await http.get<{ items: LeadStatusConfig[] }>('/api/lead-statuses');
      setStatuses(response.items || []);
    } catch (err) {
      console.error('Error loading statuses:', err);
    }
  };

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Build query parameters for filtering
      const params = new URLSearchParams();
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => {
          params.append('statuses[]', status);
        });
      }
      if (dateFrom) {
        // Convert local date (YYYY-MM-DD) to UTC timestamp at start of local day
        // Backend compares with created_at (UTC), so we need UTC representation of local date
        const fromDate = new Date(dateFrom + 'T00:00:00');
        params.append('from', fromDate.toISOString());
      }
      if (dateTo) {
        // Convert local date (YYYY-MM-DD) to UTC timestamp at end of local day
        const toDate = new Date(dateTo + 'T23:59:59');
        params.append('to', toDate.toISOString());
      }
      
      // Try to fetch stats from various endpoints
      const [
        callsData,
        leadsData,
        tasksData,
        meetingsData,
        emailsData
      ] = await Promise.allSettled([
        http.get<CallCountsResponse>('/api/outbound_calls/counts'),
        http.get<LeadsResponse>(`/api/leads?pageSize=1&${params.toString()}`),
        http.get<RemindersResponse>('/api/reminders'),
        http.get<AppointmentsResponse>('/api/calendar/appointments'),
        http.get<EmailsResponse>('/api/email/messages?limit=1')
      ]);

      // Extract call stats with proper typing
      const callCounts: CallCountsResponse = callsData.status === 'fulfilled' 
        ? callsData.value 
        : { active_total: 0, active_outbound: 0 };
      
      // Extract lead stats with proper typing
      const leadResponse: LeadsResponse = leadsData.status === 'fulfilled' 
        ? leadsData.value 
        : { total: 0 };
      const totalLeads = leadResponse.total || 0;
      
      // Extract task stats with proper typing
      const taskResponse: RemindersResponse = tasksData.status === 'fulfilled' 
        ? tasksData.value 
        : { reminders: [] };
      const reminders = taskResponse.reminders || [];
      const pendingTasks = reminders.filter(r => !r.completed_at && new Date(r.due_at) > new Date()).length;
      const overdueTasks = reminders.filter(r => !r.completed_at && new Date(r.due_at) <= new Date()).length;
      const completedTasks = reminders.filter(r => !!r.completed_at).length;
      
      // Extract meeting stats with proper typing
      const meetingResponse: AppointmentsResponse = meetingsData.status === 'fulfilled' 
        ? meetingsData.value 
        : { appointments: [] };
      const appointments = meetingResponse.appointments || [];
      const upcomingMeetings = appointments.filter(m => new Date(m.start_time) > new Date()).length;
      
      // Extract email stats with proper typing
      const emailResponse: EmailsResponse = emailsData.status === 'fulfilled' 
        ? emailsData.value 
        : { total: 0 };
      const emailsSent = emailResponse.total || emailResponse.emails?.length || 0;

      // Build stats object
      setStats({
        total_calls: callCounts.active_total || 0,
        inbound_calls: (callCounts.active_total || 0) - (callCounts.active_outbound || 0),
        outbound_calls: callCounts.active_outbound || 0,
        answered_calls: 0,
        missed_calls: 0,
        total_call_duration: 0,
        total_messages: 0,
        whatsapp_messages: 0,
        emails_sent: emailsSent,
        total_leads: totalLeads,
        new_leads: 0,
        qualified_leads: 0,
        converted_leads: 0,
        total_tasks: reminders.length,
        pending_tasks: pendingTasks,
        completed_tasks: completedTasks,
        overdue_tasks: overdueTasks,
        total_meetings: appointments.length,
        upcoming_meetings: upcomingMeetings,
        total_summaries: 0
      });
      
      setLastRefresh(new Date());
    } catch (err: any) {
      console.error('Error loading statistics:', err);
      setError('שגיאה בטעינת הסטטיסטיקות');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours} שעות ${minutes} דקות`;
    }
    return `${minutes} דקות`;
  };

  const clearFilters = () => {
    setSelectedStatuses([]);
    setDateFrom('');
    setDateTo('');
  };

  const hasActiveFilters = selectedStatuses.length > 0 || dateFrom || dateTo;

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען סטטיסטיקות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl text-white">
            <BarChart3 className="w-6 h-6 md:w-8 md:h-8" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900">סטטיסטיקות העסק</h1>
            <p className="text-sm text-gray-500 mt-1">מבט על כל הנתונים החשובים במקום אחד</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            עודכן: {formatDate(lastRefresh.toISOString())}
          </span>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors ${
              hasActiveFilters 
                ? 'bg-blue-50 border-blue-300 text-blue-700' 
                : 'bg-white border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Filter className="w-4 h-4" />
            <span>סינון</span>
            {hasActiveFilters && (
              <span className="bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {(selectedStatuses.length > 0 ? 1 : 0) + (dateFrom || dateTo ? 1 : 0)}
              </span>
            )}
          </button>
          <button
            onClick={loadStats}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>רענן</span>
          </button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <Card className="p-4 bg-gray-50">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <Filter className="w-4 h-4" />
                סינון סטטיסטיקות
              </h3>
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
                >
                  <X className="w-3 h-3" />
                  נקה סינונים
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Status Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">סטטוס</label>
                <MultiStatusSelect
                  statuses={statuses}
                  selectedStatuses={selectedStatuses}
                  onChange={setSelectedStatuses}
                  placeholder="כל הסטטוסים"
                  className="w-full"
                />
              </div>

              {/* Date Range Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">טווח תאריכים</label>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="מתאריך"
                    />
                  </div>
                  <div className="flex-1">
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => setDateTo(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="עד תאריך"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Active Filters Summary */}
            {hasActiveFilters && (
              <div className="pt-3 border-t border-gray-200">
                <div className="flex flex-wrap gap-2">
                  {selectedStatuses.length > 0 && (
                    <Badge variant="info">
                      {selectedStatuses.length === 1
                        ? statuses.find(s => s.name === selectedStatuses[0])?.label
                        : `${selectedStatuses.length} סטטוסים`}
                    </Badge>
                  )}
                  {dateFrom && (
                    <Badge variant="info">
                      מ-{formatDateDisplay(dateFrom)}
                    </Badge>
                  )}
                  {dateTo && (
                    <Badge variant="info">
                      עד-{formatDateDisplay(dateTo)}
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Error State */}
      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-red-800">{error}</p>
        </Card>
      )}

      {stats && (
        <>
          {/* Calls Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Phone className="w-5 h-5 text-blue-600" />
              שיחות
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={<Phone className="w-5 h-5" />}
                title="סה״כ שיחות"
                value={stats.total_calls}
                color="blue"
              />
              <StatCard
                icon={<PhoneIncoming className="w-5 h-5" />}
                title="שיחות נכנסות"
                value={stats.inbound_calls}
                color="green"
              />
              <StatCard
                icon={<PhoneOutgoing className="w-5 h-5" />}
                title="שיחות יוצאות"
                value={stats.outbound_calls}
                color="purple"
              />
              <StatCard
                icon={<Clock className="w-5 h-5" />}
                title="זמן שיחות כולל"
                value={formatDuration(stats.total_call_duration)}
                color="orange"
              />
            </div>
          </section>

          {/* Leads Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600" />
              לידים
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={<Users className="w-5 h-5" />}
                title="סה״כ לידים"
                value={stats.total_leads}
                color="indigo"
              />
              <StatCard
                icon={<Users className="w-5 h-5" />}
                title="לידים חדשים"
                value={stats.new_leads}
                color="blue"
              />
              <StatCard
                icon={<CheckCircle className="w-5 h-5" />}
                title="לידים מוסמכים"
                value={stats.qualified_leads}
                color="green"
              />
              <StatCard
                icon={<TrendingUp className="w-5 h-5" />}
                title="לידים שהומרו"
                value={stats.converted_leads}
                color="purple"
              />
            </div>
          </section>

          {/* Tasks & Meetings Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-purple-600" />
              משימות ופגישות
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={<CheckCircle className="w-5 h-5" />}
                title="סה״כ משימות"
                value={stats.total_tasks}
                subtitle={`${stats.completed_tasks} הושלמו`}
                color="purple"
              />
              <StatCard
                icon={<Clock className="w-5 h-5" />}
                title="משימות ממתינות"
                value={stats.pending_tasks}
                color="blue"
              />
              <StatCard
                icon={<Clock className="w-5 h-5" />}
                title="משימות באיחור"
                value={stats.overdue_tasks}
                color="red"
              />
              <StatCard
                icon={<Calendar className="w-5 h-5" />}
                title="פגישות קרובות"
                value={stats.upcoming_meetings}
                subtitle={`מתוך ${stats.total_meetings} סה״כ`}
                color="green"
              />
            </div>
          </section>

          {/* Messages Section */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-green-600" />
              הודעות ותקשורת
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                icon={<MessageSquare className="w-5 h-5" />}
                title="סה״כ הודעות"
                value={stats.total_messages}
                color="green"
              />
              <StatCard
                icon={<MessageSquare className="w-5 h-5" />}
                title="הודעות WhatsApp"
                value={stats.whatsapp_messages}
                color="green"
              />
              <StatCard
                icon={<Mail className="w-5 h-5" />}
                title="מיילים נשלחו"
                value={stats.emails_sent}
                color="blue"
              />
              <StatCard
                icon={<FileText className="w-5 h-5" />}
                title="סיכומים"
                value={stats.total_summaries}
                color="purple"
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default StatisticsPage;
