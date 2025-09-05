import React from 'react';
import { Users, MessageCircle, Phone, Building2, Calendar } from 'lucide-react';
import { statusApi } from '../../features/status/api';
import { useApi } from '../../shared/hooks/useApi';
import { StatCard } from '../../shared/components/StatCard';
import { StatCardSkeleton } from '../../shared/components/Skeleton';
import { ProviderStatus } from '../../shared/components/ProviderStatus';
import { ActivityFeed } from '../../shared/components/ActivityFeed';
import { formatNumber, formatDuration } from '../../shared/utils/format';

export function AdminHomePage() {
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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" dir="rtl">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          לוח בקרה - מנהל מערכת
        </h1>
        <p className="text-gray-600 mt-1">
          סקירה כללית של כל הפעילות במערכת
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
              title="עסקים פעילים"
              value="12" // This would come from admin-specific endpoint
              icon={<Building2 className="h-6 w-6" />}
              data-testid="stat-businesses"
            />
            <StatCard
              title="שיחות היום"
              value={stats.calls.today}
              subtitle={`ממוצע ${formatDuration(stats.calls.avgHandleSec)}`}
              icon={<Phone className="h-6 w-6" />}
              data-testid="stat-calls-today"
            />
            <StatCard
              title="WhatsApp היום"
              value={stats.whatsapp.today}
              subtitle={`${stats.whatsapp.unread} לא נקראו`}
              icon={<MessageCircle className="h-6 w-6" />}
              data-testid="stat-whatsapp-today"
            />
            <StatCard
              title="פגישות היום"
              value="8" // This would come from calendar integration
              icon={<Calendar className="h-6 w-6" />}
              data-testid="stat-meetings-today"
            />
          </>
        ) : (
          <div className="col-span-4 text-center py-8">
            <p className="text-gray-500">שגיאה בטעינת נתונים</p>
          </div>
        )}
      </div>

      {/* 7-day Activity Chart Placeholder */}
      <div className="mb-8">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            פעילות 7 ימים אחרונים
          </h3>
          <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
            <p className="text-gray-500">גרף פעילות - יתווסף בשלב הבא</p>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <ActivityFeed
        activities={activity?.items || null}
        isLoading={activityLoading}
        title="פעילות אחרונה - כל המערכת"
      />
    </div>
  );
}