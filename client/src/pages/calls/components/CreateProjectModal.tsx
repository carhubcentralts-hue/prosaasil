import React, { useState, useEffect } from 'react';
import { 
  X, 
  Users, 
  Search,
  FileSpreadsheet,
  CheckCircle2,
  Loader2
} from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Card } from '../../../shared/components/ui/Card';
import { Input } from '../../../shared/components/ui/Input';
import { MultiStatusSelect } from '../../../shared/components/ui/MultiStatusSelect';
import { http } from '../../../services/http';
import type { LeadStatusConfig } from '../../../shared/types/status';
import type { Lead } from '../../Leads/types';

interface CreateProjectModalProps {
  onClose: () => void;
  onCreate: (name: string, description: string, leadIds: number[]) => Promise<void>;
  statuses: LeadStatusConfig[];
}

export function CreateProjectModal({
  onClose,
  onCreate,
  statuses
}: CreateProjectModalProps) {
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [step, setStep] = useState<'details' | 'leads'>('details');
  const [leadSource, setLeadSource] = useState<'system' | 'import'>('system');
  
  // System leads state
  const [systemLeads, setSystemLeads] = useState<Lead[]>([]);
  const [loadingSystemLeads, setLoadingSystemLeads] = useState(false);
  const [systemLeadsSearch, setSystemLeadsSearch] = useState('');
  const [selectedStatusFilters, setSelectedStatusFilters] = useState<string[]>([]);
  
  // Import leads state
  const [importLeads, setImportLeads] = useState<any[]>([]);
  const [loadingImportLeads, setLoadingImportLeads] = useState(false);
  const [importLeadsSearch, setImportLeadsSearch] = useState('');
  const [selectedImportListId, setSelectedImportListId] = useState<number | null>(null);
  const [selectedImportStatusFilters, setSelectedImportStatusFilters] = useState<string[]>([]);
  
  // Selection state
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [creating, setCreating] = useState(false);

  // Import lists state
  const [importLists, setImportLists] = useState<any[]>([]);
  const [loadingImportLists, setLoadingImportLists] = useState(false);

  // Load system leads
  useEffect(() => {
    if (leadSource === 'system' && step === 'leads') {
      loadSystemLeads();
    }
  }, [leadSource, step, systemLeadsSearch, selectedStatusFilters]);

  // Load import leads
  useEffect(() => {
    if (leadSource === 'import' && step === 'leads') {
      loadImportLeads();
    }
  }, [leadSource, step, importLeadsSearch, selectedImportListId, selectedImportStatusFilters]);

  // Load import lists
  useEffect(() => {
    if (leadSource === 'import' && step === 'leads') {
      loadImportLists();
    }
  }, [leadSource, step]);

  const loadSystemLeads = async () => {
    try {
      setLoadingSystemLeads(true);
      const params = new URLSearchParams({
        page: '1',
        pageSize: '100',
      });
      
      if (systemLeadsSearch) {
        params.append('q', systemLeadsSearch);
      }

      if (selectedStatusFilters.length > 0) {
        selectedStatusFilters.forEach(status => {
          params.append('statuses[]', status);
        });
      }

      const response = await http.get(`/api/leads?${params.toString()}`);
      const leads = response.items || response.leads || [];
      setSystemLeads(leads);
    } catch (error) {
      console.error('Error loading system leads:', error);
    } finally {
      setLoadingSystemLeads(false);
    }
  };

  const loadImportLeads = async () => {
    try {
      setLoadingImportLeads(true);
      const params = new URLSearchParams({
        page: '1',
        page_size: '100',
      });
      
      if (importLeadsSearch) {
        params.append('search', importLeadsSearch);
      }

      if (selectedImportListId) {
        params.append('list_id', String(selectedImportListId));
      }

      if (selectedImportStatusFilters.length > 0) {
        selectedImportStatusFilters.forEach(status => {
          params.append('statuses[]', status);
        });
      }

      const response = await http.get(`/api/outbound/import-leads?${params.toString()}`);
      setImportLeads(response.items || []);
    } catch (error) {
      console.error('Error loading import leads:', error);
    } finally {
      setLoadingImportLeads(false);
    }
  };

  const loadImportLists = async () => {
    try {
      setLoadingImportLists(true);
      const response = await http.get('/api/outbound/import-lists');
      setImportLists(response.lists || []);
    } catch (error) {
      console.error('Error loading import lists:', error);
    } finally {
      setLoadingImportLists(false);
    }
  };

  const handleNext = () => {
    if (!projectName.trim()) {
      alert('יש להזין שם פרויקט');
      return;
    }
    setStep('leads');
  };

  const handleCreate = async () => {
    if (!projectName.trim()) {
      alert('יש להזין שם פרויקט');
      return;
    }

    if (selectedLeadIds.size === 0) {
      alert('יש לבחור לפחות ליד אחד לפרויקט');
      return;
    }

    try {
      setCreating(true);
      await onCreate(projectName, projectDescription, Array.from(selectedLeadIds));
      onClose();
    } catch (error) {
      console.error('Error creating project:', error);
      alert('שגיאה ביצירת הפרויקט');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleLead = (leadId: number) => {
    const newSet = new Set(selectedLeadIds);
    if (newSet.has(leadId)) {
      newSet.delete(leadId);
    } else {
      newSet.add(leadId);
    }
    setSelectedLeadIds(newSet);
  };

  const handleSelectAll = () => {
    const currentLeads = leadSource === 'system' ? systemLeads : importLeads;
    if (selectedLeadIds.size === currentLeads.length && currentLeads.length > 0) {
      setSelectedLeadIds(new Set());
    } else {
      setSelectedLeadIds(new Set(currentLeads.map((l: any) => l.id)));
    }
  };

  const handleSelectByStatus = async () => {
    if (selectedStatusFilters.length === 0) {
      alert('יש לבחור לפחות סטטוס אחד');
      return;
    }

    try {
      const response = await http.post('/api/leads/select-ids', {
        statuses: selectedStatusFilters,
        search: systemLeadsSearch,
        tab: 'system'
      });

      const leadIds = response.lead_ids || [];
      setSelectedLeadIds(new Set(leadIds));
    } catch (error) {
      console.error('Error selecting leads by status:', error);
      alert('שגיאה בבחירת לידים');
    }
  };

  const handleSelectImportByStatus = async () => {
    if (selectedImportStatusFilters.length === 0) {
      alert('יש לבחור לפחות סטטוס אחד');
      return;
    }

    try {
      const response = await http.post('/api/leads/select-ids', {
        statuses: selectedImportStatusFilters,
        search: importLeadsSearch,
        tab: 'imported',
        list_id: selectedImportListId
      });

      const leadIds = response.lead_ids || [];
      setSelectedLeadIds(new Set(leadIds));
    } catch (error) {
      console.error('Error selecting import leads by status:', error);
      alert('שגיאה בבחירת לידים');
    }
  };

  const currentLeads = leadSource === 'system' ? systemLeads : importLeads;
  const loading = leadSource === 'system' ? loadingSystemLeads : loadingImportLeads;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">יצירת פרויקט חדש</h2>
          <Button variant="ghost" onClick={onClose} className="min-h-[44px] min-w-[44px]">
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Step Indicator */}
        <div className="flex items-center gap-4 mb-6">
          <div className={`flex items-center gap-2 ${step === 'details' ? 'text-blue-600' : 'text-green-600'}`}>
            {step === 'leads' ? <CheckCircle2 className="h-5 w-5" /> : <div className="h-5 w-5 rounded-full border-2 border-current flex items-center justify-center"><span className="text-xs">1</span></div>}
            <span className="font-medium">פרטי פרויקט</span>
          </div>
          <div className="flex-1 h-0.5 bg-gray-200">
            <div className={`h-full ${step === 'leads' ? 'bg-blue-600' : 'bg-gray-200'} transition-all`} style={{ width: step === 'leads' ? '100%' : '0%' }} />
          </div>
          <div className={`flex items-center gap-2 ${step === 'leads' ? 'text-blue-600' : 'text-gray-400'}`}>
            <div className="h-5 w-5 rounded-full border-2 border-current flex items-center justify-center"><span className="text-xs">2</span></div>
            <span className="font-medium">בחירת לידים</span>
          </div>
        </div>

        {/* Step 1: Project Details */}
        {step === 'details' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                שם פרויקט <span className="text-red-500">*</span>
              </label>
              <Input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="לדוגמה: קמפיין מכירות Q1 2024"
                className="w-full"
                autoFocus
                data-testid="input-project-name"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                תיאור (אופציונלי)
              </label>
              <textarea
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
                placeholder="תיאור קצר של הפרויקט ומטרותיו"
                className="w-full p-2 border border-gray-300 rounded-md min-h-[100px]"
                data-testid="textarea-project-description"
              />
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button variant="outline" onClick={onClose}>
                ביטול
              </Button>
              <Button onClick={handleNext} data-testid="button-next">
                המשך לבחירת לידים
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Select Leads */}
        {step === 'leads' && (
          <div className="space-y-4">
            {/* Lead Source Tabs */}
            <div className="flex border-b border-gray-200">
              <button
                className={`px-4 py-2 font-medium text-sm transition-colors ${
                  leadSource === 'system'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setLeadSource('system')}
                data-testid="tab-system-leads"
              >
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  לידים במערכת
                </div>
              </button>
              <button
                className={`px-4 py-2 font-medium text-sm transition-colors ${
                  leadSource === 'import'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setLeadSource('import')}
                data-testid="tab-import-leads"
              >
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  רשימות ייבוא
                </div>
              </button>
            </div>

            {/* Filters and Search */}
            <div className="flex flex-col sm:flex-row gap-3">
              {leadSource === 'system' && (
                <>
                  <div className="flex-1">
                    <MultiStatusSelect
                      statuses={statuses}
                      selectedStatuses={selectedStatusFilters}
                      onChange={setSelectedStatusFilters}
                      placeholder="סנן לפי סטטוס"
                      data-testid="status-filter"
                    />
                  </div>
                  {selectedStatusFilters.length > 0 && (
                    <Button
                      variant="outline"
                      onClick={handleSelectByStatus}
                      className="whitespace-nowrap"
                      data-testid="button-select-by-status"
                    >
                      בחר הכל בסטטוסים
                    </Button>
                  )}
                </>
              )}
              {leadSource === 'import' && (
                <>
                  <div className="flex-1">
                    <select
                      value={selectedImportListId?.toString() || ''}
                      onChange={(e) => {
                        const value = e.target.value;
                        setSelectedImportListId(value ? parseInt(value) : null);
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      data-testid="import-list-filter"
                    >
                      <option value="">כל רשימות הייבוא</option>
                      {importLists.map((list: any) => (
                        <option key={list.id} value={list.id}>
                          {list.name} ({list.current_leads})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex-1">
                    <MultiStatusSelect
                      statuses={statuses}
                      selectedStatuses={selectedImportStatusFilters}
                      onChange={setSelectedImportStatusFilters}
                      placeholder="סנן לפי סטטוס"
                      data-testid="import-status-filter"
                    />
                  </div>
                  {selectedImportStatusFilters.length > 0 && (
                    <Button
                      variant="outline"
                      onClick={handleSelectImportByStatus}
                      className="whitespace-nowrap"
                      data-testid="button-select-import-by-status"
                    >
                      בחר הכל בסטטוסים
                    </Button>
                  )}
                </>
              )}
              <div className="relative flex-1">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="חיפוש..."
                  value={leadSource === 'system' ? systemLeadsSearch : importLeadsSearch}
                  onChange={(e) => leadSource === 'system' ? setSystemLeadsSearch(e.target.value) : setImportLeadsSearch(e.target.value)}
                  className="pr-10"
                  data-testid="input-search-leads"
                />
              </div>
              <Button
                variant="outline"
                onClick={handleSelectAll}
                disabled={currentLeads.length === 0}
                data-testid="button-toggle-all"
              >
                {selectedLeadIds.size === currentLeads.length && currentLeads.length > 0 ? 'בטל בחירה' : 'בחר הכל'}
              </Button>
            </div>

            {/* Selected Count */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-900">
                <strong>{selectedLeadIds.size}</strong> לידים נבחרו מתוך {currentLeads.length} זמינים
              </p>
            </div>

            {/* Leads List */}
            <div className="border border-gray-200 rounded-lg max-h-[400px] overflow-y-auto">
              {loading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                </div>
              ) : currentLeads.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  לא נמצאו לידים
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {currentLeads.map((lead: any) => {
                    const isSelected = selectedLeadIds.has(lead.id);
                    const displayName = lead.full_name || lead.name || 'ללא שם';
                    const displayPhone = lead.phone_e164 || lead.phone || '';
                    const displayStatus = lead.status || 'חדש';
                    
                    return (
                      <label
                        key={lead.id}
                        className={`flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 ${
                          isSelected ? 'bg-blue-50' : ''
                        }`}
                        data-testid={`lead-item-${lead.id}`}
                      >
                        <div className="flex-shrink-0">
                          {isSelected ? (
                            <CheckCircle2 className="h-5 w-5 text-blue-600" />
                          ) : (
                            <div className="h-5 w-5 border-2 border-gray-300 rounded" />
                          )}
                        </div>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleLead(lead.id)}
                          className="hidden"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">{displayName}</div>
                          <div className="text-sm text-gray-500 truncate" dir="ltr">{displayPhone}</div>
                        </div>
                        <div className="flex-shrink-0">
                          <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">
                            {displayStatus}
                          </span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
              <Button variant="outline" onClick={() => setStep('details')}>
                חזור
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating || selectedLeadIds.size === 0}
                data-testid="button-create-project"
              >
                {creating ? (
                  <>
                    <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                    יוצר...
                  </>
                ) : (
                  <>
                    צור פרויקט ({selectedLeadIds.size} לידים)
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
