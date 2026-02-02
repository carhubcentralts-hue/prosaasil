import { useState, useCallback, useEffect } from 'react';
import { http } from '../../../services/http';
import { AppointmentTypeConfig } from '../../../shared/types/status';

interface UseAppointmentTypesResult {
  types: AppointmentTypeConfig[];
  loading: boolean;
  error: string | null;
  refreshTypes: () => Promise<void>;
  updateTypes: (types: AppointmentTypeConfig[]) => Promise<void>;
}

const LOG_PREFIX = '[useAppointmentTypes]';

export function useAppointmentTypes(): UseAppointmentTypesResult {
  const [types, setTypes] = useState<AppointmentTypeConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshTypes = useCallback(async () => {
    console.log(`${LOG_PREFIX} refreshTypes called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} Fetching /api/calendar/config/appointment-types...`);
      const response = await http.get<{appointment_types: AppointmentTypeConfig[]}>('/api/calendar/config/appointment-types');
      console.log(`${LOG_PREFIX} Raw response:`, JSON.stringify(response, null, 2));
      
      const typeList = response?.appointment_types || [];
      console.log(`${LOG_PREFIX} Setting ${typeList.length} types:`, typeList.map(t => t.label));
      setTypes(typeList);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch types:`, err);
      setError(err instanceof Error ? err.message : 'Failed to fetch appointment types');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log(`${LOG_PREFIX} Initial mount - calling refreshTypes`);
    refreshTypes();
  }, [refreshTypes]);

  const updateTypes = useCallback(async (newTypes: AppointmentTypeConfig[]): Promise<void> => {
    console.log(`${LOG_PREFIX} updateTypes called with:`, JSON.stringify(newTypes, null, 2));
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} PUTing to /api/calendar/config/appointment-types...`);
      const response = await http.put<any>('/api/calendar/config/appointment-types', {
        appointment_types: newTypes
      });
      console.log(`${LOG_PREFIX} Update response:`, JSON.stringify(response, null, 2));
      
      // Update local state
      setTypes(newTypes);
      console.log(`${LOG_PREFIX} Successfully updated types`);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Update types FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה בעדכון סוגי פגישות';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    types,
    loading,
    error,
    refreshTypes,
    updateTypes,
  };
}
