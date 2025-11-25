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

const LOG_PREFIX = '[useStatuses]';

export function useStatuses(): UseStatusesResult {
  const [statuses, setStatuses] = useState<LeadStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatuses = useCallback(async () => {
    console.log(`${LOG_PREFIX} refreshStatuses called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} Fetching /api/statuses...`);
      const response = await http.get<{items: LeadStatus[], total: number} | LeadStatus[]>('/api/statuses');
      console.log(`${LOG_PREFIX} Raw response:`, JSON.stringify(response, null, 2));
      
      let statusList: LeadStatus[] = [];
      if (Array.isArray(response)) {
        console.log(`${LOG_PREFIX} Response is array with ${response.length} items`);
        statusList = response;
      } else if (response && typeof response === 'object' && 'items' in response) {
        console.log(`${LOG_PREFIX} Response has items array with ${response.items?.length || 0} items`);
        statusList = response.items || [];
      } else {
        console.warn(`${LOG_PREFIX} Unknown response format:`, typeof response, response);
      }
      
      console.log(`${LOG_PREFIX} Setting ${statusList.length} statuses:`, statusList.map(s => s.label));
      setStatuses(Array.isArray(statusList) ? statusList : []);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch statuses:`, err);
      console.error(`${LOG_PREFIX} Error details:`, { 
        message: err?.message, 
        status: err?.status,
        error: err?.error 
      });
      setError(err instanceof Error ? err.message : 'Failed to fetch statuses');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log(`${LOG_PREFIX} Initial mount - calling refreshStatuses`);
    refreshStatuses();
  }, [refreshStatuses]);

  const createStatus = useCallback(async (data: Partial<LeadStatus>): Promise<LeadStatus> => {
    console.log(`${LOG_PREFIX} createStatus called with:`, JSON.stringify(data, null, 2));
    try {
      console.log(`${LOG_PREFIX} POSTing to /api/statuses...`);
      const response = await http.post<any>('/api/statuses', data);
      console.log(`${LOG_PREFIX} Create response:`, JSON.stringify(response, null, 2));
      
      // Extract status from response - server returns {message, status: {...}}
      let newStatus: LeadStatus | undefined;
      
      if (response && typeof response === 'object') {
        console.log(`${LOG_PREFIX} Response keys:`, Object.keys(response));
        
        // Primary: server returns {status: {...}}
        if ('status' in response && response.status && typeof response.status === 'object') {
          console.log(`${LOG_PREFIX} Found status in response.status`);
          newStatus = response.status as LeadStatus;
        } 
        // Fallback: direct status object
        else if ('id' in response && 'label' in response) {
          console.log(`${LOG_PREFIX} Response is direct status object`);
          newStatus = response as LeadStatus;
        }
      }
      
      if (newStatus && newStatus.id) {
        // Ensure all required fields have defaults
        if (!newStatus.created_at) {
          newStatus.created_at = new Date().toISOString();
        }
        if (newStatus.order_index === undefined) {
          // Set order_index to end of list
          const maxOrder = statuses.reduce((max, s) => Math.max(max, s.order_index || 0), 0);
          newStatus.order_index = maxOrder + 1;
        }
        
        console.log(`${LOG_PREFIX} SUCCESS - Created status:`, newStatus.label, 'ID:', newStatus.id, 'order:', newStatus.order_index);
        
        // Update local state immediately (no refetch needed)
        setStatuses(prev => {
          const updated = [...prev, newStatus!].sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
          console.log(`${LOG_PREFIX} Updated statuses list:`, updated.map(s => s.label));
          return updated;
        });
        
        return newStatus;
      } else {
        console.error(`${LOG_PREFIX} No valid status in response`);
        // Wait a bit for DB commit, then refresh
        await new Promise(resolve => setTimeout(resolve, 500));
        await refreshStatuses();
        throw new Error('הסטטוס נוצר, רענן את הדף לראות אותו');
      }
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Create status FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה ביצירת הסטטוס';
      throw new Error(errorMsg);
    }
  }, [refreshStatuses, statuses]);

  const updateStatus = useCallback(async (id: number, data: Partial<LeadStatus>): Promise<LeadStatus> => {
    console.log(`${LOG_PREFIX} updateStatus called for ID ${id}:`, data);
    try {
      const response = await http.put<any>(`/api/statuses/${id}`, data);
      console.log(`${LOG_PREFIX} Update response:`, response);
      
      let updatedStatus: LeadStatus | undefined;
      if (response && typeof response === 'object') {
        if ('status' in response && response.status) {
          updatedStatus = response.status;
        } else if ('id' in response) {
          updatedStatus = response as LeadStatus;
        }
      }
      
      if (updatedStatus) {
        console.log(`${LOG_PREFIX} Updated status:`, updatedStatus.label);
        setStatuses(prev => 
          prev.map(status => 
            status.id === id ? { ...status, ...updatedStatus } : status
          )
        );
        return updatedStatus;
      } else {
        console.log(`${LOG_PREFIX} Fallback refresh after update`);
        await refreshStatuses();
        const found = statuses.find(s => s.id === id);
        if (found) return found;
        throw new Error('Status update failed');
      }
    } catch (err) {
      console.error(`${LOG_PREFIX} Update status FAILED:`, err);
      throw err;
    }
  }, [refreshStatuses, statuses]);

  const deleteStatus = useCallback(async (id: number): Promise<void> => {
    console.log(`${LOG_PREFIX} deleteStatus called for ID ${id}`);
    try {
      await http.delete(`/api/statuses/${id}`);
      console.log(`${LOG_PREFIX} Status ${id} deleted successfully`);
      setStatuses(prev => prev.filter(status => status.id !== id));
    } catch (err) {
      console.error(`${LOG_PREFIX} Delete status FAILED:`, err);
      throw err;
    }
  }, []);

  const reorderStatuses = useCallback(async (statusIds: number[]): Promise<void> => {
    console.log(`${LOG_PREFIX} reorderStatuses called:`, statusIds);
    try {
      await http.post('/api/statuses/reorder', { status_ids: statusIds });
      console.log(`${LOG_PREFIX} Reorder successful`);
      
      setStatuses(prev => {
        const statusMap = new Map(prev.map(s => [s.id, s]));
        return statusIds.map((id, index) => {
          const status = statusMap.get(id);
          return status ? { ...status, order_index: index } : null;
        }).filter(Boolean) as LeadStatus[];
      });
    } catch (err) {
      console.error(`${LOG_PREFIX} Reorder FAILED:`, err);
      throw err;
    }
  }, []);

  console.log(`${LOG_PREFIX} Current state - loading: ${loading}, error: ${error}, statuses: ${statuses.length}`);

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
