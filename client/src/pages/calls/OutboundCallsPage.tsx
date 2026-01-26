import React, { useState, useRef, ChangeEvent, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Phone, 
  PhoneOutgoing, 
  Users, 
  Loader2, 
  AlertTriangle, 
  CheckCircle2,
  XCircle,
  Search,
  PlayCircle,
  Upload,
  Trash2,
  FileSpreadsheet,
  Download,
  LayoutGrid,
  List,
  StopCircle,
  Clock,
  FolderOpen
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
import { callsService } from '../../services/calls';
import { QueueStatusCard } from './components/QueueStatusCard';
import { OutboundKanbanView } from './components/OutboundKanbanView';
import { ProjectsListView } from './components/ProjectsListView';
import { ProjectDetailView } from './components/ProjectDetailView';
import { CreateProjectModal } from './components/CreateProjectModal';
import { Lead } from '../Leads/types';  // ✅ Use shared Lead type
import type { LeadStatusConfig } from '../../shared/types/status';

// Type alias for backward compatibility
type LeadStatus = LeadStatusConfig;

interface ImportedLead {
  id: number;
  name: string;
  phone: string;
  status: string;
  notes: string | null;
  list_id: number | null;
  created_at: string | null;
}

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

interface ImportResult {
  success: boolean;
  list_id: number;
  list_name: string;
  imported_count: number;
  skipped_count: number;
  errors: string[];
}

interface ImportedLeadsResponse {
  total: number;
  limit: number;
  current_count: number;
  page: number;
  page_size: number;
  items: ImportedLead[];
}

interface ImportList {
  id: number;
  name: string;
  file_name: string | null;
  total_leads: number;
  current_leads: number;
  created_at: string | null;
}

type TabType = 'system' | 'active' | 'imported' | 'recent' | 'projects';

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

interface Project {
  id: number;
  name: string;
  description?: string;
  status: 'draft' | 'active' | 'completed' | 'paused';
  created_at: string;
  total_leads: number;
  stats?: {
    total_calls: number;
    answered: number;
    no_answer: number;
    failed: number;
    total_duration: number;
  } | null;
}

export function OutboundCallsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Tab and view state
  const [activeTab, setActiveTab] = useState<TabType>('system');
  const [viewMode, setViewMode] = useState<ViewMode>('kanban'); // Default to Kanban
  const [hasWebhook, setHasWebhook] = useState(false);
  
  // ✅ Sync tab with URL on mount
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const tabParam = sp.get('tab') as TabType | null;
    if (tabParam && ['system', 'active', 'imported', 'recent', 'projects'].includes(tabParam)) {
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
  
  // Imported leads state
  const [selectedImportedLeads, setSelectedImportedLeads] = useState<Set<number>>(new Set());
  const [importedSearchQuery, setImportedSearchQuery] = useState('');
  const [selectedImportListId, setSelectedImportListId] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [showImportResult, setShowImportResult] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLeadId, setDeleteLeadId] = useState<number | null>(null);
  const [updatingStatusLeadId, setUpdatingStatusLeadId] = useState<number | null>(null);
  const pageSize = 50;
  
  // Queue state
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [queueJobStatus, setQueueJobStatus] = useState<{
    job_id: number;
    status: string;
    total: number;
    processed: number;
    success: number;
    failed: number;
    in_progress: number;
    queued: number;
    progress_pct: number;
    can_cancel: boolean;
    cancel_requested: boolean;
  } | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null); // Store interval ID

  // Support deep-link from Lead page tiles: /app/outbound-calls?phone=... or ?leadId=...
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
    queryKey: ['/api/outbound_calls/counts'],
    refetchInterval: activeRunId ? 10000 : false, // Only poll when queue is running
    enabled: true, // Always enabled for initial fetch
    retry: 1,
    staleTime: 30000, // 🔥 FIX: 30s cache instead of 0 - reduce load on API
    gcTime: 60000, // 🔥 FIX: Keep in cache for 1 minute (renamed from cacheTime in v5)
  });

  // Fetch lead statuses for both Kanban and Table views
  const { data: statusesData, isLoading: statusesLoading } = useQuery<LeadStatus[]>({
    queryKey: ['/api/lead-statuses'],
    enabled: true, // ✅ Always load statuses for both view modes
    retry: 1,
  });

  useEffect(() => {
    if (statusesData) {
      console.log('[OutboundCallsPage] ✅ Lead statuses loaded:', statusesData);
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
        direction: 'outbound',
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
      console.log('[OutboundCallsPage] ✅ System leads loaded:', leadsData.leads.length, 'leads');
    }
  }, [leadsData]);

  useEffect(() => {
    if (activeLeadsData?.leads) {
      console.log('[OutboundCallsPage] ✅ Active outbound leads loaded:', activeLeadsData.leads.length, 'leads');
    }
  }, [activeLeadsData]);

  // 🔥 REQUIREMENT FIX: Reset UI state and fetch fresh from server
  // ✅ FIX: Clear all outbound UI state on mount, then fetch from server
  useEffect(() => {
    // 1. Reset all UI state to initial values (clean slate)
    setActiveRunId(null);
    setQueueJobStatus(null);
    setShowResults(false);
    setCallResults([]);
    
    // 2. Invalidate any cached outbound queries to force refetch
    queryClient.invalidateQueries({ queryKey: ['/api/outbound_calls/counts'] });
    queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
    
    // 3. Fetch active run status from server (single source of truth)
    const checkActiveRun = async () => {
      try {
        const activeQueue = await callsService.getActiveQueue();
        if (activeQueue) {
          console.log('[OutboundCallsPage] ✅ Active queue found on mount:', activeQueue);
          setActiveRunId(activeQueue.job_id);
          setQueueJobStatus(activeQueue);
          // Start polling for this run
          startQueuePolling(activeQueue.job_id);
        } else {
          console.log('[OutboundCallsPage] ✅ No active queue found - UI clean');
        }
      } catch (error) {
        console.error('[OutboundCallsPage] Failed to check active queue:', error);
      }
    };
    
    checkActiveRun();
  }, []); // Run once on mount

  const { data: importedLeadsData, isLoading: importedLoading, refetch: refetchImported } = useQuery<ImportedLeadsResponse>({
    queryKey: ['/api/outbound/import-leads', currentPage, importedSearchQuery, selectedStatuses, selectedImportListId],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(currentPage),
        page_size: String(pageSize),
      });
      
      if (importedSearchQuery) {
        params.append('search', importedSearchQuery);
      }

      // ✅ Add multi-status filter for imported leads
      if (selectedStatuses.length > 0) {
        selectedStatuses.forEach(status => {
          params.append('statuses[]', status);
        });
      }

      // ✅ Add import list filter
      if (selectedImportListId) {
        params.append('list_id', String(selectedImportListId));
      }

      return await http.get(`/api/outbound/import-leads?${params.toString()}`);
    },
    enabled: activeTab === 'imported',
    retry: 1,
  });

  // Query for import lists
  const { data: importListsData, isLoading: importListsLoading } = useQuery<{ lists: ImportList[] }>({
    queryKey: ['/api/outbound/import-lists'],
    queryFn: async () => {
      return await http.get('/api/outbound/import-lists');
    },
    enabled: activeTab === 'imported',
    retry: 1,
  });

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

  // Query for projects
  const [projectsPage, setProjectsPage] = useState(1);
  const [projectsSearch, setProjectsSearch] = useState('');
  const [projectsStatusFilter, setProjectsStatusFilter] = useState('');
  const projectsPageSize = 50;
  
  const { data: projectsData, isLoading: projectsLoading, error: projectsError, refetch: refetchProjects } = useQuery({
    queryKey: ['/api/projects', projectsPage, projectsSearch, projectsStatusFilter],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(projectsPage),
        page_size: String(projectsPageSize),
      });
      
      if (projectsSearch) {
        params.append('search', projectsSearch);
      }
      
      if (projectsStatusFilter) {
        params.append('status', projectsStatusFilter);
      }

      return await http.get(`/api/projects?${params.toString()}`);
    },
    enabled: activeTab === 'projects',
    retry: 1,
  });

  const projects: Project[] = Array.isArray(projectsData?.items) ? projectsData.items : [];
  const totalProjects = projectsData?.total || 0;
  const totalProjectsPages = Math.ceil(totalProjects / projectsPageSize);

  // Project view state
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [showCreateProject, setShowCreateProject] = useState(false);

  const systemLeads = Array.isArray(leadsData?.leads) ? leadsData.leads : [];
  const activeLeads = Array.isArray(activeLeadsData?.leads) ? activeLeadsData.leads : [];
  const importedLeads = importedLeadsData?.items || [];
  const totalImported = importedLeadsData?.total || 0;
  const importLimit = importedLeadsData?.limit || 5000;
  const totalSystemLeads = leadsData?.total || 0;
  const totalActiveLeads = activeLeadsData?.total || 0;

  // Convert imported leads to Lead format for display in Kanban/List views
  // ✅ Robust conversion that handles all field mappings properly
  // Note: This is for DISPLAY ONLY in UI components. tenant_id is not used in display contexts.
  const importedLeadsAsLeads: Lead[] = importedLeads.map((imported) => ({
    id: imported.id,
    tenant_id: 0,  // Display-only conversion - not used by UI components
    full_name: imported.name,
    name: imported.name,
    first_name: imported.name.split(' ')[0] || '',
    last_name: imported.name.split(' ').slice(1).join(' ') || '',
    phone_e164: imported.phone,
    phone: imported.phone,
    display_phone: imported.phone,
    status: imported.status || 'new',
    source: 'phone' as const,  // Imported leads are phone leads
    notes: imported.notes ?? undefined,  // ✅ Convert null to undefined for type safety
    created_at: imported.created_at || new Date().toISOString(),
    updated_at: imported.created_at || new Date().toISOString(),
    last_contact_at: undefined,
  }));

  // Get the appropriate leads array based on active tab
  const leads = activeTab === 'system' ? systemLeads : activeTab === 'active' ? activeLeads : importedLeadsAsLeads;

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
        return await http.post<any>('/api/outbound_calls/start', data);
      }
    },
    onSuccess: (data) => {
      // Check if this was a bulk queue (has run_id) or direct call (has calls)
      if (data.run_id) {
        // Bulk queue started
        setActiveRunId(data.run_id);
        // Set initial queue status from response
        setQueueJobStatus({
          job_id: data.run_id,
          status: 'running',
          total: data.queued || 0,
          processed: 0,
          success: 0,
          failed: 0,
          in_progress: 0,
          queued: data.queued || 0,
          progress_pct: 0,
          can_cancel: true,
          cancel_requested: false
        });
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

  const importMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await fetch('/api/outbound/import-leads', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'שגיאה בייבוא');
      return data as ImportResult;
    },
    onSuccess: (data) => {
      setImportResult(data);
      setShowImportResult(true);
      refetchImported();
    },
    onError: (error: any) => {
      setImportResult({
        success: false,
        list_id: 0,
        list_name: '',
        imported_count: 0,
        skipped_count: 0,
        errors: [error.message || 'שגיאה בייבוא הקובץ']
      });
      setShowImportResult(true);
    },
  });

  const deleteLeadMutation = useMutation({
    mutationFn: async (leadId: number) => {
      return await http.delete(`/api/outbound/import-leads/${leadId}`);
    },
    onSuccess: () => {
      refetchImported();
      setShowDeleteConfirm(false);
      setDeleteLeadId(null);
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async (leadIds: number[]) => {
      return await http.post('/api/outbound/import-leads/bulk-delete', { lead_ids: leadIds });
    },
    onSuccess: () => {
      refetchImported();
      setSelectedImportedLeads(new Set());
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ leadId, newStatus }: { leadId: number; newStatus: string }) => {
      console.log(`[OutboundCallsPage] Updating lead ${leadId} status to ${newStatus}`);
      setUpdatingStatusLeadId(leadId);
      return await http.patch(`/api/leads/${leadId}/status`, { status: newStatus });
    },
    onMutate: async ({ leadId, newStatus }) => {
      // Cancel outgoing queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['/api/leads'] });
      await queryClient.cancelQueries({ queryKey: ['/api/outbound/import-leads'] });
      
      // Snapshot previous values for rollback
      const previousSystemLeads = queryClient.getQueryData(['/api/leads', 'system', searchQuery, selectedStatuses]);
      const previousActiveLeads = queryClient.getQueryData(['/api/leads', 'active-outbound', searchQuery, selectedStatuses]);
      const previousImportedLeads = queryClient.getQueryData(['/api/outbound/import-leads', currentPage, importedSearchQuery]);
      
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
      
      // Optimistically update imported leads
      queryClient.setQueryData(['/api/outbound/import-leads', currentPage, importedSearchQuery], (old: any) => {
        if (!old?.items) return old;
        return {
          ...old,
          items: old.items.map((lead: any) =>
            lead.id === leadId ? { ...lead, status: newStatus } : lead
          ),
        };
      });
      
      return { previousSystemLeads, previousActiveLeads, previousImportedLeads };
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousSystemLeads) {
        queryClient.setQueryData(['/api/leads', 'system', searchQuery, selectedStatuses], context.previousSystemLeads);
      }
      if (context?.previousActiveLeads) {
        queryClient.setQueryData(['/api/leads', 'active-outbound', searchQuery, selectedStatuses], context.previousActiveLeads);
      }
      if (context?.previousImportedLeads) {
        queryClient.setQueryData(['/api/outbound/import-leads', currentPage, importedSearchQuery], context.previousImportedLeads);
      }
      console.error(`[OutboundCallsPage] ❌ Failed to update status for lead ${variables.leadId}:`, error);
      setUpdatingStatusLeadId(null);
    },
    onSuccess: (data, variables) => {
      console.log(`[OutboundCallsPage] ✅ Status updated for lead ${variables.leadId}`);
      setUpdatingStatusLeadId(null);
      // Refetch to sync with server - invalidate all leads queries
      queryClient.invalidateQueries({ queryKey: ['/api/leads'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/import-leads'] });
    },
  });

  // Handlers
  const handleToggleLead = (leadId: number) => {
    setSelectedLeads(prev => {
      const newSet = new Set(prev);
      const hadLead = newSet.has(leadId);
      if (hadLead) {
        newSet.delete(leadId);
        console.log(`[OutboundCallsPage] ✅ Deselected lead ${leadId}. Total selected: ${newSet.size}`);
      } else {
        newSet.add(leadId);
        console.log(`[OutboundCallsPage] ✅ Selected lead ${leadId}. Total selected: ${newSet.size}`);
      }
      return newSet;
    });
  };

  const handleToggleImportedLead = (leadId: number) => {
    setSelectedImportedLeads(prev => {
      const newSet = new Set(prev);
      const hadLead = newSet.has(leadId);
      if (hadLead) {
        newSet.delete(leadId);
        console.log(`[OutboundCallsPage] ✅ Deselected imported lead ${leadId}. Total selected: ${newSet.size}`);
      } else {
        newSet.add(leadId);
        console.log(`[OutboundCallsPage] ✅ Selected imported lead ${leadId}. Total selected: ${newSet.size}`);
      }
      return newSet;
    });
  };

  const handleStartCalls = () => {
    // ✅ FIX: Check correct tab names - 'system' for CRM leads, 'imported' for imported leads
    const ids = (activeTab === 'system' || activeTab === 'active') 
      ? Array.from(selectedLeads)
      : Array.from(selectedImportedLeads);
    
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
        const status = await callsService.getQueueStatus(runId);
        setQueueJobStatus(status);
        
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
          setQueueJobStatus(null);
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
      queryClient.invalidateQueries({ queryKey: ['/api/outbound_calls/counts'] });
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
      setQueueJobStatus(null);
      
      // 🔥 FIX: Invalidate ALL outbound-related queries to force refetch
      queryClient.invalidateQueries({ queryKey: ['/api/outbound_calls/counts'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
      queryClient.invalidateQueries({ queryKey: ['/api/outbound/recent-calls'] });
      
      // 🔥 FIX: Set counts to 0 immediately (optimistic update) to prevent blink
      queryClient.setQueryData(['/api/outbound_calls/counts'], (old: CallCounts | undefined) => {
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

  const handleCancelQueue = async () => {
    if (!queueJobStatus) return;
    
    try {
      await callsService.cancelQueue(queueJobStatus.job_id);
      // Update local state to show canceling
      setQueueJobStatus(prev => prev ? { ...prev, cancel_requested: true } : null);
    } catch (error) {
      console.error('Failed to cancel queue:', error);
    }
  };

  const handleFileUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    importMutation.mutate(formData);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDeleteLead = (leadId: number) => {
    setDeleteLeadId(leadId);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    if (deleteLeadId) {
      deleteLeadMutation.mutate(deleteLeadId);
    }
  };

  const handleBulkDelete = () => {
    if (selectedImportedLeads.size > 0) {
      bulkDeleteMutation.mutate(Array.from(selectedImportedLeads));
    }
  };
  
  const handleSelectAllImported = () => {
    if (selectedImportedLeads.size === importedLeads.length && importedLeads.length > 0) {
      // Deselect all
      setSelectedImportedLeads(new Set());
    } else {
      // Select all leads on current page
      const allIds = importedLeads.map(l => l.id);
      setSelectedImportedLeads(new Set(allIds));
    }
  };

  const handleLeadSelect = (leadId: number, isShiftKey?: boolean) => {
    setSelectedLeads(prev => {
      const newSet = new Set(prev);
      const hadLead = newSet.has(leadId);
      if (hadLead) {
        newSet.delete(leadId);
        console.log(`[OutboundCallsPage] ✅ Deselected lead ${leadId} (Kanban). Total selected: ${newSet.size}`);
      } else {
        newSet.add(leadId);
        console.log(`[OutboundCallsPage] ✅ Selected lead ${leadId} (Kanban). Total selected: ${newSet.size}`);
      }
      return newSet;
    });
  };

  const handleSelectAll = (leadIds: number[]) => {
    // Select all provided lead IDs (no limit)
    // Check which tab we're on to update the correct state
    if (activeTab === 'imported') {
      setSelectedImportedLeads(new Set(leadIds));
    } else {
      setSelectedLeads(new Set(leadIds));
    }
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
        search: activeTab === 'imported' ? importedSearchQuery : searchQuery,
        tab: activeTab,
        source: '', // Can be extended if needed
        direction: activeTab === 'active' ? 'outbound' : '',
        list_id: activeTab === 'imported' ? selectedImportListId : undefined
      });

      const leadIds = response.lead_ids || [];
      
      // Check if all these leads are already selected
      const currentSelection = activeTab === 'imported' ? selectedImportedLeads : selectedLeads;
      const allSelected = leadIds.length > 0 && leadIds.every((id: number) => currentSelection.has(id));
      
      if (allSelected) {
        // Deselect all
        if (activeTab === 'imported') {
          setSelectedImportedLeads(new Set());
        } else {
          setSelectedLeads(new Set());
        }
        console.log(`[OutboundCallsPage] ✅ Deselected all leads from ${selectedStatuses.length} statuses`);
      } else {
        // Select all
        if (activeTab === 'imported') {
          setSelectedImportedLeads(new Set(leadIds));
        } else {
          setSelectedLeads(new Set(leadIds));
        }
        console.log(`[OutboundCallsPage] ✅ Selected ${leadIds.length} leads from ${selectedStatuses.length} statuses`);
      }
    } catch (error) {
      console.error('[OutboundCallsPage] ❌ Failed to select leads by status:', error);
      alert('שגיאה בבחירת לידים');
    }
  };

  // Helper to check if all leads in current filtered view are selected
  const areAllFilteredLeadsSelected = () => {
    const currentLeads = activeTab === 'imported' ? importedLeadsAsLeads : (activeTab === 'active' ? activeLeads : systemLeads);
    const currentSelection = activeTab === 'imported' ? selectedImportedLeads : selectedLeads;
    
    if (currentLeads.length === 0) return false;
    
    return currentLeads.every((lead: Lead) => currentSelection.has(lead.id));
  };

  const handleClearSelection = () => {
    if (activeTab === 'imported') {
      setSelectedImportedLeads(new Set());
    } else {
      setSelectedLeads(new Set());
    }
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    console.log(`[OutboundCallsPage] handleStatusChange called: lead=${leadId}, newStatus=${newStatus}`);
    await updateStatusMutation.mutateAsync({ leadId, newStatus });
  };

  const handleLeadClick = (leadId: number) => {
    // Build URL with navigation context including current tab
    const params = new URLSearchParams();
    params.set('from', 'outbound_calls');
    params.set('tab', activeTab);  // Preserve which tab user is on (system/active/imported/recent)
    
    // Add filter context if applicable
    if (searchQuery) params.set('filterSearch', searchQuery);
    if (selectedStatuses.length > 0) {
      params.set('filterStatuses', selectedStatuses.join(','));
    }
    // Add page context for imported tab
    if (activeTab === 'imported' && currentPage > 1) {
      params.set('page', currentPage.toString());
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

  const totalPages = Math.ceil(totalImported / pageSize);

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
  const importedLeadsStatusCounts = calculateStatusCounts(importedLeadsAsLeads);
  
  // Defensive guard: Ensure selections are always Sets (fix for runtime errors)
  const safeSelectedLeads = selectedLeads instanceof Set ? selectedLeads : new Set(Array.isArray(selectedLeads) ? selectedLeads : []);
  const safeSelectedImportedLeads = selectedImportedLeads instanceof Set ? selectedImportedLeads : new Set(Array.isArray(selectedImportedLeads) ? selectedImportedLeads : []);
  const selectedLeadIdsSet = safeSelectedLeads; // Already a Set, no need to wrap again

  // Log on component mount
  useEffect(() => {
    console.log('[OutboundCallsPage] 🎯 Component mounted');
    console.log('[OutboundCallsPage] Default view mode:', viewMode);
  }, []);

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-full overflow-x-hidden" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <PhoneOutgoing className="h-6 w-6 sm:h-8 sm:w-8 text-blue-600 flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">שיחות יוצאות</h1>
            <p className="text-xs sm:text-sm text-gray-500 line-clamp-1">לידים שמקורם משיחות יוצאות + ניהול רשימות ייבוא</p>
          </div>
        </div>
        
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 w-full sm:w-auto">
          {/* View Mode Toggle */}
          {(activeTab === 'system' || activeTab === 'active' || activeTab === 'imported') && !showResults && (
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1 w-full sm:w-auto">
              <button
                onClick={() => {
                  console.log('[OutboundCallsPage] Switching to Kanban view');
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
                  console.log('[OutboundCallsPage] Switching to Table view');
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
                <PhoneOutgoing className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="whitespace-nowrap">
                  יוצאות: {counts.active_outbound}/{counts.max_outbound}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Queue Status Card */}
      {queueJobStatus && (
        <QueueStatusCard
          jobId={queueJobStatus.job_id}
          status={queueJobStatus.status}
          total={queueJobStatus.total}
          processed={queueJobStatus.processed}
          success={queueJobStatus.success}
          failed={queueJobStatus.failed}
          inProgress={queueJobStatus.in_progress}
          queued={queueJobStatus.queued}
          progressPct={queueJobStatus.progress_pct}
          canCancel={queueJobStatus.can_cancel}
          cancelRequested={queueJobStatus.cancel_requested}
          onCancel={handleCancelQueue}
          onDismiss={() => {
            setQueueJobStatus(null);
            setActiveRunId(null);
          }}
        />
      )}

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
            <PhoneOutgoing className="h-4 w-4" />
            <span className="hidden sm:inline">לידים לשיחות יוצאות</span>
            <span className="sm:hidden">יוצאות</span>
          </div>
        </button>
        <button
          className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors whitespace-nowrap flex-shrink-0 ${
            activeTab === 'imported'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('imported');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-imported-leads"
        >
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            <span className="hidden sm:inline">רשימת ייבוא לשיחות יוצאות</span>
            <span className="sm:hidden">ייבוא</span>
            {totalImported > 0 && (
              <span className="bg-blue-100 text-blue-600 text-xs px-2 py-0.5 rounded-full">
                {totalImported}
              </span>
            )}
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
        <button
          className={`px-4 sm:px-6 py-3 font-medium text-xs sm:text-sm transition-colors whitespace-nowrap flex-shrink-0 ${
            activeTab === 'projects'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('projects');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-projects"
        >
          <div className="flex items-center gap-2">
            <LayoutGrid className="h-4 w-4" />
            פרויקטים
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
              setSelectedImportedLeads(new Set());
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
                            source="outbound_calls"
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
                <PhoneOutgoing className="h-5 w-5" />
                לידים פעילים לשיחות יוצאות ({totalActiveLeads} כולל)
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
                {searchQuery ? 'לא נמצאו לידים מתאימים' : 'אין לידים פעילים לשיחות יוצאות'}
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
                          source="outbound_calls"
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
            כל הלידים שנבחרו לקמפיין שיחות יוצאות מוצגים כאן
          </p>
        </div>
      )}

      {/* Imported Leads Tab */}
      {!showResults && activeTab === 'imported' && (
        <div className="space-y-4">
          {/* Import Result */}
          {showImportResult && importResult && (
            <Card className="p-4">
              <div className={`flex items-start gap-3 ${importResult.success ? 'text-green-700' : 'text-red-700'}`}>
                {importResult.success ? (
                  <CheckCircle2 className="h-5 w-5 mt-0.5" />
                ) : (
                  <XCircle className="h-5 w-5 mt-0.5" />
                )}
                <div className="flex-1">
                  {importResult.success ? (
                    <>
                      <p className="font-medium">הייבוא הושלם בהצלחה!</p>
                      <p className="text-sm mt-1">
                        יובאו {importResult.imported_count} לידים
                        {importResult.skipped_count > 0 && `, ${importResult.skipped_count} שורות דולגו`}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="font-medium">שגיאה בייבוא</p>
                      {importResult.errors.map((err, i) => (
                        <p key={i} className="text-sm mt-1">{err}</p>
                      ))}
                    </>
                  )}
                </div>
                <button 
                  onClick={() => setShowImportResult(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              </div>
            </Card>
          )}

          {/* Import Area */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  <Upload className="h-5 w-5" />
                  ייבוא לידים מקובץ
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  ניתן לייצא מאקסל או Google Sheets כ-CSV / Excel ולהעלות כאן. השרת יזהה עמודות אוטומטית — חובה רק מספר טלפון (שם אופציונלי).
                </p>
              </div>
              <div className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">
                {totalImported} מתוך {importLimit} לידים
              </div>
            </div>

            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                onChange={handleFileUpload}
                className="hidden"
                id="csv-upload"
                data-testid="input-csv-upload"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <FileSpreadsheet className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 mb-2">לחץ לבחירת קובץ CSV / Excel</p>
                <p className="text-sm text-gray-400">או גרור ושחרר כאן</p>
              </label>
              {importMutation.isPending && (
                <div className="mt-4 flex items-center justify-center gap-2 text-blue-600">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>מייבא לידים...</span>
                </div>
              )}
            </div>
          </Card>

          {/* Imported Leads Display - Kanban or Table */}
          {/* Sticky Action Bar for Imported Tab */}
          <div className="sticky top-0 z-30 bg-white border-b border-gray-200 -mx-6 px-6 py-3 shadow-sm">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                {/* Import List Filter */}
                <div className="w-full sm:w-48">
                  <Select
                    value={selectedImportListId?.toString() || ''}
                    onChange={(e) => {
                      const value = e.target.value;
                      setSelectedImportListId(value ? parseInt(value) : null);
                      setCurrentPage(1);
                    }}
                    className="w-full"
                    data-testid="imported-list-filter"
                  >
                    <option value="">כל רשימות הייבוא</option>
                    {(importListsData?.lists || []).map((list) => (
                      <option key={list.id} value={list.id}>
                        {list.name} ({list.current_leads})
                      </option>
                    ))}
                  </Select>
                </div>
                {/* Status Filter */}
                <div className="w-full sm:w-48">
                  <MultiStatusSelect
                    statuses={statuses}
                    selectedStatuses={selectedStatuses}
                    onChange={setSelectedStatuses}
                    placeholder="סנן לפי סטטוס"
                    data-testid="imported-kanban-status-filter"
                  />
                </div>
                {selectedStatuses.length > 0 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSelectAllInStatuses}
                    className="whitespace-nowrap"
                    data-testid="button-select-all-in-statuses-imported"
                  >
                    בחר הכל בסטטוסים ({selectedStatuses.length})
                  </Button>
                )}
                <div className="relative w-full sm:w-64">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="חיפוש לפי שם או טלפון..."
                    value={importedSearchQuery}
                    onChange={(e) => {
                      setImportedSearchQuery(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="pr-10 w-full"
                    data-testid="input-imported-kanban-search"
                  />
                </div>
              </div>
              <Button
                size="lg"
                disabled={
                  safeSelectedImportedLeads.size === 0 ||
                  !canStartCalls ||
                  startCallsMutation.isPending
                }
                onClick={handleStartCalls}
                className="px-8 w-full sm:w-auto"
                data-testid="button-start-imported-calls"
              >
                {startCallsMutation.isPending ? (
                  <>
                    <Loader2 className="h-5 w-5 ml-2 animate-spin" />
                    מתחיל שיחות...
                  </>
                ) : (
                  <>
                    <PlayCircle className="h-5 w-5 ml-2" />
                    הפעל {safeSelectedImportedLeads.size} שיחות
                  </>
                )}
              </Button>
            </div>
          </div>

          {viewMode === 'kanban' ? (
            <>

              {(importedLoading || statusesLoading) ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
                </div>
              ) : statuses.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  לא נמצאו סטטוסים. יש להגדיר סטטוסים במערכת.
                </Card>
              ) : importedLeadsAsLeads.length === 0 ? (
                <Card className="p-8 text-center text-gray-500">
                  עדיין לא יובאו לידים
                </Card>
              ) : (
                <div className="min-h-[600px]">
                  <OutboundKanbanView
                    leads={importedLeadsAsLeads}
                    statuses={statuses}
                    loading={importedLoading}
                    selectedLeadIds={safeSelectedImportedLeads}
                    onLeadSelect={(leadId) => handleToggleImportedLead(leadId)}
                    onLeadClick={handleLeadClick}
                    onStatusChange={handleStatusChange}
                    onSelectAll={handleSelectAll}
                    onClearSelection={handleClearSelection}
                    updatingStatusLeadId={updatingStatusLeadId}
                    statusCounts={importedLeadsStatusCounts}
                    totalLeads={totalImported}
                  />
                </div>
              )}
            </>
          ) : (
            <Card className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  לידים מיובאים ({safeSelectedImportedLeads.size})
                </h3>
                <div className="flex items-center gap-3">
                  {safeSelectedImportedLeads.size > 0 && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleBulkDelete}
                      disabled={bulkDeleteMutation.isPending}
                      data-testid="button-bulk-delete"
                    >
                      {bulkDeleteMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <Trash2 className="h-4 w-4 ml-1" />
                          מחק נבחרים ({safeSelectedImportedLeads.size})
                        </>
                      )}
                    </Button>
                  )}
                  <div className="w-48">
                    <Select
                      value={selectedImportListId?.toString() || ''}
                      onChange={(e) => {
                        const value = e.target.value;
                        setSelectedImportListId(value ? parseInt(value) : null);
                        setCurrentPage(1);
                      }}
                      className="w-full"
                      data-testid="imported-table-list-filter"
                    >
                      <option value="">כל רשימות הייבוא</option>
                      {(importListsData?.lists || []).map((list) => (
                        <option key={list.id} value={list.id}>
                          {list.name} ({list.current_leads})
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="w-48">
                    <MultiStatusSelect
                      statuses={statuses}
                      selectedStatuses={selectedStatuses}
                      onChange={setSelectedStatuses}
                      placeholder="סנן לפי סטטוס"
                      data-testid="imported-table-status-filter"
                    />
                  </div>
                  <div className="relative">
                    <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="חיפוש..."
                      value={importedSearchQuery}
                      onChange={(e) => {
                        setImportedSearchQuery(e.target.value);
                        setCurrentPage(1);
                      }}
                      className="pr-10 w-48"
                      data-testid="input-imported-search"
                    />
                  </div>
                </div>
              </div>

            {importedLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : importedLeads.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {importedSearchQuery ? 'לא נמצאו לידים מתאימים' : 'עדיין לא יובאו לידים'}
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                         <th className="text-right py-3 px-2 font-medium">
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={safeSelectedImportedLeads.size > 0 && safeSelectedImportedLeads.size === importedLeads.length}
                              onChange={handleSelectAllImported}
                              className="h-4 w-4 rounded border-gray-300"
                              data-testid="checkbox-select-all-imported"
                              aria-label="בחר את כל הלידים"
                            />
                            <span>בחירה</span>
                          </div>
                        </th>
                        <th className="text-right py-3 px-2 font-medium">שם</th>
                        <th className="text-right py-3 px-2 font-medium">טלפון</th>
                        <th className="text-right py-3 px-2 font-medium">סטטוס</th>
                        <th className="text-right py-3 px-2 font-medium">הערות</th>
                        <th className="text-right py-3 px-2 font-medium">נוצר</th>
                        <th className="text-right py-3 px-2 font-medium">פעולות</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importedLeads.map((lead) => {
                        const isSelected = safeSelectedImportedLeads.has(lead.id);
                        
                        return (
                          <tr 
                            key={lead.id} 
                            className={`border-b hover:bg-gray-50 cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                            data-testid={`imported-lead-row-${lead.id}`}
                            onClick={() => handleLeadClick(lead.id)}
                          >
                            <td className="py-3 px-2" onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleImportedLead(lead.id)}
                                className="h-4 w-4 rounded border-gray-300"
                                data-testid={`checkbox-imported-${lead.id}`}
                              />
                            </td>
                            <td className="py-3 px-2 font-medium">{lead.name}</td>
                            <td className="py-3 px-2" dir="ltr">{lead.phone}</td>
                            <td className="py-3 px-2" onClick={(e) => e.stopPropagation()}>
                              {/* ✅ Use unified StatusCell component */}
                              <StatusDropdownWithWebhook
                                leadId={lead.id}
                                currentStatus={lead.status}
                                statuses={statuses}
                                onStatusChange={async (newStatus) => await handleStatusChange(lead.id, newStatus)}
                                source="outbound_calls"
                                hasWebhook={hasWebhook}
                                size="sm"
                              />
                            </td>
                            <td className="py-3 px-2 text-gray-500 max-w-[150px] truncate">
                              {lead.notes || '-'}
                            </td>
                            <td className="py-3 px-2 text-gray-500">
                              {lead.created_at 
                                ? formatDateOnly(lead.created_at)
                                : '-'}
                            </td>
                            <td className="py-3 px-2" onClick={(e) => e.stopPropagation()}>
                              <button
                                onClick={() => handleDeleteLead(lead.id)}
                                className="text-red-500 hover:text-red-700 p-1"
                                title="מחק ליד"
                                data-testid={`button-delete-${lead.id}`}
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4">
                    <div className="text-sm text-gray-500">
                      עמוד {currentPage} מתוך {totalPages}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                        data-testid="button-prev-page"
                      >
                        הקודם
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                        data-testid="button-next-page"
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
                {recentCallsSearch ? 'לא נמצאו שיחות מתאימות' : 'עדיין לא בוצעו שיחות יוצאות'}
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

      {/* Projects Tab */}
      {!showResults && activeTab === 'projects' && (
        <div className="space-y-4">
          {projectsError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
              <XCircle className="h-5 w-5 text-red-600" />
              <div className="flex-1">
                <span className="text-red-800 font-medium">שגיאה בטעינת פרויקטים</span>
                <p className="text-red-600 text-sm mt-1">
                  {projectsError instanceof Error ? projectsError.message : 'אנא נסה שוב מאוחר יותר'}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => refetchProjects()}
                className="flex-shrink-0"
              >
                נסה שוב
              </Button>
            </div>
          )}
          {selectedProjectId ? (
            <ProjectDetailView
              projectId={selectedProjectId}
              onBack={() => {
                setSelectedProjectId(null);
                refetchProjects();
              }}
              onStartCalls={(leadIds) => {
                // Use existing bulk call mutation with project_id
                startCallsMutation.mutate({ lead_ids: leadIds, project_id: selectedProjectId });
              }}
              statuses={statuses}
              hasWebhook={hasWebhook}
            />
          ) : (
            <>
              <ProjectsListView
                projects={projects}
                loading={projectsLoading}
                onCreateProject={() => setShowCreateProject(true)}
                onOpenProject={(projectId) => setSelectedProjectId(projectId)}
                onDeleteProject={async (projectId) => {
                  if (confirm('האם אתה בטוח שברצונך למחוק את הפרויקט?')) {
                    try {
                      await http.delete(`/api/projects/${projectId}`);
                      refetchProjects();
                    } catch (error) {
                      console.error('Error deleting project:', error);
                      alert('שגיאה במחיקת הפרויקט');
                    }
                  }
                }}
              />

              {/* Pagination */}
              {totalProjectsPages > 1 && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-gray-100">
                  <div className="text-sm text-gray-500 order-2 sm:order-1">
                    עמוד {projectsPage} מתוך {totalProjectsPages}
                  </div>
                  <div className="flex gap-2 w-full sm:w-auto order-1 sm:order-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setProjectsPage(p => Math.max(1, p - 1))}
                      disabled={projectsPage === 1}
                      data-testid="button-prev-projects-page"
                      className="flex-1 sm:flex-none min-h-[44px]"
                    >
                      הקודם
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setProjectsPage(p => Math.min(totalProjectsPages, p + 1))}
                      disabled={projectsPage === totalProjectsPages}
                      data-testid="button-next-projects-page"
                      className="flex-1 sm:flex-none min-h-[44px]"
                    >
                      הבא
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateProject && (
        <CreateProjectModal
          onClose={() => setShowCreateProject(false)}
          onCreate={async (name, description, leadIds) => {
            try {
              const response = await http.post('/api/projects', {
                name,
                description,
                lead_ids: leadIds
              });
              
              setShowCreateProject(false);
              refetchProjects();
              
              // Show feedback about the result
              if (response.message) {
                alert(response.message);
              }
            } catch (error) {
              console.error('Error creating project:', error);
              throw error;
            }
          }}
          statuses={statuses}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="p-6 max-w-md mx-4">
            <h3 className="font-bold text-lg mb-2">אישור מחיקה</h3>
            <p className="text-gray-600 mb-4">
              למחוק את הליד הזה מרשימת השיחות היוצאות? הפעולה בלתי הפיכה.
            </p>
            <div className="flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteLeadId(null);
                }}
                data-testid="button-cancel-delete"
              >
                ביטול
              </Button>
              <Button
                variant="destructive"
                onClick={confirmDelete}
                disabled={deleteLeadMutation.isPending}
                data-testid="button-confirm-delete"
              >
                {deleteLeadMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'מחק'
                )}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

export default OutboundCallsPage;
