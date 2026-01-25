// business dashboard hooks for data fetching
import { useState, useEffect, useCallback } from 'react';
import { businessApi, type BusinessDashboardStats, type BusinessActivity, type TimeFilter, type DateRange } from './api';
import { useAuth } from '../auth/hooks';

export const useBusinessDashboard = (timeFilter: TimeFilter = 'today', dateRange?: DateRange) => {
  const { user, tenant, impersonating } = useAuth();
  const [stats, setStats] = useState<BusinessDashboardStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState<Error | null>(null);
  
  const [activity, setActivity] = useState<BusinessActivity[]>([]);
  const [isLoadingActivity, setIsLoadingActivity] = useState(true);
  const [activityError, setActivityError] = useState<Error | null>(null);
  
  const fetchStats = useCallback(async () => {
    console.log('🔍 Fetching dashboard stats...', { user: user?.email, tenant: tenant?.name, timeFilter });
    setIsLoadingStats(true);
    setStatsError(null);
    try {
      const result = await businessApi.getDashboardStats(timeFilter, dateRange);
      console.log('✅ Dashboard stats loaded:', result);
      setStats(result);
    } catch (err) {
      console.error('❌ Dashboard stats error:', err);
      setStatsError(err instanceof Error ? err : new Error('Failed to fetch business stats'));
    } finally {
      setIsLoadingStats(false);
    }
  }, [timeFilter, dateRange]); // 🔥 FIX: Only re-create when filter changes, not on every auth change
  
  const fetchActivity = useCallback(async () => {
    console.log('🔍 Fetching dashboard activity...', { user: user?.email, tenant: tenant?.name, timeFilter });
    setIsLoadingActivity(true);
    setActivityError(null);
    try {
      const result = await businessApi.getDashboardActivity(timeFilter, dateRange);
      console.log('✅ Dashboard activity loaded:', result);
      setActivity(result);
    } catch (err) {
      console.error('❌ Dashboard activity error:', err);
      setActivityError(err instanceof Error ? err : new Error('Failed to fetch business activity'));
    } finally {
      setIsLoadingActivity(false);
    }
  }, [timeFilter, dateRange]); // 🔥 FIX: Only re-create when filter changes, not on every auth change
  
  // Re-fetch when auth state or time filter changes
  // 🔥 FIX: Don't include fetchStats/fetchActivity in deps to avoid infinite loop
  useEffect(() => {
    if (user && tenant) {
      console.log('🔄 Fetching dashboard data...', { timeFilter, tenant: tenant.name });
      fetchStats();
      fetchActivity();
    }
  }, [user?.id, tenant?.id, timeFilter, dateRange]); // 🔥 FIX: Use stable IDs, not objects
  
  const refetch = useCallback(() => {
    fetchStats();
    fetchActivity();
  }, [fetchStats, fetchActivity]);
  
  return {
    stats,
    isLoadingStats,
    statsError,
    activity,
    isLoadingActivity,
    activityError,
    refetch
  };
};

export { type TimeFilter, type DateRange } from './api';