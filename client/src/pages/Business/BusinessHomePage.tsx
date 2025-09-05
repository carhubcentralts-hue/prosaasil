import React from 'react';
import { 
  Users, 
  MessageCircle, 
  Phone, 
  Calendar, 
  Bell,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Activity,
  Plus,
  ExternalLink
} from 'lucide-react';

// Mock data - will be replaced with API calls  
const mockProviderStatus = {
  twilio: { up: true, latency: 45 },
  baileys: { up: true, latency: null },
  db: { up: true, latency: 12 }
};

const mockBusinessStats = {
  newLeads: { today: 8, trend: '+15%' },
  activeLeads: { count: 23 },
  unread: { whatsapp: 3 },
  calls: { today: 12, trend: '+5%' },
  meetings: { today: 2 }
};

const mockTenantActivity = [
  { time: '14:32', type: 'call', preview: 'שיחה חדשה מ-054-123-4567', id: '1' },
  { time: '14:18', type: 'whatsapp', preview: 'הודעה מלאה בן דוד - מעוניין בדירה', id: '2' },
  { time: '13:45', type: 'call', preview: 'ליד חדש נוסף למערכת', id: '3' },
  { time: '13:22', type: 'whatsapp', preview: 'פגישה נקבעה - יום ראשון 16:00', id: '4' }
];

function ProviderStatusCard() {
  const getStatusIcon = (up: boolean) => {
    return up ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    );
  };

  return (
    <div className="bg-gradient-to-l from-blue-600 to-blue-700 rounded-xl p-6 text-white mb-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold mb-2">סטטוס מערכת</h3>
          <div className="flex items-center space-x-reverse space-x-4">
            <div className="flex items-center">
              {getStatusIcon(mockProviderStatus.twilio.up)}
              <span className="text-sm mr-2">Twilio מחובר</span>
            </div>
            <div className="flex items-center">
              {getStatusIcon(mockProviderStatus.baileys.up)}
              <span className="text-sm mr-2">WhatsApp פעיל</span>
            </div>
          </div>
        </div>
        <Activity className="h-12 w-12 text-blue-200" />
      </div>
    </div>
  );
}

function KPICard({ title, value, subtitle, icon, trend }: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-gray-600 text-sm mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mb-2">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-500">{subtitle}</p>
          )}
          {trend && (
            <p className="text-xs text-green-600 flex items-center mt-1">
              <TrendingUp className="h-3 w-3 ml-1" />
              {trend}
            </p>
          )}
        </div>
        <div className="text-gray-400">
          {icon}
        </div>
      </div>
    </div>
  );
}

function QuickActionsCard() {
  const actions = [
    { title: 'לידים', icon: <Users className="h-5 w-5" />, color: 'bg-purple-50 text-purple-600' },
    { title: 'WhatsApp', icon: <MessageCircle className="h-5 w-5" />, color: 'bg-green-50 text-green-600' },
    { title: 'שיחות', icon: <Phone className="h-5 w-5" />, color: 'bg-blue-50 text-blue-600' },
    { title: 'לוח שנה', icon: <Calendar className="h-5 w-5" />, color: 'bg-orange-50 text-orange-600' }
  ];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">פעולות מהירות</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((action, index) => (
          <button
            key={index}
            className="flex flex-col items-center p-4 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
            onClick={() => alert('בקרוב! תכונה זו תהיה זמינה בגרסה הבאה.')}
          >
            <div className={`p-3 rounded-lg ${action.color} mb-2`}>
              {action.icon}
            </div>
            <span className="text-sm font-medium text-gray-900">{action.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function RecentActivityCard() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">פעילות אחרונה</h3>
        <Clock className="h-5 w-5 text-gray-400" />
      </div>
      
      <div className="space-y-3">
        {mockTenantActivity.map((activity) => (
          <div key={activity.id} className="flex items-start p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            <div className={`w-3 h-3 rounded-full mt-2 ml-3 ${
              activity.type === 'call' ? 'bg-blue-500' : 'bg-green-500'
            }`} />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900">{activity.time}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1">{activity.preview}</p>
            </div>
            <button className="text-blue-600 hover:text-blue-800 text-sm font-medium mr-2">
              פתח
            </button>
          </div>
        ))}
      </div>
      
      <div className="mt-4 text-center">
        <button className="text-blue-600 hover:text-blue-800 text-sm font-medium">
          ראה עוד פעילות
        </button>
      </div>
    </div>
  );
}

export function BusinessHomePage() {
  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">
            לוח בקרה עסקי 🏢
          </h1>
          <p className="text-gray-600 mt-1">
            היום: {new Date().toLocaleDateString('he-IL', { 
              weekday: 'long', 
              year: 'numeric', 
              month: 'long', 
              day: 'numeric' 
            })}
          </p>
        </div>

        {/* Provider Status */}
        <ProviderStatusCard />

        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
          <KPICard
            title="לידים חדשים היום"
            value={mockBusinessStats.newLeads.today}
            trend={mockBusinessStats.newLeads.trend}
            icon={<Users className="h-6 w-6" />}
          />
          <KPICard
            title="לידים פעילים"
            value={mockBusinessStats.activeLeads.count}
            icon={<Users className="h-6 w-6" />}
          />
          <KPICard
            title="הודעות שלא נקראו"
            value={mockBusinessStats.unread.whatsapp}
            subtitle="WhatsApp"
            icon={<Bell className="h-6 w-6" />}
          />
          <KPICard
            title="שיחות היום"
            value={mockBusinessStats.calls.today}
            trend={mockBusinessStats.calls.trend}
            icon={<Phone className="h-6 w-6" />}
          />
          <KPICard
            title="פגישות היום"
            value={mockBusinessStats.meetings.today}
            icon={<Calendar className="h-6 w-6" />}
          />
        </div>

        {/* Quick Actions */}
        <QuickActionsCard />

        {/* Recent Activity */}
        <RecentActivityCard />
      </div>
    </div>
  );
}