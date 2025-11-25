import { useState, useCallback, useEffect } from 'react';
import { http } from '../../services/http';

export interface LeadStatus {
  id: number;
  name: string;
  label: string;
  color: string;
  description?: string;
  order_index: number;
  is_default: boolean;
  is_system: boolean;
  created_at?: string;
}

interface UseStatusesResult {
  statuses: LeadStatus[];
  loading: boolean;
  error: string | null;
  refreshStatuses: () => Promise<void>;
  createStatus: (data: Partial<LeadStatus>) => Promise<LeadStatus>;
  updateStatus: (id: number, data: Partial<LeadStatus>) => Promise<LeadStatus>;
  deleteStatus: (id: number) => Promise<void>;
  reorderStatuses: (statusIds: number[]) => Promise<void>;
}

export function useStatuses(): UseStatusesResult {
  const [statuses, setStatuses] = useState<LeadStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatuses = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await http.get<{items: LeadStatus[], total: number} | LeadStatus[]>('/api/statuses');
      
      let statusList: LeadStatus[] = [];
      if (Array.isArray(response)) {
        statusList = response;
      } else if (response && typeof response === 'object' && 'items' in response) {
        statusList = response.items || [];
      }
      
      setStatuses(Array.isArray(statusList) ? statusList : []);
    } catch (err) {
      console.error('Failed to fetch statuses:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch statuses');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStatuses();
  }, [refreshStatuses]);

  const createStatus = useCallback(async (data: Partial<LeadStatus>): Promise<LeadStatus> => {
    try {
      console.log('Creating status with data:', data);
      const response = await http.post<any>('/api/statuses', data);
      console.log('Create status response:', response);
      
      let newStatus: LeadStatus | undefined;
      
      if (response && typeof response === 'object') {
        if ('status' in response && response.status && typeof response.status === 'object') {
          newStatus = response.status as LeadStatus;
        } else if ('id' in response && 'name' in response && 'label' in response) {
          newStatus = response as LeadStatus;
        } else if ('data' in response && response.data) {
          newStatus = response.data as LeadStatus;
        } else if ('item' in response && response.item) {
          newStatus = response.item as LeadStatus;
        }
      }
      
      if (newStatus && newStatus.id) {
        if (!newStatus.created_at) {
          newStatus.created_at = new Date().toISOString();
        }
        setStatuses(prev => [...prev, newStatus!].sort((a, b) => (a.order_index || 0) - (b.order_index || 0)));
        return newStatus;
      } else {
        console.log('No newStatus found in response, refreshing...');
        await refreshStatuses();
        const latestStatuses = await http.get<{items: LeadStatus[]}>('/api/statuses');
        const items = latestStatuses?.items || [];
        if (items.length > 0) {
          const latest = items[items.length - 1];
          return latest;
        }
        throw new Error('Could not find created status');
      }
    } catch (err: any) {
      console.error('Failed to create status:', err);
      const errorMsg = err?.error || err?.message || 'שגיאה ביצירת הסטטוס';
      throw new Error(errorMsg);
    }
  }, [refreshStatuses]);

  const updateStatus = useCallback(async (id: number, data: Partial<LeadStatus>): Promise<LeadStatus> => {
    try {
      const response = await http.put<any>(`/api/statuses/${id}`, data);
      
      let updatedStatus: LeadStatus | undefined;
      if (response && typeof response === 'object') {
        if ('status' in response && response.status) {
          updatedStatus = response.status;
        } else if ('id' in response) {
          updatedStatus = response as LeadStatus;
        }
      }
      
      if (updatedStatus) {
        setStatuses(prev => 
          prev.map(status => 
            status.id === id ? { ...status, ...updatedStatus } : status
          )
        );
        return updatedStatus;
      } else {
        await refreshStatuses();
        const found = statuses.find(s => s.id === id);
        if (found) return found;
        throw new Error('Status update failed');
      }
    } catch (err) {
      console.error('Failed to update status:', err);
      throw err;
    }
  }, [refreshStatuses, statuses]);

  const deleteStatus = useCallback(async (id: number): Promise<void> => {
    try {
      await http.delete(`/api/statuses/${id}`);
      setStatuses(prev => prev.filter(status => status.id !== id));
    } catch (err) {
      console.error('Failed to delete status:', err);
      throw err;
    }
  }, []);

  const reorderStatuses = useCallback(async (statusIds: number[]): Promise<void> => {
    try {
      await http.post('/api/statuses/reorder', { status_ids: statusIds });
      
      setStatuses(prev => {
        const statusMap = new Map(prev.map(s => [s.id, s]));
        return statusIds.map((id, index) => {
          const status = statusMap.get(id);
          return status ? { ...status, order_index: index } : null;
        }).filter(Boolean) as LeadStatus[];
      });
    } catch (err) {
      console.error('Failed to reorder statuses:', err);
      throw err;
    }
  }, []);

  return {
    statuses,
    loading,
    error,
    refreshStatuses,
    createStatus,
    updateStatus,
    deleteStatus,
    reorderStatuses,
  };
}
