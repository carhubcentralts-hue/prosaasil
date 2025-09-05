import React from 'react';
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
  Activity
} from 'lucide-react';
import { Card, StatCard, Badge } from '../../shared/components/ui/Card';
import { QuickManagementActions } from '../../shared/components/ui/ManagementCard';
import { cn } from '../../shared/utils/cn';

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
  const actions = [
    { title: 'לידים', icon: <Users className="h-6 w-6" />, color: 'bg-violet-50 text-violet-600' },
    { title: 'WhatsApp', icon: <MessageCircle className="h-6 w-6" />, color: 'bg-green-50 text-green-600' },
    { title: 'שיחות', icon: <Phone className="h-6 w-6" />, color: 'bg-blue-50 text-blue-600' },
    { title: 'לוח שנה', icon: <Calendar className="h-6 w-6" />, color: 'bg-orange-50 text-orange-600' }
  ];

  return (
    <Card className="p-6 mb-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">פעולות מהירות</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((action, index) => (
          <button
            key={index}
            className="flex flex-col items-center p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors min-h-[88px]"
            onClick={() => alert('בקרוב! תכונה זו תהיה זמינה בגרסה הבאה.')}
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
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-semibold text-slate-900">
            שי דירות ומשרדים 🏢
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
              <button className="btn-secondary text-xs px-3 py-1">היום</button>
              <button className="btn-ghost text-xs px-3 py-1">7 ימים</button>
            </div>
          </div>
        </div>

        {/* Provider Status */}
        <ProviderStatusCard />

        {/* Provider Status */}
        <ProviderStatusCard />

        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
          <StatCard
            title="לידים חדשים היום"
            value={mockBusinessStats.newLeads.today}
            trend={mockBusinessStats.newLeads.trend}
            icon={<Users className="h-6 w-6" />}
          />
          <StatCard
            title="לידים פעילים"
            value={mockBusinessStats.activeLeads.count}
            icon={<Users className="h-6 w-6" />}
          />
          <StatCard
            title="הודעות שלא נקראו"
            value={mockBusinessStats.unread.whatsapp}
            subtitle="WhatsApp"
            icon={<Bell className="h-6 w-6" />}
          />
          <StatCard
            title="שיחות היום"
            value={mockBusinessStats.calls.today}
            trend={mockBusinessStats.calls.trend}
            icon={<Phone className="h-6 w-6" />}
          />
          <StatCard
            title="פגישות היום"
            value={mockBusinessStats.meetings.today}
            icon={<Calendar className="h-6 w-6" />}
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
        <RecentActivityCard />
      </div>
    </div>
  );
}