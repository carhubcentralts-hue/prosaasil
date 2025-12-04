import React, { useState, useRef, ChangeEvent } from 'react';
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
  Download
} from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { http } from '../../services/http';

interface Lead {
  id: number;
  full_name: string;
  phone_e164: string;
  status: string;
  created_at: string;
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

type TabType = 'existing' | 'imported';

export function OutboundCallsPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('existing');
  
  // Existing leads state
  const [selectedLeads, setSelectedLeads] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
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

  const { data: leadsData, isLoading: leadsLoading, error: leadsError } = useQuery<{ leads: Lead[] }>({
    queryKey: ['/api/leads', searchQuery],
    enabled: activeTab === 'existing',
    select: (data: any) => {
      if (!data) return { leads: [] };
      if (Array.isArray(data)) return { leads: data };
      if (data.items && Array.isArray(data.items)) return { leads: data.items };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads };
      return { leads: [] };
    },
    retry: 1,
  });

  const { data: importedLeadsData, isLoading: importedLoading, refetch: refetchImported } = useQuery<ImportedLeadsResponse>({
    queryKey: ['/api/outbound/import-leads', currentPage, importedSearchQuery],
    enabled: activeTab === 'imported',
    retry: 1,
  });

  const leads = Array.isArray(leadsData?.leads) ? leadsData.leads : [];
  const importedLeads = importedLeadsData?.items || [];
  const totalImported = importedLeadsData?.total || 0;
  const importLimit = importedLeadsData?.limit || 5000;

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

  return (
    <div className="p-6 space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PhoneOutgoing className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">שיחות יוצאות</h1>
            <p className="text-sm text-gray-500">בחר לידים והפעל שיחות AI יוצאות</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
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
            activeTab === 'existing'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => {
            setActiveTab('existing');
            setShowResults(false);
            setCallResults([]);
          }}
          data-testid="tab-existing-leads"
        >
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            לידים קיימים
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

      {/* Existing Leads Tab */}
      {!showResults && activeTab === 'existing' && (
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Users className="h-5 w-5" />
                בחירת לידים ({selectedLeads.length}/{Math.min(3, availableSlots)})
              </h3>
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="חיפוש לפי שם או טלפון..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pr-10 w-64"
                  data-testid="input-lead-search"
                />
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
                    className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedLeads.includes(lead.id)
                        ? 'bg-blue-50 border-blue-300'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    onClick={() => !isDisabled && handleToggleLead(lead.id)}
                    data-testid={`lead-select-${lead.id}`}
                  >
                    <div>
                      <div className="font-medium">{lead.full_name || 'ללא שם'}</div>
                      <div className="text-sm text-gray-500" dir="ltr">{lead.phone_e164}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-gray-100 px-2 py-1 rounded">{lead.status}</span>
                      {selectedLeads.includes(lead.id) && (
                        <CheckCircle2 className="h-5 w-5 text-blue-600" />
                      )}
                    </div>
                  </div>
                );})}
              </div>
            )}
          </Card>

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

          {/* Imported Leads Table */}
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
                        <th className="text-right py-3 px-2 font-medium">בחירה</th>
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
                            className={`border-b hover:bg-gray-50 ${isSelected ? 'bg-blue-50' : ''}`}
                            data-testid={`imported-lead-row-${lead.id}`}
                          >
                            <td className="py-3 px-2">
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
                            <td className="py-3 px-2">
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
