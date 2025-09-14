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

export function useLeads(filters: LeadFilters = {}): UseLeadsResult {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const { user } = useAuth();

  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Build query parameters
      const params = new URLSearchParams();
      
      if (filters.search) {
        params.append('search', filters.search);
      }
      if (filters.status) {
        params.append('status', filters.status);
      }
      if (filters.source) {
        params.append('source', filters.source);
      }
      if (filters.owner_user_id) {
        params.append('owner_user_id', filters.owner_user_id.toString());
      }
      if (filters.page) {
        params.append('page', filters.page.toString());
      }
      if (filters.pageSize) {
        params.append('pageSize', filters.pageSize.toString());
      }

      const queryString = params.toString();
      // Use admin endpoint for admin/manager roles to see all tenants' leads
      const isAdmin = user?.role === 'admin' || user?.role === 'manager';
      const url = isAdmin 
        ? `/api/admin/leads${queryString ? `?${queryString}` : ''}`
        : `/api/leads${queryString ? `?${queryString}` : ''}`;
      
      const response = await http.get<{leads?: Lead[], items?: Lead[], total: number}>(url);
      
      // Handle both regular endpoint (leads) and admin endpoint (items) response formats
      const leadsList = response.leads || response.items || [];
      setLeads(leadsList);
      setTotal(response.total || leadsList.length);
    } catch (err) {
      console.error('Failed to fetch leads:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch leads');
      setLeads([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters]);

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
      console.error('Failed to create lead:', err);
      throw err;
    }
  }, []);

  const updateLead = useCallback(async (leadId: number, leadData: UpdateLeadRequest): Promise<Lead> => {
    try {
      const response = await http.patch<{lead: Lead}>(`/api/leads/${leadId}`, leadData);
      
      if (response.lead) {
        // Update the lead in the current list
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
      console.error('Failed to update lead:', err);
      throw err;
    }
  }, []);

  const deleteLead = useCallback(async (leadId: number): Promise<void> => {
    try {
      await http.delete(`/api/leads/${leadId}`);
      
      // Remove the lead from the current list
      setLeads(prevLeads => prevLeads.filter(lead => lead.id !== leadId));
      setTotal(prevTotal => prevTotal - 1);
    } catch (err) {
      console.error('Failed to delete lead:', err);
      throw err;
    }
  }, []);

  const moveLead = useCallback(async (leadId: number, moveData: MoveLeadRequest): Promise<void> => {
    try {
      await http.patch(`/api/leads/${leadId}/move`, moveData);
      
      // The parent component will call refreshLeads() after this
    } catch (err) {
      console.error('Failed to move lead:', err);
      throw err;
    }
  }, []);

  const refreshLeads = useCallback(async () => {
    await fetchLeads();
  }, [fetchLeads]);

  // Initial fetch and when filters change
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
      
      // Use admin endpoint for admin/manager/superadmin roles
      const isAdmin = user?.role === 'admin' || user?.role === 'manager';
      if (!isAdmin) {
        throw new Error('Admin access required');
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