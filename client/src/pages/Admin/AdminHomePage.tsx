import React from 'react';
import { 
  Building2, 
  MessageCircle, 
  Phone, 
  Calendar, 
  Bell,
  TrendingUp,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Activity
} from 'lucide-react';

// Mock data - will be replaced with API calls
const mockProviderStatus = {
  twilio: { up: true, latency: 45 },
  baileys: { up: true, latency: null },
  db: { up: true, latency: 12 },
  stt: 120,
  ai: 850,
  tts: 200
};

const mockAdminStats = {
  businesses: { total: 12, active: 8 },
  whatsapp: { today: 24 },
  calls: { today: 18 },
  unread: { total: 7 },
  meetings: { today: 5 }
};

const mockRecentActivity = [
  { time: '14:32', type: 'call', tenant: 'שי דירות', preview: 'שיחה חדשה מ-054-123-4567', id: '1' },
  { time: '14:18', type: 'whatsapp', tenant: 'נדלן טופ', preview: 'הודעה מלאה בן דוד - מעוניין בדירה', id: '2' },
  { time: '13:45', type: 'call', tenant: 'משרדי פרימיום', preview: 'ליד חדש נוסף למערכת', id: '3' },
  { time: '13:22', type: 'whatsapp', tenant: 'שי דירות', preview: 'פגישה נקבעה - יום ראשון 16:00', id: '4' },
  { time: '12:58', type: 'call', tenant: 'נדלן טופ', preview: 'שיחה הושלמה - 3 דקות', id: '5' }
];

function ProviderStatusCard() {
  const getStatusIcon = (up: boolean) => {
    return up ? (
      <CheckCircle className="h-5 w-5 text-green-500" />
    ) : (
      <XCircle className="h-5 w-5 text-red-500" />
    );
  };

  const getStatusColor = (up: boolean) => {
    return up ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">סטטוס מערכת</h3>
        <Activity className="h-6 w-6 text-gray-400" />
      </div>
      
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div className={`p-3 rounded-lg border ${getStatusColor(mockProviderStatus.twilio.up)}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center">
                {getStatusIcon(mockProviderStatus.twilio.up)}
                <span className="text-sm font-medium text-gray-900 mr-2">Twilio</span>
              </div>
              {mockProviderStatus.twilio.latency && (
                <span className="text-xs text-gray-500">{mockProviderStatus.twilio.latency}ms</span>
              )}
            </div>
          </div>
        </div>

        <div className={`p-3 rounded-lg border ${getStatusColor(mockProviderStatus.baileys.up)}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center">
                {getStatusIcon(mockProviderStatus.baileys.up)}
                <span className="text-sm font-medium text-gray-900 mr-2">Baileys</span>
              </div>
            </div>
          </div>
        </div>

        <div className={`p-3 rounded-lg border ${getStatusColor(mockProviderStatus.db.up)}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center">
                {getStatusIcon(mockProviderStatus.db.up)}
                <span className="text-sm font-medium text-gray-900 mr-2">Database</span>
              </div>
              {mockProviderStatus.db.latency && (
                <span className="text-xs text-gray-500">{mockProviderStatus.db.latency}ms</span>
              )}
            </div>
          </div>
        </div>

        <div className="p-3 rounded-lg border bg-blue-50 border-blue-200">
          <div className="text-xs text-blue-800">
            <div>STT: {mockProviderStatus.stt}ms</div>
            <div>AI: {mockProviderStatus.ai}ms</div>
            <div>TTS: {mockProviderStatus.tts}ms</div>
          </div>
        </div>
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
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mb-2">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500">{subtitle}</p>
          )}
          {trend && (
            <p className="text-sm text-green-600 flex items-center mt-1">
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

function RecentActivityCard() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">פעילות אחרונה</h3>
        <Clock className="h-5 w-5 text-gray-400" />
      </div>
      
      <div className="space-y-3">
        {mockRecentActivity.map((activity) => (
          <div key={activity.id} className="flex items-start p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            <div className={`w-3 h-3 rounded-full mt-2 ml-3 ${
              activity.type === 'call' ? 'bg-blue-500' : 'bg-green-500'
            }`} />
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900">{activity.tenant}</span>
                <span className="text-xs text-gray-500">{activity.time}</span>
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

export function AdminHomePage() {
  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">
            לוח בקרה מנהל 👋
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
            title="עסקים פעילים"
            value={`${mockAdminStats.businesses.active}/${mockAdminStats.businesses.total}`}
            icon={<Building2 className="h-6 w-6" />}
          />
          <KPICard
            title="WhatsApp היום"
            value={mockAdminStats.whatsapp.today}
            trend="+12%"
            icon={<MessageCircle className="h-6 w-6" />}
          />
          <KPICard
            title="שיחות היום"
            value={mockAdminStats.calls.today}
            trend="+8%"
            icon={<Phone className="h-6 w-6" />}
          />
          <KPICard
            title="הודעות שלא נקראו"
            value={mockAdminStats.unread.total}
            subtitle="כל המערכת"
            icon={<Bell className="h-6 w-6" />}
          />
          <KPICard
            title="פגישות היום"
            value={mockAdminStats.meetings.today}
            icon={<Calendar className="h-6 w-6" />}
          />
        </div>

        {/* Recent Activity */}
        <RecentActivityCard />
      </div>
    </div>
  );
}