import React, { useState } from 'react';
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
  Bot,
  Edit3,
  Save,
  RotateCcw,
  History
} from 'lucide-react';
import { Card, StatCard, Badge } from '../../shared/components/ui/Card';
import { QuickManagementActions } from '../../shared/components/ui/ManagementCard';
import { cn } from '../../shared/utils/cn';
import { useBusinessDashboard } from '../../features/business/hooks';
import { useAIPrompt, type PromptHistoryItem } from '../../features/business/useAIPrompt';

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

function RecentActivityCard({ activity, isLoading }: { activity?: any[], isLoading?: boolean }) {
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
        {activity && activity.length > 0 ? activity.slice(0, 6).map((item, index) => {
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
              <button className="text-blue-600 hover:text-blue-800 text-sm font-medium mr-2">
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
      
      {activity && activity.length > 0 && (
        <div className="mt-4 text-center">
          <button className="text-blue-600 hover:text-blue-800 text-sm font-medium">
            ראה עוד פעילות
          </button>
        </div>
      )}
    </div>
  );
}

function AIPromptCard() {
  const { 
    promptData, 
    history, 
    isLoading, 
    historyLoading,
    error,
    isEditing, 
    editablePrompt, 
    setEditablePrompt,
    startEditing, 
    cancelEditing, 
    savePrompt,
    isSaving,
    saveError 
  } = useAIPrompt();
  
  const [showHistory, setShowHistory] = useState(false);

  if (isLoading) {
    return (
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-50 rounded-lg">
              <Bot className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">AI Agent (לאה)</h3>
              <p className="text-sm text-slate-600">הגדרות שיחה חכמה</p>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="text-gray-600 mr-2">טוען הגדרות...</span>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 mb-6 bg-red-50 border-red-200">
        <div className="flex items-center gap-3 text-red-700">
          <XCircle className="h-5 w-5" />
          <div>
            <p className="font-medium">שגיאה בטעינת הגדרות AI</p>
            <p className="text-sm text-red-600">{error.message}</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-50 rounded-lg">
            <Bot className="h-6 w-6 text-purple-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">AI Agent (לאה)</h3>
            <p className="text-sm text-slate-600">
              {promptData ? `גרסה ${promptData.version} • עודכן ${new Date(promptData.lastUpdated).toLocaleDateString('he-IL')}` : 'הגדרות שיחה חכמה'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="היסטוריית גרסאות"
          >
            <History className="h-4 w-4 text-gray-600" />
          </button>
          {!isEditing && (
            <button
              onClick={startEditing}
              className="flex items-center gap-2 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
            >
              <Edit3 className="h-4 w-4" />
              ערוך
            </button>
          )}
        </div>
      </div>

      {/* Error Display */}
      {saveError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2 text-red-700">
            <XCircle className="h-4 w-4" />
            <span className="text-sm">שגיאה בשמירה: {saveError.message}</span>
          </div>
        </div>
      )}

      {/* Main Content */}
      {isEditing ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              הנחיות לסוכן הדיגיטלי
            </label>
            <textarea
              value={editablePrompt}
              onChange={(e) => setEditablePrompt(e.target.value)}
              className="w-full h-40 p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-sm"
              placeholder="הכנס את ההנחיות לסוכן הדיגיטלי (לאה) שיטפל בשיחות נכנסות..."
              dir="rtl"
            />
          </div>
          <div className="flex justify-end gap-3">
            <button
              onClick={cancelEditing}
              disabled={isSaving}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4 inline mr-1" />
              ביטול
            </button>
            <button
              onClick={savePrompt}
              disabled={isSaving || !editablePrompt.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              שמור
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
            {promptData?.prompt || 'לא הוגדר פרומפט עדיין'}
          </p>
        </div>
      )}

      {/* History Section */}
      {showHistory && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h4 className="text-md font-semibold text-gray-900 mb-3">היסטוריית גרסאות</h4>
          {historyLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              <span className="text-gray-600 text-sm mr-2">טוען היסטוריה...</span>
            </div>
          ) : history && history.length > 0 ? (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {history.map((item: PromptHistoryItem, index: number) => (
                <div key={index} className="bg-white p-3 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="neutral">גרסה {item.version}</Badge>
                    <span className="text-xs text-gray-500">
                      {new Date(item.createdAt).toLocaleString('he-IL')} • {item.updatedBy}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 line-clamp-2">
                    {item.prompt.substring(0, 120)}
                    {item.prompt.length > 120 ? '...' : ''}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-4">אין היסטוריה זמינה</p>
          )}
        </div>
      )}
    </Card>
  );
}

export function BusinessHomePage() {
  // Fetch real dashboard data
  const { stats, isLoadingStats, statsError, activity, isLoadingActivity, activityError, refetch } = useBusinessDashboard();

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

        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
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
            title="WhatsApp היום"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : (
              stats?.whatsapp?.today || 0
            )}
            subtitle={stats?.whatsapp?.last7d ? `${stats.whatsapp.last7d} ב-7 ימים` : undefined}
            icon={<MessageCircle className="h-6 w-6" />}
          />
          <StatCard
            title="הודעות שלא נקראו"
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
          <StatCard
            title="ממוצע שיחה"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : stats?.calls?.avgHandleSec ? (
              `${Math.round(stats.calls.avgHandleSec)}s`
            ) : (
              'אין נתונים'
            )}
            subtitle="זמן טיפול ממוצע"
            icon={<Clock className="h-6 w-6" />}
          />
          <StatCard
            title="הכנסות החודש"
            value={isLoadingStats ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">טוען...</span>
              </div>
            ) : stats?.revenue?.thisMonth ? (
              `₪${stats.revenue.thisMonth.toLocaleString('he-IL')}`
            ) : (
              'אין נתונים'
            )}
            subtitle={stats?.revenue?.ytd ? `₪${stats.revenue.ytd.toLocaleString('he-IL')} השנה` : undefined}
            icon={<TrendingUp className="h-6 w-6" />}
          />
        </div>

        {/* AI Agent Prompt Management */}
        <AIPromptCard />

        {/* Management Actions - User management only */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">ניהול משתמשים</h3>
          <QuickManagementActions />
        </div>

        {/* Quick Actions */}
        <QuickActionsCard />

        {/* Recent Activity */}
        <RecentActivityCard activity={activity} isLoading={isLoadingActivity} />
      </div>
    </div>
  );
}