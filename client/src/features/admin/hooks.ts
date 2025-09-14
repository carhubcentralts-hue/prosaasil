// admin hooks for data fetching
import { useState, useEffect, useCallback } from 'react';
import { adminApi, type TimeFilterParams, type AdminOverviewResponse } from './api';

export const useAdminOverview = (params: TimeFilterParams) => {
  const [data, setData] = useState<AdminOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await adminApi.getOverview(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch overview data'));
    } finally {
      setIsLoading(false);
    }
  }, [params.time_filter, params.start_date, params.end_date]);
  
  useEffect(() => {
    refetch();
  }, [refetch]);
  
  return { data, isLoading, error, refetch };
};

export const useAdminCallsKPI = (params: TimeFilterParams) => {
  const [data, setData] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await adminApi.getCallsKPI(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch calls KPI'));
    } finally {
      setIsLoading(false);
    }
  }, [params.time_filter, params.start_date, params.end_date]);
  
  useEffect(() => {
    refetch();
  }, [refetch]);
  
  return { data, isLoading, error, refetch };
};

export const useAdminWhatsappKPI = (params: TimeFilterParams) => {
  const [data, setData] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await adminApi.getWhatsappKPI(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch WhatsApp KPI'));
    } finally {
      setIsLoading(false);
    }
  }, [params.time_filter, params.start_date, params.end_date]);
  
  useEffect(() => {
    refetch();
  }, [refetch]);
  
  return { data, isLoading, error, refetch };
};

// Helper function to generate date ranges
export const getDateRangeForFilter = (filter: 'today' | 'week' | 'month' | 'custom', customStart?: Date, customEnd?: Date) => {
  const today = new Date();
  const formatDate = (date: Date) => date.toISOString().split('T')[0];
  
  switch (filter) {
    case 'today':
      return {
        time_filter: 'today' as const,
        start_date: formatDate(today),
        end_date: formatDate(today),
      };
      
    case 'week':
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - 7);
      return {
        time_filter: 'week' as const,
        start_date: formatDate(weekStart),
        end_date: formatDate(today),
      };
      
    case 'month':
      const monthStart = new Date(today);
      monthStart.setDate(today.getDate() - 30);
      return {
        time_filter: 'month' as const,
        start_date: formatDate(monthStart),
        end_date: formatDate(today),
      };
      
    case 'custom':
      if (!customStart || !customEnd) {
        throw new Error('Custom filter requires start and end dates');
      }
      return {
        time_filter: 'custom' as const,
        start_date: formatDate(customStart),
        end_date: formatDate(customEnd),
      };
      
    default:
      return {
        time_filter: 'today' as const,
        start_date: formatDate(today),
        end_date: formatDate(today),
      };
  }
};

export function usePhoneNumbers() {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchPhoneNumbers = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const result = await adminApi.getPhoneNumbers();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPhoneNumbers();
  }, [fetchPhoneNumbers]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchPhoneNumbers
  };
}

// Admin Support Management Hooks
export function useSupportProfile() {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchSupportProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const result = await adminApi.getSupportProfile();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSupportProfile();
  }, [fetchSupportProfile]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchSupportProfile
  };
}

export function useSupportPrompt() {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchSupportPrompt = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const result = await adminApi.getSupportPrompt();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSupportPrompt();
  }, [fetchSupportPrompt]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchSupportPrompt
  };
}

export function useSupportPhones() {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchSupportPhones = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const result = await adminApi.getSupportPhones();
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSupportPhones();
  }, [fetchSupportPhones]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchSupportPhones
  };
}