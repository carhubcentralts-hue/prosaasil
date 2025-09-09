// business dashboard hooks for data fetching
import { useState, useEffect, useCallback } from 'react';
import { businessApi, type BusinessDashboardStats, type BusinessActivity } from './api';

export const useBusinessDashboard = () => {
  const [stats, setStats] = useState<BusinessDashboardStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState<Error | null>(null);
  
  const [activity, setActivity] = useState<BusinessActivity[]>([]);
  const [isLoadingActivity, setIsLoadingActivity] = useState(true);
  const [activityError, setActivityError] = useState<Error | null>(null);
  
  const fetchStats = useCallback(async () => {
    setIsLoadingStats(true);
    setStatsError(null);
    try {
      const result = await businessApi.getDashboardStats();
      setStats(result);
    } catch (err) {
      setStatsError(err instanceof Error ? err : new Error('Failed to fetch business stats'));
    } finally {
      setIsLoadingStats(false);
    }
  }, []);
  
  const fetchActivity = useCallback(async () => {
    setIsLoadingActivity(true);
    setActivityError(null);
    try {
      const result = await businessApi.getDashboardActivity();
      setActivity(result);
    } catch (err) {
      setActivityError(err instanceof Error ? err : new Error('Failed to fetch business activity'));
    } finally {
      setIsLoadingActivity(false);
    }
  }, []);
  
  useEffect(() => {
    fetchStats();
    fetchActivity();
  }, [fetchStats, fetchActivity]);
  
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