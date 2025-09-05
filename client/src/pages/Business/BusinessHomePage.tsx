import React from 'react';
import { Users, MessageCircle, Phone, Calendar, Plus, Eye } from 'lucide-react';
import { statusApi } from '../../features/status/api';
import { useApi } from '../../shared/hooks/useApi';
import { StatCard } from '../../shared/components/StatCard';
import { StatCardSkeleton } from '../../shared/components/Skeleton';
import { ProviderStatus } from '../../shared/components/ProviderStatus';
import { ActivityFeed } from '../../shared/components/ActivityFeed';
import { Button } from '../../shared/components/Button';
import { Card, CardContent, CardHeader } from '../../shared/components/Card';

export function BusinessHomePage() {
  const { 
    data: status, 
    isLoading: statusLoading 
  } = useApi(() => statusApi.getStatus());
  
  const { 
    data: stats, 
    isLoading: statsLoading 
  } = useApi(() => statusApi.getStats());
  
  const { 
    data: activity, 
    isLoading: activityLoading 
  } = useApi(() => statusApi.getActivity());

  const handleComingSoon = () => {
    alert('בקרוב! תכונה זו תהיה זמינה בגרסה הבאה.');
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" dir="rtl">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          לוח בקרה עסקי
        </h1>
        <p className="text-gray-600 mt-1">
          סקירה כללית של הפעילות בעסק שלך
        </p>
      </div>

      {/* Provider Status */}
      <div className="mb-8">
        <ProviderStatus status={status} isLoading={statusLoading} />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : stats ? (
          <>
            <StatCard
              title="לידים חדשים היום"
              value="5" // This would be calculated from leads
              subtitle="מתוך השיחות והודעות"
              icon={<Users className="h-6 w-6" />}
              data-testid="stat-new-leads"
            />
            <StatCard
              title="לידים פעילים"
              value="23" // This would come from CRM
              subtitle="דורשים מעקב"
              icon={<Users className="h-6 w-6" />}
              data-testid="stat-active-leads"
            />
            <StatCard
              title="הודעות לא נקראו"
              value={stats.whatsapp.unread}
              subtitle={`${stats.whatsapp.today} הודעות היום`}
              icon={<MessageCircle className="h-6 w-6" />}
              data-testid="stat-unread-messages"
            />
            <StatCard
              title="שיחות היום"
              value={stats.calls.today}
              subtitle={`${stats.calls.last7d} השבוע`}
              icon={<Phone className="h-6 w-6" />}
              data-testid="stat-calls-today"
            />
          </>
        ) : (
          <div className="col-span-4 text-center py-8">
            <p className="text-gray-500">שגיאה בטעינת נתונים</p>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <Card>
          <CardHeader>
            <h3 className="text-lg font-medium text-gray-900">פעולות מהירות</h3>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Button
                variant="secondary"
                className="h-20 flex-col"
                onClick={handleComingSoon}
                data-testid="button-open-leads"
              >
                <Eye className="h-6 w-6 mb-2" />
                פתח לידים
              </Button>
              <Button
                variant="secondary"
                className="h-20 flex-col"
                onClick={handleComingSoon}
                data-testid="button-open-whatsapp"
              >
                <MessageCircle className="h-6 w-6 mb-2" />
                פתח WhatsApp
              </Button>
              <Button
                variant="secondary"
                className="h-20 flex-col"
                onClick={handleComingSoon}
                data-testid="button-open-calls"
              >
                <Phone className="h-6 w-6 mb-2" />
                פתח שיחות
              </Button>
              <Button
                variant="secondary"
                className="h-20 flex-col"
                onClick={handleComingSoon}
                data-testid="button-open-calendar"
              >
                <Calendar className="h-6 w-6 mb-2" />
                פתח לוח שנה
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <ActivityFeed
        activities={activity?.items || null}
        isLoading={activityLoading}
        title="פעילות אחרונה - העסק שלך"
      />
    </div>
  );
}