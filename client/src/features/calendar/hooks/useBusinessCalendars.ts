import { useState, useCallback, useEffect } from 'react';
import { http } from '../../../services/http';

export interface BusinessCalendar {
  id: number;
  business_id: number;
  name: string;
  type_key?: string;
  provider: string;
  calendar_external_id?: string;
  is_active: boolean;
  priority: number;
  default_duration_minutes: number;
  buffer_before_minutes: number;
  buffer_after_minutes: number;
  allowed_tags: string[];
  created_at?: string;
  updated_at?: string;
}

interface UseBusinessCalendarsResult {
  calendars: BusinessCalendar[];
  loading: boolean;
  error: string | null;
  refreshCalendars: () => Promise<void>;
}

const LOG_PREFIX = '[useBusinessCalendars]';

export function useBusinessCalendars(): UseBusinessCalendarsResult {
  const [calendars, setCalendars] = useState<BusinessCalendar[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshCalendars = useCallback(async () => {
    console.log(`${LOG_PREFIX} refreshCalendars called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} Fetching /api/calendar/calendars...`);
      const response = await http.get<{calendars: BusinessCalendar[]}>('/api/calendar/calendars');
      console.log(`${LOG_PREFIX} Raw response:`, JSON.stringify(response, null, 2));
      
      const calendarList = response?.calendars || [];
      console.log(`${LOG_PREFIX} Setting ${calendarList.length} calendars`);
      setCalendars(calendarList);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch calendars:`, err);
      setError(err instanceof Error ? err.message : 'Failed to fetch calendars');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log(`${LOG_PREFIX} Initial mount - calling refreshCalendars`);
    refreshCalendars();
  }, [refreshCalendars]);

  return {
    calendars,
    loading,
    error,
    refreshCalendars,
  };
}
