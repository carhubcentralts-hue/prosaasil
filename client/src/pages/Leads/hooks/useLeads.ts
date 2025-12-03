import { useState, useEffect, useCallback } from 'react';
import { http } from '../../../services/http';
import { useAuth } from '../../../features/auth/hooks';
import { Lead, LeadFilters, CreateLeadRequest, UpdateLeadRequest, MoveLeadRequest } from '../types';

interface UseLeadsResult {
  leads: Lead[];
  loading: boolean;
  error: string | null;
  total: number;
  createLead: (leadData: Partial<CreateLeadRequest>) => Promise<Lead>;
  updateLead: (leadId: number, leadData: UpdateLeadRequest) => Promise<Lead>;
  deleteLead: (leadId: number) => Promise<void>;
  moveLead: (leadId: number, moveData: MoveLeadRequest) => Promise<void>;
  refreshLeads: () => Promise<void>;
  setLeads: React.Dispatch<React.SetStateAction<Lead[]>>;  // ✅ BUILD 170: Expose for optimistic updates
}

interface LeadStats {
  new: number;
  in_progress: number;
  qualified: number;
  won: number;
  lost: number;
  total: number;
}

interface UseLeadStatsResult {
  stats: LeadStats | null;
  loading: boolean;
  error: string | null;
  refreshStats: () => Promise<void>;
}

export function useLeads(passedFilters?: LeadFilters): UseLeadsResult {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const { user } = useAuth();

  // Stabilize filters dependency to prevent infinite loop
  const depKey = JSON.stringify(passedFilters || {});
  // Only system_admin uses admin endpoint - owners use regular /api/leads with their tenant
  const isSystemAdmin = user?.role === 'system_admin';
  const filters = passedFilters || {};

  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Add timeout to prevent infinite hanging
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      // Build query parameters - admin endpoint uses 'search', regular endpoint uses 'q'
      const params = new URLSearchParams();
      
      if (filters.search) params.append(isSystemAdmin ? 'search' : 'q', filters.search);
      if (filters.status) params.append('status', filters.status);
      if (filters.source) params.append('source', filters.source);
      if (filters.owner_user_id) params.append('owner_user_id', filters.owner_user_id.toString());
      if (filters.page) params.append('page', filters.page.toString());
      if (filters.pageSize) params.append('pageSize', filters.pageSize.toString());

      const queryString = params.toString();
      const url = isSystemAdmin 
        ? `/api/admin/leads${queryString ? `?${queryString}` : ''}`
        : `/api/leads${queryString ? `?${queryString}` : ''}`;
      
      console.log('[useLeads] Fetching:', url, 'search:', filters.search);
      
      const response = await http.get<{leads?: Lead[], items?: Lead[], total: number}>(url, {
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      console.log('[useLeads] Response items:', response.items?.length || 0, 'leads:', response.leads?.length || 0, 'total:', response.total);
      
      // Handle both regular endpoint (leads) and admin endpoint (items) response formats
      const leadsList = response.leads || response.items || [];
      setLeads(leadsList);
      setTotal(response.total || leadsList.length);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.name === 'AbortError' ? 'Request timeout - please try again' : err.message);
      } else {
        setError('Failed to fetch leads');
      }
      setLeads([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [depKey, isSystemAdmin]);

  const createLead = useCallback(async (leadData: Partial<CreateLeadRequest>): Promise<Lead> => {
    try {
      const response = await http.post<{lead: Lead}>('/api/leads', leadData);
      
      if (response.lead) {
        // Add the new lead to the current list
        setLeads(prevLeads => [response.lead, ...prevLeads]);
        setTotal(prevTotal => prevTotal + 1);
        return response.lead;
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      throw err;
    }
  }, []);

  const updateLead = useCallback(async (leadId: number, leadData: UpdateLeadRequest): Promise<Lead> => {
    try {
      const response = await http.patch<{lead: Lead}>(`/api/leads/${leadId}`, leadData);
      
      if (response.lead) {
        setLeads(prevLeads => 
          prevLeads.map(lead => 
            lead.id === leadId ? { ...lead, ...response.lead } : lead
          )
        );
        return response.lead;
      } else {
        throw new Error('Invalid response format');
      }
    } catch (err) {
      throw err;
    }
  }, []);

  const deleteLead = useCallback(async (leadId: number): Promise<void> => {
    try {
      await http.delete(`/api/leads/${leadId}`);
      setLeads(prevLeads => prevLeads.filter(lead => lead.id !== leadId));
      setTotal(prevTotal => prevTotal - 1);
    } catch (err) {
      throw err;
    }
  }, []);

  const moveLead = useCallback(async (leadId: number, moveData: MoveLeadRequest): Promise<void> => {
    try {
      await http.patch(`/api/leads/${leadId}/move`, moveData);
    } catch (err) {
      throw err;
    }
  }, []);

  const refreshLeads = useCallback(async () => {
    await fetchLeads();
  }, [fetchLeads]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  return {
    leads,
    loading,
    error,
    total,
    createLead,
    updateLead,
    deleteLead,
    moveLead,
    refreshLeads,
    setLeads,  // ✅ BUILD 170: Expose for optimistic updates
  };
}

export function useLeadStats(): UseLeadStatsResult {
  const [stats, setStats] = useState<LeadStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Admin stats endpoint is only for system_admin
      const isSystemAdmin = user?.role === 'system_admin';
      if (!isSystemAdmin) {
        // For non-system-admin users, we skip fetching admin stats
        setStats(null);
        setLoading(false);
        return;
      }
      
      const response = await http.get<LeadStats>('/api/admin/leads/stats');
      setStats(response);
    } catch (err) {
      console.error('Failed to fetch leads stats:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch leads stats');
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [user?.role]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    refreshStats: fetchStats,
  };
}