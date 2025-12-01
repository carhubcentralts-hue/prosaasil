// business dashboard hooks for data fetching
import { useState, useEffect, useCallback } from 'react';
import { businessApi, type BusinessDashboardStats, type BusinessActivity } from './api';
import { useAuth } from '../auth/hooks';

export const useBusinessDashboard = () => {
  const { user, tenant, impersonating } = useAuth();
  const [stats, setStats] = useState<BusinessDashboardStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState<Error | null>(null);
  
  const [activity, setActivity] = useState<BusinessActivity[]>([]);
  const [isLoadingActivity, setIsLoadingActivity] = useState(true);
  const [activityError, setActivityError] = useState<Error | null>(null);
  
  const fetchStats = useCallback(async () => {
    console.log('🔍 Fetching dashboard stats...', { user: user?.email, tenant: tenant?.name, impersonating });
    setIsLoadingStats(true);
    setStatsError(null);
    try {
      const result = await businessApi.getDashboardStats();
      console.log('✅ Dashboard stats loaded:', result);
      setStats(result);
    } catch (err) {
      console.error('❌ Dashboard stats error:', err);
      setStatsError(err instanceof Error ? err : new Error('Failed to fetch business stats'));
    } finally {
      setIsLoadingStats(false);
    }
  }, [user, tenant, impersonating]);
  
  const fetchActivity = useCallback(async () => {
    console.log('🔍 Fetching dashboard activity...', { user: user?.email, tenant: tenant?.name, impersonating });
    setIsLoadingActivity(true);
    setActivityError(null);
    try {
      const result = await businessApi.getDashboardActivity();
      console.log('✅ Dashboard activity loaded:', result);
      setActivity(result);
    } catch (err) {
      console.error('❌ Dashboard activity error:', err);
      setActivityError(err instanceof Error ? err : new Error('Failed to fetch business activity'));
    } finally {
      setIsLoadingActivity(false);
    }
  }, [user, tenant, impersonating]);
  
  // Re-fetch when auth state changes (important for impersonation!)
  useEffect(() => {
    console.log('🔍 useBusinessDashboard useEffect triggered:', { 
      user: user?.email, 
      tenant: tenant?.name, 
      impersonating,
      hasUser: !!user,
      hasTenant: !!tenant,
      willFetch: !!(user && tenant)
    });
    
    if (user && tenant) {  // Only fetch when we have auth state
      console.log('🔄 Auth state changed, re-fetching dashboard data...', { impersonating, tenant: tenant.name });
      // Fire both in parallel (each handles its own errors and loading state)
      fetchStats();
      fetchActivity();
    } else {
      console.log('⚠️ Not fetching dashboard data - missing auth state:', { user: !!user, tenant: !!tenant });
    }
  }, [user, tenant, impersonating, fetchStats, fetchActivity]);
  
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