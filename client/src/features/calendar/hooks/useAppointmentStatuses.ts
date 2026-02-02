import { useState, useCallback, useEffect } from 'react';
import { http } from '../../../services/http';
import { AppointmentStatusConfig } from '../../../shared/types/status';

interface UseAppointmentStatusesResult {
  statuses: AppointmentStatusConfig[];
  loading: boolean;
  error: string | null;
  refreshStatuses: () => Promise<void>;
  updateStatuses: (statuses: AppointmentStatusConfig[]) => Promise<void>;
}

const LOG_PREFIX = '[useAppointmentStatuses]';

export function useAppointmentStatuses(): UseAppointmentStatusesResult {
  const [statuses, setStatuses] = useState<AppointmentStatusConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatuses = useCallback(async () => {
    console.log(`${LOG_PREFIX} refreshStatuses called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} Fetching /api/calendar/config/appointment-statuses...`);
      const response = await http.get<{appointment_statuses: AppointmentStatusConfig[]}>('/api/calendar/config/appointment-statuses');
      console.log(`${LOG_PREFIX} Raw response:`, JSON.stringify(response, null, 2));
      
      const statusList = response?.appointment_statuses || [];
      console.log(`${LOG_PREFIX} Setting ${statusList.length} statuses:`, statusList.map(s => s.label));
      setStatuses(statusList);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch statuses:`, err);
      setError(err instanceof Error ? err.message : 'Failed to fetch appointment statuses');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log(`${LOG_PREFIX} Initial mount - calling refreshStatuses`);
    refreshStatuses();
  }, [refreshStatuses]);

  const updateStatuses = useCallback(async (newStatuses: AppointmentStatusConfig[]): Promise<void> => {
    console.log(`${LOG_PREFIX} updateStatuses called with:`, JSON.stringify(newStatuses, null, 2));
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} PUTing to /api/calendar/config/appointment-statuses...`);
      const response = await http.put<any>('/api/calendar/config/appointment-statuses', {
        appointment_statuses: newStatuses
      });
      console.log(`${LOG_PREFIX} Update response:`, JSON.stringify(response, null, 2));
      
      // Update local state
      setStatuses(newStatuses);
      console.log(`${LOG_PREFIX} Successfully updated statuses`);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Update statuses FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה בעדכון סטטוסים';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    statuses,
    loading,
    error,
    refreshStatuses,
    updateStatuses,
  };
}
