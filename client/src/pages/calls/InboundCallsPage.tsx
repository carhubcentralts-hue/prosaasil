import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Phone, 
  PhoneIncoming, 
  Users, 
  Loader2, 
  AlertTriangle, 
  CheckCircle2,
  XCircle,
  Search,
  PlayCircle,
  Download,
  LayoutGrid,
  List,
  StopCircle,
  Clock
} from 'lucide-react';
import { formatDateOnly, formatDate } from '../../shared/utils/format';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { Select } from '../../shared/components/ui/Select';
import { MultiStatusSelect } from '../../shared/components/ui/MultiStatusSelect';
import { StatusCell } from '../../shared/components/ui/StatusCell';
import { StatusDropdownWithWebhook } from '../../shared/components/ui/StatusDropdownWithWebhook';
import { AudioPlayer } from '../../shared/components/AudioPlayer';
import { http } from '../../services/http';
import { OutboundKanbanView } from './components/OutboundKanbanView';
import { Lead } from '../Leads/types';  // ✅ Use shared Lead type
import type { LeadStatusConfig } from '../../shared/types/status';

// Type alias for backward compatibility
type LeadStatus = LeadStatusConfig;

interface CallCounts {
  active_total: number;
  active_outbound: number;
  max_total: number;
  max_outbound: number;
}

interface CallResult {
  lead_id: number;
  lead_name: string;
  call_sid?: string;
  status: string;
  error?: string;
}

type TabType = 'system' | 'active' | 'recent';

// Default number of available call slots when counts haven't loaded yet
const DEFAULT_AVAILABLE_SLOTS = 3;
type ViewMode = 'table' | 'kanban';

interface RecentCall {
  call_sid: string;
  to_number: string;
  lead_id: number | null;
  lead_name: string | null;
  lead_status: string | null;  // ✅ FIX: Add lead_status field
  status: string;  // call status (completed, failed, etc.)
  started_at: string | null;
  ended_at: string | null;
  duration: number;
  recording_url: string | null;
  recording_sid: string | null;
  transcript: string | null;
  summary: string | null;
}

export function InboundCallsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  
  // Tab and view state
  const [activeTab, setActiveTab] = useState<TabType>('system');
  const [viewMode, setViewMode] = useState<ViewMode>('kanban'); // Default to Kanban
  const [hasWebhook, setHasWebhook] = useState(false);
  
  // ✅ Sync tab with URL on mount
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const tabParam = sp.get('tab') as TabType | null;
    if (tabParam && ['system', 'active', 'recent'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [location.search]);
  
  // ✅ Update URL when tab changes
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const currentTab = sp.get('tab');
    if (currentTab !== activeTab) {
      sp.set('tab', activeTab);
      navigate(`${location.pathname}?${sp.toString()}`, { replace: true });
    }
  }, [activeTab, navigate, location.pathname]);
  
  // Existing leads state
  const [selectedLeads, setSelectedLeads] = useState<Set<number>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [callResults, setCallResults] = useState<CallResult[]>([]);
  const [systemLeadsPage, setSystemLeadsPage] = useState(1);
  const [activeLeadsPage, setActiveLeadsPage] = useState(1);
  const systemLeadsPageSize = 50;
  
  // State for UI controls
  const [updatingStatusLeadId, setUpdatingStatusLeadId] = useState<number | null>(null);
  
  // Queue state
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [queueStatus, setQueueStatus] = useState<{
    queued: number;
    in_progress: number;
    completed: number;
    failed: number;
  } | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null); // Store interval ID

  // Support deep-link from Lead page tiles: /app/calls?phone=... or ?leadId=...
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const phone = sp.get('phone');
    const leadId = sp.get('leadId');
    if (phone) {
      setActiveTab('system');
      setSearchQuery(phone);
    } else if (leadId) {
      setActiveTab('system');
      setSearchQuery(leadId);
    }
  }, [location.search]);

  // Queries
  // 🔥 FIX: Only poll for counts when there's actually a running process
  const { data: counts, isLoading: countsLoading, refetch: refetchCounts, error: countsError } = useQuery<CallCounts>({
    queryKey: ['/api/inbound_calls/counts'],
    refetchInterval: activeRunId ? 10000 : false, // Only poll when queue is running
    enabled: true, // Always enabled for initial fetch
    retry: 1,
    staleTime: 0, // ✅ FIX: Always fetch fresh data, no cache
    gcTime: 0, // ✅ FIX: Don't keep in cache (renamed from cacheTime in v5)
  });

  // Fetch lead statuses for both Kanban and Table views
  const { data: statusesData, isLoading: statusesLoading } = useQuery<LeadStatus[]>({
    queryKey: ['/api/lead-statuses'],
    enabled: true, // ✅ Always load statuses for both view modes
    retry: 1,
  });

  useEffect(() => {
    if (statusesData) {
      console.log('[InboundCallsPage] ✅ Lead statuses loaded:', statusesData);
    }
  }, [statusesData]);

  // Check if business has status webhook configured
  useEffect(() => {
    const loadWebhookStatus = async () => {
      try {
        const response = await http.get('/api/business/current');
        setHasWebhook(!!response.status_webhook_url);
      } catch (error) {
        console.error('Error loading webhook status:', error);
      }
    };
    loadWebhookStatus();
  }, []);

  const { data: leadsData, isLoading: leadsLoading, error: leadsError } = useQuery({
    queryKey: ['/api/leads', 'system', searchQuery, selectedStatuses, systemLeadsPage],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(systemLeadsPage),
        pageSize: String(systemLeadsPageSize),
      });
      
      if (searchQuery) {
        params.append('q', searchQuery);
      }

      // Add multi-status filter
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => {
          params.append('statuses[]', status);
        });
      }

      return await http.get(`/api/leads?${params.toString()}`);
    },
    enabled: activeTab === 'system',
    select: (data: any) => {
      if (!data) return { leads: [], total: 0 };
      // Try different response formats for backward compatibility
      if (Array.isArray(data)) return { leads: data, total: data.length };
      if (data.items && Array.isArray(data.items)) return { leads: data.items, total: data.total || data.items.length };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads, total: data.total || data.leads.length };
      return { leads: [], total: 0 };
    },
    retry: 1,
  });

  // Query for active outbound leads (leads assigned to outbound campaign)
  const { data: activeLeadsData, isLoading: activeLoading, error: activeError } = useQuery({
    queryKey: ['/api/leads', 'active-outbound', searchQuery, selectedStatuses, activeLeadsPage],
    queryFn: async () => {
      const params = new URLSearchParams({
        direction: 'inbound',
        page: String(activeLeadsPage),
        pageSize: String(systemLeadsPageSize),
      });
      
      if (searchQuery) {
        params.append('q', searchQuery);
      }

      // Add multi-status filter
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => {
          params.append('statuses[]', status);
        });
      }

      return await http.get(`/api/leads?${params.toString()}`);
    },
    enabled: activeTab === 'active',
    select: (data: any) => {
      if (!data) return { leads: [], total: 0 };
      if (Array.isArray(data)) return { leads: data, total: data.length };
      if (data.items && Array.isArray(data.items)) return { leads: data.items, total: data.total || data.items.length };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads, total: data.total || data.leads.length };
      return { leads: [], total: 0 };
    },
    retry: 1,
  });

  useEffect(() => {
    if (leadsData?.leads) {
      console.log('[InboundCallsPage] ✅ System leads loaded:', leadsData.leads.length, 'leads');
    }
  }, [leadsData]);

  useEffect(() => {
    if (activeLeadsData?.leads) {
      console.log('[InboundCallsPage] ✅ Active outbound leads loaded:', activeLeadsData.leads.length, 'leads');
    }
  }, [activeLeadsData]);

  // 🔥 REQUIREMENT FIX: Reset UI state and fetch fresh from server
  // ✅ FIX: Clear all outbound UI state on mount, then fetch from server
  useEffect(() => {
    // 1. Reset all UI state to initial values (clean slate)
    setActiveRunId(null);
    setQueueStatus(null);
    setShowResults(false);
    setCallResults([]);
    
    // 2. Invalidate any cached outbound queries to force refetch
    queryClient.invalidateQueries({ queryKey: ['/api/inbound_calls/counts'] });
    queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
    
    // 3. Fetch active run status from server (single source of truth)
    const checkActiveRun = async () => {
      try {
        const response = await http.get<{ active: boolean; run?: any }>('/api/outbound/bulk/active');
        if (response.active && response.run) {
          console.log('[InboundCallsPage] ✅ Active run found on mount:', response.run);
          setActiveRunId(response.run.run_id);
          setQueueStatus({
            queued: response.run.queued,
            in_progress: response.run.in_progress,
            completed: response.run.completed,
            failed: response.run.failed
          });
          // Start polling for this run
          startQueuePolling(response.run.run_id);
        } else {
          console.log('[InboundCallsPage] ✅ No active run found - UI clean');
        }
      } catch (error) {
        console.error('[InboundCallsPage] Failed to check active run:', error);
      }
    };
    
    checkActiveRun();
  }, []); // Run once on mount

  // Query for recent calls
  const [recentCallsPage, setRecentCallsPage] = useState(1);
  const [recentCallsSearch, setRecentCallsSearch] = useState('');
  const recentCallsPageSize = 50;
  
  const { data: recentCallsData, isLoading: recentCallsLoading, refetch: refetchRecentCalls } = useQuery({
    queryKey: ['/api/outbound/recent-calls', recentCallsPage, recentCallsSearch, activeRunId],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(recentCallsPage),
        page_size: String(recentCallsPageSize),
      });
      
      if (recentCallsSearch) {
        params.append('search', recentCallsSearch);
      }
      
      // Filter by active run if available
      if (activeRunId) {
        params.append('run_id', String(activeRunId));
      }

      return await http.get(`/api/outbound/recent-calls?${params.toString()}`);
    },
    enabled: activeTab === 'recent',
    retry: 1,
    refetchInterval: activeTab === 'recent' && activeRunId ? 5000 : false, // Auto-refresh when viewing active run
  });

  const recentCalls: RecentCall[] = recentCallsData?.items || [];
  const totalRecentCalls = recentCallsData?.total || 0;
  const totalRecentPages = Math.ceil(totalRecentCalls / recentCallsPageSize);

  const systemLeads = Array.isArray(leadsData?.leads) ? leadsData.leads : [];
  const activeLeads = Array.isArray(activeLeadsData?.leads) ? activeLeadsData.leads : [];
  const totalSystemLeads = leadsData?.total || 0;
  const totalActiveLeads = activeLeadsData?.total || 0;

  // Get the appropriate leads array based on active tab
  const leads = activeTab === 'system' ? systemLeads : activeLeads;

  // Mutations
  const startCallsMutation = useMutation({
    mutationFn: async (data: { lead_ids: number[]; project_id?: number }) => {
      // If more than 3 leads, use bulk enqueue, otherwise use direct start
      if (data.lead_ids.length > 3) {
        return await http.post<any>('/api/outbound/bulk-enqueue', {
          lead_ids: data.lead_ids,
          concurrency: 3,
          project_id: data.project_id
        });
      } else {
        return await http.post<any>('/api/inbound_calls/start', data);
      }
    },
    onSuccess: (data) => {
      // Check if this was a bulk queue (has run_id) or direct call (has calls)
      if (data.run_id) {
        // Bulk queue started
        setActiveRunId(data.run_id);
        setShowResults(true);
        setCallResults([{
          lead_id: 0,
          lead_name: 'תור שיחות',
          status: 'initiated',
          call_sid: `Queue started: ${data.queued} leads`
        }]);
        // Start polling for queue status
        startQueuePolling(data.run_id);
        // Switch to recent calls tab to show progress
        setActiveTab('recent');
      } else {
        // Direct calls started
        setCallResults(data.calls || []);
        setShowResults(true);
      }
      refetchCounts();
      refetchRecentCalls();
      queryClient.invalidateQueries({ queryKey: ['/api/calls'] });
    },
    onError: (error: any) => {
      const errorMessage = error?.message || error?.error || 'שגיאה בהפעלת השיחות';
      setCallResults([{ 
        lead_id: 0, 
        lead_name: 'שגיאה', 
        status: 'failed', 
        error: errorMessage 
      }]);
      setShowResults(true);
    },
  });



  const updateStatusMutation = useMutation({
    mutationFn: async ({ leadId, newStatus }: { leadId: number; newStatus: string }) => {
      console.log(`[InboundCallsPage] Updating lead ${leadId} status to ${newStatus}`);
      setUpdatingStatusLeadId(leadId);
      return await http.patch(`/api/leads/${leadId}/status`, { status: newStatus });
    },
    onMutate: async ({ leadId, newStatus }) => {
      // Cancel outgoing queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['/api/leads'] });
      
      // Snapshot previous values for rollback
      const previousSystemLeads = queryClient.getQueryData(['/api/leads', 'system', searchQuery, selectedStatuses]);
      const previousActiveLeads = queryClient.getQueryData(['/api/leads', 'active-outbound', searchQuery, selectedStatuses]);
      
      // Optimistically update system leads
      queryClient.setQueryData(['/api/leads', 'system', searchQuery, selectedStatuses], (old: any) => {
        if (!old?.leads) return old;
        return {
          ...old,
          leads: old.leads.map((lead: any) =>
            lead.id === leadId ? { ...lead, status: newStatus } : lead
          ),
        };
      });
      
      // Optimistically update active outbound leads
      queryClient.setQueryData(['/api/leads', 'active-outbound', searchQuery, selectedStatuses], (old: any) => {
        if (!old?.leads) return old;
        return {
          ...old,
          leads: old.leads.map((lead: any) =>
            lead.id === leadId ? { ...lead, status: newStatus } : lead
          ),
        };
      });
      
      return { previousSystemLeads, previousActiveLeads };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousSystemLeads) {
        queryClient.setQueryData(['/api/leads', 'system', searchQuery, selectedStatuses], context.previousSystemLeads);
      }
      if (context?.previousActiveLeads) {
        queryClient.setQueryData(['/api/leads', 'active-outbound', searchQuery, selectedStatuses], context.previousActiveLeads);
      }
      console.error(`[InboundCallsPage] ❌ Failed to update status for lead ${variables.leadId}:`, error);
      setUpdatingStatusLeadId(null);
    },
    onSuccess: (data, variables) => {
      console.log(`[InboundCallsPage] ✅ Status updated for lead ${variables.leadId}`);
      setUpdatingStatusLeadId(null);
      // Refetch to sync with server - invalidate all leads queries
      queryClient.invalidateQueries({ queryKey: ['/api/leads'] });
    },
  });

  // Handlers
  const handleToggleLead = (leadId: number) => {
    setSelectedLeads(prev => {
      const newSet = new Set(prev);
      const hadLead = newSet.has(leadId);
      if (hadLead) {
        newSet.delete(leadId);
        console.log(`[InboundCallsPage] ✅ Deselected lead ${leadId}. Total selected: ${newSet.size}`);
      } else {
        newSet.add(leadId);
        console.log(`[InboundCallsPage] ✅ Selected lead ${leadId}. Total selected: ${newSet.size}`);
      }
      return newSet;
    });
  };



  const handleStartCalls = () => {
    const ids = Array.from(selectedLeads);
    
    if (ids.length === 0) {
      alert('יש לבחור לפחות ליד אחד להפעלת שיחה');
      return;
    }
    
    console.log('🔵 Starting calls:', { activeTab, selectedIds: ids, count: ids.length });
    startCallsMutation.mutate({ lead_ids: ids });
  };
  
  const startQueuePolling = (runId: number) => {
    // Clear any existing poll interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    
    // Start new polling - check every 5 seconds (per requirement)
    pollIntervalRef.current = setInterval(async () => {
      try {
        const status = await http.get(`/api/outbound/runs/${runId}`);
        setQueueStatus({
          queued: status.queued,
          in_progress: status.in_progress,
          completed: status.completed,
          failed: status.failed
        });
        
        // Refetch recent calls to show new calls
        if (activeTab === 'recent') {
          refetchRecentCalls();
        }
        
        // Stop polling if queue is complete/stopped/cancelled
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled' || status.status === 'stopped') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setActiveRunId(null);
          setQueueStatus(null);
          refetchCounts();
          refetchRecentCalls();
        }
      } catch (error) {
        console.error('Queue status polling error:', error);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
    }, 5000); // Poll every 5 seconds (per requirement)
  };

  // Clean up polling interval and invalidate queries on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      // ✅ FIX: Clear outbound queries on unmount to prevent stale data
      queryClient.invalidateQueries({ queryKey: ['/api/inbound_calls/counts'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
    };
  }, []);

  const handleStopQueue = async () => {
    if (!activeRunId) return;
    
    try {
      // 🔥 FIX: Stop the queue and wait for confirmation
      await http.post(`/api/outbound/stop-queue`, { run_id: activeRunId });
      
      // Clear polling immediately
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      
      // 🔥 FIX: Reset UI state IMMEDIATELY (don't wait for server)
      setActiveRunId(null);
      setQueueStatus(null);
      
      // 🔥 FIX: Invalidate ALL outbound-related queries to force refetch
      queryClient.invalidateQueries({ queryKey: ['/api/inbound_calls/counts'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/recent-calls'] });
      
      // 🔥 FIX: Set counts to 0 immediately (optimistic update) to prevent blink
      queryClient.setQueryData(['/api/inbound_calls/counts'], (old: CallCounts | undefined) => {
        if (!old) return old;
        return {
          ...old,
          active_outbound: 0,
          // Keep max values unchanged
        };
      });
      
      // Refetch to sync with server
      refetchCounts();
      refetchRecentCalls();
    } catch (error) {
      console.error('Failed to stop queue:', error);
    }
  };

  const handleLeadSelect = (leadId: number, isShiftKey?: boolean) => {
    setSelectedLeads(prev => {
      const newSet = new Set(prev);
      const hadLead = newSet.has(leadId);
      if (hadLead) {
        newSet.delete(leadId);
        console.log(`[InboundCallsPage] ✅ Deselected lead ${leadId} (Kanban). Total selected: ${newSet.size}`);
      } else {
        newSet.add(leadId);
        console.log(`[InboundCallsPage] ✅ Selected lead ${leadId} (Kanban). Total selected: ${newSet.size}`);
      }
      return newSet;
    });
  };

  const handleSelectAll = (leadIds: number[]) => {
    // Select all provided lead IDs (no limit)
    setSelectedLeads(new Set(leadIds));
  };

  const handleSelectAllInStatuses = async () => {
    // Toggle: Select all leads matching the selected statuses (across pagination)
    // If all are already selected, deselect them instead
    if (selectedStatuses.length === 0) {
      alert('יש לבחור לפחות סטטוס אחד');
      return;
    }

    try {
      const response = await http.post('/api/leads/select-ids', {
        statuses: selectedStatuses,
        search: searchQuery,
        tab: activeTab,
        source: '', // Can be extended if needed
        direction: activeTab === 'active' ? 'inbound' : ''
      });

      const leadIds = response.lead_ids || [];
      
      // Check if all these leads are already selected
      const currentSelection = selectedLeads;
      const allSelected = leadIds.length > 0 && leadIds.every((id: number) => currentSelection.has(id));
      
      if (allSelected) {
        // Deselect all
        setSelectedLeads(new Set());
        console.log(`[InboundCallsPage] ✅ Deselected all leads from ${selectedStatuses.length} statuses`);
      } else {
        // Select all
        setSelectedLeads(new Set(leadIds));
        console.log(`[InboundCallsPage] ✅ Selected ${leadIds.length} leads from ${selectedStatuses.length} statuses`);
      }
    } catch (error) {
      console.error('[InboundCallsPage] ❌ Failed to select leads by status:', error);
      alert('שגיאה בבחירת לידים');
    }
  };

  // Helper to check if all leads in current filtered view are selected
  const areAllFilteredLeadsSelected = () => {
    const currentLeads = activeTab === 'active' ? activeLeads : systemLeads;
    const currentSelection = selectedLeads;
    
    if (currentLeads.length === 0) return false;
    
    return currentLeads.every((lead: Lead) => currentSelection.has(lead.id));
  };

  const handleClearSelection = () => {
    setSelectedLeads(new Set());
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    console.log(`[InboundCallsPage] handleStatusChange called: lead=${leadId}, newStatus=${newStatus}`);
    await updateStatusMutation.mutateAsync({ leadId, newStatus });
  };

  const handleLeadClick = (leadId: number) => {
    // Build URL with navigation context including current tab
    const params = new URLSearchParams();
    params.set('from', 'inbound_calls');
    params.set('tab', activeTab);  // Preserve which tab user is on (system/active/recent)
    
    // Add filter context if applicable
    if (searchQuery) params.set('filterSearch', searchQuery);
    if (selectedStatuses.length > 0) {
      params.set('filterStatuses', selectedStatuses.join(','));
    }
    
    navigate(`/app/leads/${leadId}?${params.toString()}`);
  };

  const filteredLeads = (Array.isArray(leads) ? leads : []).filter((lead: Lead) => {
    if (!lead) return false;
    if (!searchQuery) return lead.phone_e164;
    const query = searchQuery.toLowerCase();
    return (
      lead.phone_e164 && (
        (lead.full_name && lead.full_name.toLowerCase().includes(query)) ||
        lead.phone_e164.includes(query)
      )
    );
  });

  const canStartCalls = counts 
    ? (counts.active_outbound < counts.max_outbound && counts.active_total < counts.max_total)
    : true;

  const availableSlots = counts 
    ? Math.min(counts.max_outbound - counts.active_outbound, counts.max_total - counts.active_total)
    : DEFAULT_AVAILABLE_SLOTS;

  const statuses = statusesData || [];
  
  // Calculate status counts from currently loaded leads
  // Note: These are counts from current page only, real totals would require a separate API call
  const calculateStatusCounts = (leadsList: Lead[]) => {
    const counts: Record<string, number> = {};
    statuses.forEach(status => {
      counts[status.name] = 0;
    });
    leadsList.forEach(lead => {
      const status = lead.status?.toLowerCase() || 'new';
      if (counts[status] !== undefined) {
        counts[status]++;
      }
    });
    return counts;
  };

  // For now, show counts based on loaded leads
  // In a future enhancement, fetch real counts from backend
  const systemLeadsStatusCounts = calculateStatusCounts(systemLeads);
  const activeLeadsStatusCounts = calculateStatusCounts(activeLeads);
  
  // Defensive guard: Ensure selections are always Sets (fix for runtime errors)
  const safeSelectedLeads = selectedLeads instanceof Set ? selectedLeads : new Set(Array.isArray(selectedLeads) ? selectedLeads : []);
  const selectedLeadIdsSet = safeSelectedLeads; // Already a Set, no need to wrap again

  // Log on component mount
  useEffect(() => {
    console.log('[InboundCallsPage] 🎯 Component mounted');
    console.log('[InboundCallsPage] Default view mode:', viewMode);
  }, []);

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-full overflow-x-hidden" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <PhoneIncoming className="h-6 w-6 sm:h-8 sm:w-8 text-blue-600 flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">שיחות נכנסות</h1>
            <p className="text-xs sm:text-sm text-gray-500 line-clamp-1">לידים שמקורם משיחות נכנסות</p>
          </div>
        </div>
        
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 w-full sm:w-auto">
          {/* Stop Queue Button */}
          {activeRunId && queueStatus && (
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 w-full sm:w-auto">
              <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 sm:px-4 py-2 flex items-center gap-2 sm:gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600 flex-shrink-0" />
                  <div className="text-xs sm:text-sm min-w-0">
                    <div className="font-medium text-blue-900">תור פעיל</div>
                    <div className="text-blue-600 truncate">
                      בתור: {queueStatus.queued} | מתבצע: {queueStatus.in_progress} | הושלם: {queueStatus.completed}
                      {queueStatus.failed > 0 && ` | נכשל: ${queueStatus.failed}`}
                    </div>
                  </div>
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleStopQueue}
                className="flex items-center justify-center gap-2 min-h-[44px] w-full sm:w-auto"
                data-testid="button-stop-queue"
              >
                <StopCircle className="h-4 w-4" />
                עצור תור
              </Button>
            </div>
          )}
          
          {/* View Mode Toggle */}
          {(activeTab === 'system' || activeTab === 'active') && !showResults && (
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1 w-full sm:w-auto">
              <button
                onClick={() => {
                  console.log('[InboundCallsPage] Switching to Kanban view');
                  setViewMode('kanban');
                }}
                className={`flex-1 sm:flex-none px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5 ${
                  viewMode === 'kanban'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
                data-testid="button-kanban-view"
              >
                <LayoutGrid className="h-4 w-4" />
                <span className="hidden sm:inline">Kanban</span>
              </button>
              <button
                onClick={() => {
                  console.log('[InboundCallsPage] Switching to Table view');
                  setViewMode('table');
                }}
                className={`flex-1 sm:flex-none px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center justify-center gap-1.5 ${
                  viewMode === 'table'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
                data-testid="button-table-view"
              >
                <List className="h-4 w-4" />
                <span className="hidden sm:inline">רשימה</span>
              </button>
            </div>
          )}
          
          {counts && (
            <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-gray-600 bg-gray-100 px-3 sm:px-4 py-2 rounded-lg w-full sm:w-auto">
              <div className="flex items-center gap-1 sm:gap-2">
                <Phone className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="whitespace-nowrap">
                  שיחות פעילות: {counts.active_total}/{counts.max_total}
                </span>
              </div>
              <span className="hidden sm:inline mx-2">|</span>
              <div className="flex items-center gap-1 sm:gap-2">
                <PhoneIncoming className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="whitespace-nowrap">
                  יוצאות: {counts.active_outbound}/{counts.max_outbound}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Errors */}
      {(leadsError || countsError) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <XCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">
            שגיאה בטעינת נתונים. נסה לרענן את הדף.
          </span>
        </div>
      )}

      {!canStartCalls && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <span className="text-yellow-800">
            כרגע יש יותר מדי שיחות פעילות. המתן לסיום חלק מהשיחות ונסה שוב.
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex overflow-x-auto border-b border-gray-200 -mx-4 sm:mx-0 px-4 sm:px-0 scrollbar-hide">
        <button
          className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors whitespace-nowrap flex-shrink-0 ${
            activeTab === 'system'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('system');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-system-leads"
        >
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">לידים במערכת</span>
            <span className="sm:hidden">במערכת</span>
          </div>
        </button>
        <button
          className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors whitespace-nowrap flex-shrink-0 ${
            activeTab === 'active'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('active');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-active-outbound-leads"
        >
          <div className="flex items-center gap-2">
            <PhoneIncoming className="h-4 w-4" />
            <span className="hidden sm:inline">לידים לשיחות נכנסות</span>
            <span className="sm:hidden">נכנסות</span>
          </div>
        </button>
        <button
          className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors whitespace-nowrap flex-shrink-0 ${
            activeTab === 'recent'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('recent');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-recent-calls"
        >
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <span className="hidden sm:inline">שיחות אחרונות</span>
            <span className="sm:hidden">אחרונות</span>
            {totalRecentCalls > 0 && (
              <span className="bg-blue-100 text-blue-600 text-xs px-2 py-0.5 rounded-full">
                {totalRecentCalls}
              </span>
            )}
          </div>
        </button>
      </div>

      {/* Call Results */}
      {showResults && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">תוצאות השיחות</h3>
          <div className="space-y-2">
            {callResults.map((result) => (
              <div 
                key={result.lead_id}
                className={`flex items-center justify-between p-3 rounded-lg ${
                  result.status === 'initiated' ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  {result.status === 'initiated' ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  <span>{result.lead_name}</span>
                </div>
                <span className="text-sm text-gray-500">
                  {result.status === 'initiated' ? 'השיחה הופעלה' : result.error}
                </span>
              </div>
            ))}
          </div>
          <Button 
            variant="secondary"
            className="mt-4"
            onClick={() => {
              setShowResults(false);
              setSelectedLeads(new Set());
              setCallResults([]);
            }}
            data-testid="button-new-calls"
          >
            הפעל שיחות נוספות
          </Button>
        </Card>
      )}

      {/* System Leads Tab - For Browsing and Selection */}
      {!showResults && activeTab === 'system' && (
        <div className="space-y-4">
          {/* Sticky Action Bar */}
          <div className="sticky top-0 z-30 bg-white border-b border-gray-200 -mx-6 px-6 py-3 shadow-sm">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <div className="w-full sm:w-48">
                  <MultiStatusSelect
                    statuses={statuses}
                    selectedStatuses={selectedStatuses}
                    onChange={setSelectedStatuses}
                    placeholder="סנן לפי סטטוס"
                    data-testid="system-kanban-status-filter"
                  />
                </div>
                {selectedStatuses.length > 0 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSelectAllInStatuses}
                    className="whitespace-nowrap"
                    data-testid="button-select-all-in-statuses"
                  >
                    בחר הכל בסטטוסים ({selectedStatuses.length})
                  </Button>
                )}
                <div className="relative w-full sm:w-64">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="חיפוש לפי שם או טלפון..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pr-10 w-full"
                    data-testid="input-kanban-lead-search"
                  />
                </div>
              </div>
              <Button
                size="lg"
                disabled={
                  safeSelectedLeads.size === 0 ||
                  !canStartCalls ||
                  startCallsMutation.isPending
                }
                onClick={handleStartCalls}
                className="px-8 w-full sm:w-auto"
                data-testid="button-start-calls"
              >
                {startCallsMutation.isPending ? (
                  <>
                    <Loader2 className="h-5 w-5 ml-2 animate-spin" />
                    מתחיל שיחות...
                  </>
                ) : (
                  <>
                    <PlayCircle className="h-5 w-5 ml-2" />
                    הפעל {safeSelectedLeads.size} שיחות
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Kanban View */}
          {viewMode === 'kanban' && (
            <>

              {(leadsLoading || statusesLoading) ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
                </div>
              ) : statuses.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  לא נמצאו סטטוסים. יש להגדיר סטטוסים במערכת.
                </Card>
              ) : (
                <div className="min-h-[600px]">
                  <OutboundKanbanView
                    leads={filteredLeads}
                    statuses={statuses}
                    loading={leadsLoading}
                    selectedLeadIds={selectedLeadIdsSet}
                    onLeadSelect={handleLeadSelect}
                    onLeadClick={handleLeadClick}
                    onStatusChange={handleStatusChange}
                    onSelectAll={handleSelectAll}
                    onClearSelection={handleClearSelection}
                    updatingStatusLeadId={updatingStatusLeadId}
                    statusCounts={systemLeadsStatusCounts}
                    totalLeads={totalSystemLeads}
                  />
                </div>
              )}
            </>
          )}

          {/* Table View */}
          {viewMode === 'table' && (
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Users className="h-5 w-5" />
                לידים במערכת ({totalSystemLeads} כולל)
                {safeSelectedLeads.size > 0 && (
                  <span className="text-blue-600"> • {safeSelectedLeads.size} נבחרו</span>
                )}
              </h3>
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                {viewMode === 'table' && (
                  <div className="w-full sm:w-48">
                    <MultiStatusSelect
                      statuses={statuses}
                      selectedStatuses={selectedStatuses}
                      onChange={setSelectedStatuses}
                      placeholder="סנן לפי סטטוס"
                      data-testid="outbound-status-filter"
                    />
                  </div>
                )}
                <div className="relative w-full sm:w-64">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="חיפוש לפי שם או טלפון..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pr-10 w-full"
                    data-testid="input-lead-search"
                  />
                </div>
              </div>
            </div>

            {leadsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {searchQuery ? 'לא נמצאו לידים מתאימים' : 'אין לידים עם מספר טלפון'}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
                  {filteredLeads.map((lead: Lead) => {
                    const isSelected = safeSelectedLeads.has(lead.id);
                    
                    return (
                    <div
                      key={lead.id}
                      className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                        isSelected
                          ? 'bg-blue-50 border-blue-300'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      } cursor-pointer`}
                      data-testid={`lead-select-${lead.id}`}
                    >
                      <div 
                        className="flex-1"
                        onClick={() => handleLeadClick(lead.id)}
                      >
                        <div className="font-medium">{lead.full_name || 'ללא שם'}</div>
                        <div className="text-sm text-gray-500" dir="ltr">{lead.phone_e164}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {/* ✅ Editable status dropdown */}
                        <div onClick={(e) => e.stopPropagation()}>
                          <StatusDropdownWithWebhook
                            leadId={lead.id}
                            currentStatus={lead.status}
                            statuses={statuses}
                            onStatusChange={async (newStatus) => await handleStatusChange(lead.id, newStatus)}
                            source="inbound_calls"
                            hasWebhook={hasWebhook}
                            size="sm"
                          />
                        </div>
                        <div onClick={(e) => { e.stopPropagation(); handleToggleLead(lead.id); }}>
                          {isSelected ? (
                            <CheckCircle2 className="h-5 w-5 text-blue-600 cursor-pointer" />
                          ) : (
                            <div className="h-5 w-5 border-2 border-gray-300 rounded cursor-pointer"></div>
                          )}
                        </div>
                      </div>
                    </div>
                  );})}
                </div>

                {/* Pagination */}
                {totalSystemLeads > systemLeadsPageSize && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t">
                    <div className="text-sm text-gray-500">
                      עמוד {systemLeadsPage} מתוך {Math.ceil(totalSystemLeads / systemLeadsPageSize)}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSystemLeadsPage(p => Math.max(1, p - 1))}
                        disabled={systemLeadsPage === 1}
                        data-testid="button-prev-system-page"
                      >
                        הקודם
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSystemLeadsPage(p => Math.min(Math.ceil(totalSystemLeads / systemLeadsPageSize), p + 1))}
                        disabled={systemLeadsPage >= Math.ceil(totalSystemLeads / systemLeadsPageSize)}
                        data-testid="button-next-system-page"
                      >
                        הבא
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
          )}
        </div>
      )}

      {/* Active Outbound Leads Tab - For Managing Active Campaign */}
      {!showResults && activeTab === 'active' && (
        <div className="space-y-4">
          {/* Kanban View */}
          {viewMode === 'kanban' && (
            <>
              {/* Filters for Kanban View */}
              <Card className="p-4">
                <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                  <div className="w-full sm:w-48">
                    <MultiStatusSelect
                      statuses={statuses}
                      selectedStatuses={selectedStatuses}
                      onChange={setSelectedStatuses}
                      placeholder="סנן לפי סטטוס"
                      data-testid="active-kanban-status-filter"
                    />
                  </div>
                  <div className="relative w-full sm:w-64">
                    <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="חיפוש לפי שם או טלפון..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pr-10 w-full"
                      data-testid="input-active-kanban-lead-search"
                    />
                  </div>
                </div>
              </Card>

              {(activeLoading || statusesLoading) ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
                </div>
              ) : statuses.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  לא נמצאו סטטוסים. יש להגדיר סטטוסים במערכת.
                </Card>
              ) : (
                <div className="min-h-[600px]">
                  <OutboundKanbanView
                    leads={filteredLeads}
                    statuses={statuses}
                    loading={activeLoading}
                    selectedLeadIds={selectedLeadIdsSet}
                    onLeadSelect={handleLeadSelect}
                    onLeadClick={handleLeadClick}
                    onStatusChange={handleStatusChange}
                    onSelectAll={handleSelectAll}
                    onClearSelection={handleClearSelection}
                    updatingStatusLeadId={updatingStatusLeadId}
                    statusCounts={activeLeadsStatusCounts}
                    totalLeads={totalActiveLeads}
                  />
                </div>
              )}
            </>
          )}

          {/* Table View */}
          {viewMode === 'table' && (
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <PhoneIncoming className="h-5 w-5" />
                לידים פעילים לשיחות נכנסות ({totalActiveLeads} כולל)
              </h3>
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <div className="w-full sm:w-48">
                  <MultiStatusSelect
                    statuses={statuses}
                    selectedStatuses={selectedStatuses}
                    onChange={setSelectedStatuses}
                    placeholder="סנן לפי סטטוס"
                    data-testid="active-status-filter"
                  />
                </div>
                <div className="relative w-full sm:w-64">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="חיפוש לפי שם או טלפון..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pr-10 w-full"
                    data-testid="input-lead-search"
                  />
                </div>
              </div>
            </div>

            {activeLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {searchQuery ? 'לא נמצאו לידים מתאימים' : 'אין לידים פעילים לשיחות נכנסות'}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
                  {filteredLeads.map((lead: Lead) => (
                    <div
                      key={lead.id}
                      className="flex items-center justify-between p-3 rounded-lg border transition-colors bg-white border-gray-200 hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleLeadClick(lead.id)}
                      data-testid={`active-lead-${lead.id}`}
                    >
                      <div className="flex-1">
                        <div className="font-medium">{lead.full_name || 'ללא שם'}</div>
                        <div className="text-sm text-gray-500" dir="ltr">{lead.phone_e164}</div>
                      </div>
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        {/* ✅ Editable status dropdown */}
                        <StatusDropdownWithWebhook
                          leadId={lead.id}
                          currentStatus={lead.status}
                          statuses={statuses}
                          onStatusChange={async (newStatus) => await handleStatusChange(lead.id, newStatus)}
                          source="inbound_calls"
                          hasWebhook={hasWebhook}
                          size="sm"
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {totalActiveLeads > systemLeadsPageSize && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t">
                    <div className="text-sm text-gray-500">
                      עמוד {activeLeadsPage} מתוך {Math.ceil(totalActiveLeads / systemLeadsPageSize)}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setActiveLeadsPage(p => Math.max(1, p - 1))}
                        disabled={activeLeadsPage === 1}
                        data-testid="button-prev-active-page"
                      >
                        הקודם
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setActiveLeadsPage(p => Math.min(Math.ceil(totalActiveLeads / systemLeadsPageSize), p + 1))}
                        disabled={activeLeadsPage >= Math.ceil(totalActiveLeads / systemLeadsPageSize)}
                        data-testid="button-next-active-page"
                      >
                        הבא
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
          )}

          <p className="text-sm text-gray-500 text-center">
            כל הלידים שנבחרו לקמפיין שיחות נכנסות מוצגים כאן
          </p>
        </div>
      )}



      {/* Recent Calls Tab */}
      {!showResults && activeTab === 'recent' && (
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Clock className="h-5 w-5" />
                שיחות אחרונות ({totalRecentCalls})
              </h3>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto">
                <div className="relative w-full sm:w-48">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="חיפוש..."
                    value={recentCallsSearch}
                    onChange={(e) => {
                      setRecentCallsSearch(e.target.value);
                      setRecentCallsPage(1);
                    }}
                    className="pr-10 w-full"
                    data-testid="input-recent-calls-search"
                  />
                </div>
                {activeRunId && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setActiveRunId(null);
                      refetchRecentCalls();
                    }}
                    data-testid="button-show-all-calls"
                    className="w-full sm:w-auto"
                  >
                    הצג את כל השיחות
                  </Button>
                )}
              </div>
            </div>

            {recentCallsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : recentCalls.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {recentCallsSearch ? 'לא נמצאו שיחות מתאימות' : 'עדיין לא בוצעו שיחות נכנסות'}
              </div>
            ) : (
              <>
                {/* Desktop Table View - Hidden on mobile */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-right py-3 px-2 font-medium">זמן</th>
                        <th className="text-right py-3 px-2 font-medium">טלפון</th>
                        <th className="text-right py-3 px-2 font-medium">ליד</th>
                        <th className="text-right py-3 px-2 font-medium">סטטוס ליד</th>
                        <th className="text-right py-3 px-2 font-medium">סטטוס שיחה</th>
                        <th className="text-right py-3 px-2 font-medium">משך</th>
                        <th className="text-right py-3 px-2 font-medium">הקלטה</th>
                        <th className="text-right py-3 px-2 font-medium">סיכום</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentCalls.map((call) => {
                        const duration = call.duration 
                          ? `${Math.floor(call.duration / 60)}:${(call.duration % 60).toString().padStart(2, '0')}`
                          : '-';
                        
                        return (
                          <tr 
                            key={call.call_sid} 
                            className="border-b hover:bg-gray-50 cursor-pointer"
                            onClick={() => {
                              if (call.lead_id) {
                                handleLeadClick(call.lead_id);
                              }
                            }}
                            data-testid={`recent-call-row-${call.call_sid}`}
                          >
                            <td className="py-3 px-2">
                              {call.started_at 
                                ? formatDate(call.started_at)
                                : '-'}
                            </td>
                            <td className="py-3 px-2" dir="ltr">{call.to_number || '-'}</td>
                            <td className="py-3 px-2 font-medium">
                              {call.lead_name || call.lead_id ? (
                                <span className="text-blue-600 hover:underline">
                                  {call.lead_name || `ליד #${call.lead_id}`}
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td className="py-3 px-2" onClick={(e) => e.stopPropagation()}>
                              {call.lead_id && call.lead_status ? (
                                <StatusDropdownWithWebhook
                                  leadId={call.lead_id}
                                  currentStatus={call.lead_status}
                                  statuses={statuses}
                                  onStatusChange={async (newStatus) => await handleStatusChange(call.lead_id, newStatus)}
                                  source="recent_calls_tab"
                                  hasWebhook={hasWebhook}
                                  size="sm"
                                />
                              ) : (
                                <span className="text-gray-400 text-xs">אין ליד</span>
                              )}
                            </td>
                            <td className="py-3 px-2">
                              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                call.status === 'completed' || call.status === 'answered'
                                  ? 'bg-green-100 text-green-800'
                                  : call.status === 'no-answer' || call.status === 'busy'
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : call.status === 'failed'
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-gray-100 text-gray-800'
                              }`}>
                                {call.status}
                              </span>
                            </td>
                            <td className="py-3 px-2">{duration}</td>
                            <td className="py-3 px-2" onClick={(e) => e.stopPropagation()}>
                              {call.recording_url ? (
                                <div className="space-y-2">
                                  <a
                                    href={`/api/calls/${call.call_sid}/download`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-600 hover:underline flex items-center gap-1"
                                  >
                                    <Download className="h-4 w-4" />
                                    הורד
                                  </a>
                                  <AudioPlayer src={`/api/recordings/${call.call_sid}/stream`} />
                                </div>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td className="py-3 px-2 max-w-xs">
                              {call.summary ? (
                                <div className="text-gray-600 truncate" title={call.summary}>
                                  {call.summary}
                                </div>
                              ) : call.transcript ? (
                                <div className="text-gray-500 text-xs truncate" title={call.transcript}>
                                  {call.transcript}
                                </div>
                              ) : (
                                '-'
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Card View - Visible only on mobile */}
                <div className="md:hidden space-y-3">
                  {recentCalls.map((call) => {
                    const duration = call.duration 
                      ? `${Math.floor(call.duration / 60)}:${(call.duration % 60).toString().padStart(2, '0')}`
                      : '-';
                    
                    const getCallStatusColor = (status: string) => {
                      if (status === 'completed' || status === 'answered') return 'bg-green-100 text-green-800';
                      if (status === 'no-answer' || status === 'busy') return 'bg-yellow-100 text-yellow-800';
                      if (status === 'failed') return 'bg-red-100 text-red-800';
                      return 'bg-gray-100 text-gray-800';
                    };

                    const getCallStatusLabel = (status: string) => {
                      if (status === 'completed' || status === 'answered') return 'נענה';
                      if (status === 'no-answer') return 'לא נענה';
                      if (status === 'busy') return 'תפוס';
                      if (status === 'failed') return 'נכשל';
                      return status;
                    };
                    
                    return (
                      <div
                        key={call.call_sid}
                        className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                        data-testid={`recent-call-card-${call.call_sid}`}
                      >
                        {/* Header: Phone/Name + Call Status */}
                        <div 
                          className="flex items-start justify-between gap-3 mb-3 cursor-pointer"
                          onClick={() => {
                            if (call.lead_id) {
                              handleLeadClick(call.lead_id);
                            }
                          }}
                        >
                          <div className="flex-1 min-w-0">
                            <p className="text-base font-medium text-gray-900 truncate">
                              {call.lead_name || `ליד #${call.lead_id}` || 'לקוח אלמוני'}
                            </p>
                            <p className="text-sm text-gray-500 truncate" dir="ltr">{call.to_number || '-'}</p>
                          </div>
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${getCallStatusColor(call.status)}`}>
                            {getCallStatusLabel(call.status)}
                          </span>
                        </div>

                        {/* Details Row: Duration + Time */}
                        <div className="flex items-center justify-between text-sm text-gray-600 mb-3">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-gray-400" />
                            <span className="font-medium">{duration}</span>
                          </div>
                          <span className="text-xs text-gray-400">
                            {call.started_at ? formatDate(call.started_at) : '-'}
                          </span>
                        </div>

                        {/* Lead Status - if available */}
                        {call.lead_id && call.lead_status && (
                          <div className="mb-3 pb-3 border-b border-gray-100" onClick={(e) => e.stopPropagation()}>
                            <div className="text-xs text-gray-500 mb-1">סטטוס ליד</div>
                            <StatusDropdownWithWebhook
                              leadId={call.lead_id}
                              currentStatus={call.lead_status}
                              statuses={statuses}
                              onStatusChange={async (newStatus) => await handleStatusChange(call.lead_id!, newStatus)}
                              source="recent_calls_tab"
                              hasWebhook={hasWebhook}
                              size="sm"
                            />
                          </div>
                        )}

                        {/* Recording + Summary */}
                        {(call.recording_url || call.summary || call.transcript) && (
                          <div className="space-y-2">
                            {call.recording_url && (
                              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                <a
                                  href={`/api/calls/${call.call_sid}/download`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 active:bg-blue-200 transition-colors min-h-[44px]"
                                >
                                  <Download className="h-4 w-4" />
                                  הורד הקלטה
                                </a>
                              </div>
                            )}
                            {(call.summary || call.transcript) && (
                              <div className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg">
                                <div className="font-medium text-gray-700 mb-1">סיכום:</div>
                                <p className="line-clamp-2">
                                  {call.summary || call.transcript || '-'}
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Pagination */}
                {totalRecentPages > 1 && (
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
                    <div className="text-sm text-gray-500 order-2 sm:order-1">
                      עמוד {recentCallsPage} מתוך {totalRecentPages}
                    </div>
                    <div className="flex gap-2 w-full sm:w-auto order-1 sm:order-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRecentCallsPage(p => Math.max(1, p - 1))}
                        disabled={recentCallsPage === 1}
                        data-testid="button-prev-recent-page"
                        className="flex-1 sm:flex-none min-h-[44px]"
                      >
                        הקודם
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRecentCallsPage(p => Math.min(totalRecentPages, p + 1))}
                        disabled={recentCallsPage === totalRecentPages}
                        data-testid="button-next-recent-page"
                        className="flex-1 sm:flex-none min-h-[44px]"
                      >
                        הבא
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      )}


    </div>
  );
}

export default InboundCallsPage;
