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
  Mail
} from 'lucide-react';
import { http } from '../../services/http';
import { formatDate, formatDateOnly } from '../../shared/utils/format';

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

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Try to fetch stats from various endpoints
      const [
        callsData,
        leadsData,
        tasksData,
        meetingsData,
        emailsData
      ] = await Promise.allSettled([
        http.get('/api/outbound_calls/counts'),
        http.get('/api/leads?pageSize=1'),
        http.get('/api/reminders'),
        http.get('/api/calendar/appointments'),
        http.get('/api/email/messages?limit=1')
      ]);

      // Extract call stats
      const callCounts = callsData.status === 'fulfilled' ? callsData.value : { active_total: 0, active_outbound: 0 };
      
      // Extract lead stats  
      const leadResponse = leadsData.status === 'fulfilled' ? leadsData.value : { total: 0 };
      const totalLeads = (leadResponse as any)?.total || 0;
      
      // Extract task stats
      const taskResponse = tasksData.status === 'fulfilled' ? tasksData.value : { reminders: [] };
      const reminders = (taskResponse as any)?.reminders || [];
      const pendingTasks = reminders.filter((r: any) => !r.completed_at && new Date(r.due_at) > new Date()).length;
      const overdueTasks = reminders.filter((r: any) => !r.completed_at && new Date(r.due_at) <= new Date()).length;
      const completedTasks = reminders.filter((r: any) => !!r.completed_at).length;
      
      // Extract meeting stats
      const meetingResponse = meetingsData.status === 'fulfilled' ? meetingsData.value : { appointments: [] };
      const appointments = (meetingResponse as any)?.appointments || [];
      const upcomingMeetings = appointments.filter((m: any) => new Date(m.start_time) > new Date()).length;
      
      // Extract email stats
      const emailResponse = emailsData.status === 'fulfilled' ? emailsData.value : { total: 0 };
      const emailsSent = (emailResponse as any)?.total || (emailResponse as any)?.emails?.length || 0;

      // Build stats object
      setStats({
        total_calls: (callCounts as any)?.active_total || 0,
        inbound_calls: (callCounts as any)?.active_total - (callCounts as any)?.active_outbound || 0,
        outbound_calls: (callCounts as any)?.active_outbound || 0,
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
            onClick={loadStats}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>רענן</span>
          </button>
        </div>
      </div>

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
