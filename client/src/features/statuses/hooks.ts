import { useState, useCallback, useMemo } from 'react';
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
  created_at: string;
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
      
      const response = await http.get<{items: LeadStatus[], total: number}>('/api/statuses');
      setStatuses(response.items || []);
    } catch (err) {
      console.error('Failed to fetch statuses:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch statuses');
    } finally {
      setLoading(false);
    }
  }, []);

  const createStatus = useCallback(async (data: Partial<LeadStatus>): Promise<LeadStatus> => {
    try {
      const response = await http.post<{status: LeadStatus}>('/api/statuses', data);
      
      if (response.status) {
        setStatuses(prev => [...prev, response.status].sort((a, b) => a.order_index - b.order_index));
        return response.status;
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      console.error('Failed to create status:', err);
      throw err;
    }
  }, []);

  const updateStatus = useCallback(async (id: number, data: Partial<LeadStatus>): Promise<LeadStatus> => {
    try {
      const response = await http.put<{status: LeadStatus}>(`/api/statuses/${id}`, data);
      
      if (response.status) {
        setStatuses(prev => 
          prev.map(status => 
            status.id === id ? { ...status, ...response.status } : status
          )
        );
        return response.status;
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      console.error('Failed to update status:', err);
      throw err;
    }
  }, []);

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
      
      // Update local state to match new order
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