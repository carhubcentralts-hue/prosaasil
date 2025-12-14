import React, { useState, useRef, ChangeEvent, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  List
} from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { MultiStatusSelect } from '../../shared/components/ui/MultiStatusSelect';
import { http } from '../../services/http';
import { OutboundKanbanView } from './components/OutboundKanbanView';
import { Lead } from '../Leads/types';  // ✅ Use shared Lead type

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

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

type TabType = 'system' | 'active' | 'imported';
type ViewMode = 'table' | 'kanban';

export function OutboundCallsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Tab and view state
  const [activeTab, setActiveTab] = useState<TabType>('system');
  const [viewMode, setViewMode] = useState<ViewMode>('kanban'); // Default to Kanban
  
  // Existing leads state
  const [selectedLeads, setSelectedLeads] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [callResults, setCallResults] = useState<CallResult[]>([]);
  
  // Imported leads state
  const [selectedImportedLeads, setSelectedImportedLeads] = useState<number[]>([]);
  const [importedSearchQuery, setImportedSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [showImportResult, setShowImportResult] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLeadId, setDeleteLeadId] = useState<number | null>(null);
  const pageSize = 50;

  // Queries
  const { data: counts, isLoading: countsLoading, refetch: refetchCounts, error: countsError } = useQuery<CallCounts>({
    queryKey: ['/api/outbound_calls/counts'],
    refetchInterval: 10000,
    retry: 1,
  });

  // Fetch lead statuses for Kanban
  const { data: statusesData, isLoading: statusesLoading } = useQuery<LeadStatus[]>({
    queryKey: ['/api/lead-statuses'],
    enabled: viewMode === 'kanban',
    retry: 1,
  });

  useEffect(() => {
    if (statusesData) {
      console.log('[OutboundCallsPage] ✅ Lead statuses loaded:', statusesData);
    }
  }, [statusesData]);

  const { data: leadsData, isLoading: leadsLoading, error: leadsError } = useQuery({
    queryKey: ['/api/leads', 'system', searchQuery, selectedStatuses],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: '1',
        pageSize: '100',
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
      if (!data) return { leads: [] };
      // Try different response formats for backward compatibility
      if (Array.isArray(data)) return { leads: data };
      if (data.items && Array.isArray(data.items)) return { leads: data.items };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads };
      return { leads: [] };
    },
    retry: 1,
  });

  // Query for active outbound leads (leads assigned to outbound campaign)
  const { data: activeLeadsData, isLoading: activeLoading, error: activeError } = useQuery({
    queryKey: ['/api/leads', 'active-outbound', searchQuery, selectedStatuses],
    queryFn: async () => {
      const params = new URLSearchParams({
        direction: 'outbound',
        page: '1',
        pageSize: '100',
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
      if (!data) return { leads: [] };
      if (Array.isArray(data)) return { leads: data };
      if (data.items && Array.isArray(data.items)) return { leads: data.items };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads };
      return { leads: [] };
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

  const { data: importedLeadsData, isLoading: importedLoading, refetch: refetchImported } = useQuery<ImportedLeadsResponse>({
    queryKey: ['/api/outbound/import-leads', currentPage, importedSearchQuery],
    enabled: activeTab === 'imported',
    retry: 1,
  });

  const systemLeads = Array.isArray(leadsData?.leads) ? leadsData.leads : [];
  const activeLeads = Array.isArray(activeLeadsData?.leads) ? activeLeadsData.leads : [];
  const importedLeads = importedLeadsData?.items || [];
  const totalImported = importedLeadsData?.total || 0;
  const importLimit = importedLeadsData?.limit || 5000;

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
    mutationFn: async (data: { lead_ids: number[] }) => {
      return await http.post<any>('/api/outbound_calls/start', data);
    },
    onSuccess: (data) => {
      setCallResults(data.calls || []);
      setShowResults(true);
      refetchCounts();
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
      setSelectedImportedLeads([]);
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ leadId, newStatus }: { leadId: number; newStatus: string }) => {
      console.log(`[OutboundCallsPage] Updating lead ${leadId} status to ${newStatus}`);
      return await http.patch(`/api/leads/${leadId}/status`, { status: newStatus });
    },
    onSuccess: (data, variables) => {
      console.log(`[OutboundCallsPage] ✅ Status updated for lead ${variables.leadId}`);
      queryClient.invalidateQueries({ queryKey: ['/api/leads'] });
    },
    onError: (error, variables) => {
      console.error(`[OutboundCallsPage] ❌ Failed to update status for lead ${variables.leadId}:`, error);
    },
  });

  // Handlers
  const handleToggleLead = (leadId: number) => {
    setSelectedLeads(prev => {
      if (prev.includes(leadId)) {
        return prev.filter(id => id !== leadId);
      }
      const maxSelectable = Math.min(3, availableSlots);
      if (prev.length >= maxSelectable) {
        return prev;
      }
      return [...prev, leadId];
    });
  };

  const handleToggleImportedLead = (leadId: number) => {
    setSelectedImportedLeads(prev => {
      if (prev.includes(leadId)) {
        return prev.filter(id => id !== leadId);
      }
      const maxSelectable = Math.min(3, availableSlots);
      if (prev.length >= maxSelectable) {
        return prev;
      }
      return [...prev, leadId];
    });
  };

  const handleStartCalls = () => {
    const ids = activeTab === 'existing' ? selectedLeads : selectedImportedLeads;
    if (ids.length === 0) return;
    
    startCallsMutation.mutate({ lead_ids: ids });
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
    if (selectedImportedLeads.length > 0) {
      bulkDeleteMutation.mutate(selectedImportedLeads);
    }
  };
  
  const handleSelectAllImported = () => {
    const maxSelectable = Math.min(3, availableSlots);
    const selectableCount = Math.min(importedLeads.length, maxSelectable);
    
    if (selectedImportedLeads.length === selectableCount) {
      // Deselect all
      setSelectedImportedLeads([]);
    } else {
      // Select up to max
      const leadsToSelect = importedLeads.slice(0, maxSelectable).map(l => l.id);
      setSelectedImportedLeads(leadsToSelect);
    }
  };

  const handleLeadSelect = (leadId: number, isShiftKey?: boolean) => {
    setSelectedLeads(prev => {
      if (prev.includes(leadId)) {
        return prev.filter(id => id !== leadId);
      }
      const maxSelectable = Math.min(3, availableSlots);
      if (prev.length >= maxSelectable) {
        return prev;
      }
      return [...prev, leadId];
    });
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    console.log(`[OutboundCallsPage] handleStatusChange called: lead=${leadId}, newStatus=${newStatus}`);
    await updateStatusMutation.mutateAsync({ leadId, newStatus });
  };

  const handleLeadClick = (leadId: number) => {
    navigate(`/app/leads/${leadId}`);
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
    : 3;

  const totalPages = Math.ceil(totalImported / pageSize);

  const statuses = statusesData || [];
  const selectedLeadIdsSet = new Set(selectedLeads);

  // Log on component mount
  useEffect(() => {
    console.log('[OutboundCallsPage] 🎯 Component mounted');
    console.log('[OutboundCallsPage] Default view mode:', viewMode);
  }, []);

  return (
    <div className="p-6 space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PhoneOutgoing className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">שיחות יוצאות</h1>
            <p className="text-sm text-gray-500">לידים שמקורם משיחות יוצאות + ניהול רשימות ייבוא</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* View Mode Toggle */}
          {(activeTab === 'system' || activeTab === 'active' || activeTab === 'imported') && !showResults && (
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => {
                  console.log('[OutboundCallsPage] Switching to Kanban view');
                  setViewMode('kanban');
                }}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  viewMode === 'kanban'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
                data-testid="button-kanban-view"
              >
                <LayoutGrid className="h-4 w-4" />
                Kanban
              </button>
              <button
                onClick={() => {
                  console.log('[OutboundCallsPage] Switching to Table view');
                  setViewMode('table');
                }}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  viewMode === 'table'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
                data-testid="button-table-view"
              >
                <List className="h-4 w-4" />
                רשימה
              </button>
            </div>
          )}
          
          {counts && (
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">
              <Phone className="h-4 w-4" />
              <span>
                שיחות פעילות: {counts.active_total}/{counts.max_total}
              </span>
              <span className="mx-2">|</span>
              <PhoneOutgoing className="h-4 w-4" />
              <span>
                יוצאות: {counts.active_outbound}/{counts.max_outbound}
              </span>
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
      <div className="flex border-b border-gray-200">
        <button
          className={`px-6 py-3 font-medium text-sm transition-colors ${
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
            לידים במערכת
          </div>
        </button>
        <button
          className={`px-6 py-3 font-medium text-sm transition-colors ${
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
            לידים לשיחות יוצאות
          </div>
        </button>
        <button
          className={`px-6 py-3 font-medium text-sm transition-colors ${
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
            רשימת ייבוא לשיחות יוצאות
            {totalImported > 0 && (
              <span className="bg-blue-100 text-blue-600 text-xs px-2 py-0.5 rounded-full">
                {totalImported}
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
              setSelectedLeads([]);
              setSelectedImportedLeads([]);
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
                בחירת לידים ({selectedLeads.length}/{Math.min(3, availableSlots)})
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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
                {filteredLeads.slice(0, 50).map((lead: Lead) => {
                  const maxSelectable = Math.min(3, availableSlots);
                  const isDisabled = selectedLeads.length >= maxSelectable && !selectedLeads.includes(lead.id);
                  
                  return (
                  <div
                    key={lead.id}
                    className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                      selectedLeads.includes(lead.id)
                        ? 'bg-blue-50 border-blue-300'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    } ${isDisabled ? 'opacity-50' : 'cursor-pointer'}`}
                    data-testid={`lead-select-${lead.id}`}
                  >
                    <div 
                      className="flex-1"
                      onClick={() => !isDisabled && handleLeadClick(lead.id)}
                    >
                      <div className="font-medium">{lead.full_name || 'ללא שם'}</div>
                      <div className="text-sm text-gray-500" dir="ltr">{lead.phone_e164}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-gray-100 px-2 py-1 rounded">{lead.status}</span>
                      <div onClick={(e) => { e.stopPropagation(); !isDisabled && handleToggleLead(lead.id); }}>
                        {selectedLeads.includes(lead.id) ? (
                          <CheckCircle2 className="h-5 w-5 text-blue-600 cursor-pointer" />
                        ) : (
                          <div className="h-5 w-5 border-2 border-gray-300 rounded cursor-pointer"></div>
                        )}
                      </div>
                    </div>
                  </div>
                );})}
              </div>
            )}
          </Card>
          )}

          <div className="flex justify-center">
            <Button
              size="lg"
              disabled={
                selectedLeads.length === 0 ||
                !canStartCalls ||
                startCallsMutation.isPending
              }
              onClick={handleStartCalls}
              className="px-8"
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
                  הפעל {selectedLeads.length} שיחות
                </>
              )}
            </Button>
          </div>

          <p className="text-sm text-gray-500 text-center">
            ה-AI ישתמש בפרומפט שיחות יוצאות מהגדרות המערכת
          </p>
        </div>
      )}

      {/* Active Outbound Leads Tab - For Managing Active Campaign */}
      {!showResults && activeTab === 'active' && (
        <div className="space-y-4">
          {/* Kanban View */}
          {viewMode === 'kanban' && (
            <>
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
                לידים פעילים לשיחות יוצאות
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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
                {filteredLeads.slice(0, 50).map((lead: Lead) => (
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
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-gray-100 px-2 py-1 rounded">{lead.status}</span>
                    </div>
                  </div>
                ))}
              </div>
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
                  ניתן לייצא מאקסל או Google Sheets כ-CSV ולהעלות כאן. חובה לכלול עמודות: שם, טלפון. עיר והערות – אופציונלי.
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
                accept=".csv"
                onChange={handleFileUpload}
                className="hidden"
                id="csv-upload"
                data-testid="input-csv-upload"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <FileSpreadsheet className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 mb-2">לחץ לבחירת קובץ CSV</p>
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
                    selectedLeadIds={new Set(selectedImportedLeads)}
                    onLeadSelect={(leadId) => handleToggleImportedLead(leadId)}
                    onLeadClick={handleLeadClick}
                    onStatusChange={handleStatusChange}
                  />
                </div>
              )}
            </>
          ) : (
            <Card className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  לידים מיובאים ({selectedImportedLeads.length}/{Math.min(3, availableSlots)})
                </h3>
                <div className="flex items-center gap-3">
                  {selectedImportedLeads.length > 0 && (
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
                          מחק נבחרים ({selectedImportedLeads.length})
                        </>
                      )}
                    </Button>
                  )}
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
                              checked={selectedImportedLeads.length > 0 && selectedImportedLeads.length === Math.min(importedLeads.length, 3, availableSlots)}
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
                        const maxSelectable = Math.min(3, availableSlots);
                        const isDisabled = selectedImportedLeads.length >= maxSelectable && !selectedImportedLeads.includes(lead.id);
                        const isSelected = selectedImportedLeads.includes(lead.id);
                        
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
                                onChange={() => !isDisabled && handleToggleImportedLead(lead.id)}
                                disabled={isDisabled && !isSelected}
                                className="h-4 w-4 rounded border-gray-300"
                                data-testid={`checkbox-imported-${lead.id}`}
                              />
                            </td>
                            <td className="py-3 px-2 font-medium">{lead.name}</td>
                            <td className="py-3 px-2" dir="ltr">{lead.phone}</td>
                            <td className="py-3 px-2">
                              <span className="text-xs bg-gray-100 px-2 py-1 rounded">{lead.status}</span>
                            </td>
                            <td className="py-3 px-2 text-gray-500 max-w-[150px] truncate">
                              {lead.notes || '-'}
                            </td>
                            <td className="py-3 px-2 text-gray-500">
                              {lead.created_at 
                                ? new Date(lead.created_at).toLocaleDateString('he-IL')
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

          {/* Start Calls Button for Imported Leads */}
          <div className="flex justify-center">
            <Button
              size="lg"
              disabled={
                selectedImportedLeads.length === 0 ||
                !canStartCalls ||
                startCallsMutation.isPending
              }
              onClick={handleStartCalls}
              className="px-8"
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
                  הפעל {selectedImportedLeads.length} שיחות
                </>
              )}
            </Button>
          </div>

          <p className="text-sm text-gray-500 text-center">
            ה-AI ישתמש בפרומפט שיחות יוצאות מהגדרות המערכת
          </p>
        </div>
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
