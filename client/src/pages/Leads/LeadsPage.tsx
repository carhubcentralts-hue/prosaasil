import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Filter, MessageSquare, Edit, Phone, Trash2, Settings, User, CheckSquare, Receipt, Calendar, X, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Checkbox } from '../../shared/components/ui/Checkbox';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../shared/components/ui/Table';
import { Select, SelectOption } from '../../shared/components/ui/Select';
import { StatusDropdown } from '../../shared/components/ui/StatusDropdown';
import LeadCreateModal from './components/LeadCreateModal';
import StatusManagementModal from './components/StatusManagementModal';
import { useLeads } from './hooks/useLeads';
import { Lead, LeadStatus, LeadSource } from './types';
import { useStatuses } from '../../features/statuses/hooks';
import { http } from '../../services/http';
import { getStatusColor, getStatusLabel, getStatusDotColor } from '../../shared/utils/status';

// Safe value helper function as per guidelines
const safe = (val: any, dash: string = '—'): string => {
  if (val === null || val === undefined || val === '') return dash;
  return String(val);
};

export default function LeadsPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<LeadStatus | 'all'>('all');
  const [selectedSource, setSelectedSource] = useState<LeadSource | 'all'>('all');
  const [selectedDirection, setSelectedDirection] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [selectedOutboundList, setSelectedOutboundList] = useState<string>('all');
  const [outboundLists, setOutboundLists] = useState<Array<{ id: number; name: string }>>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [sortBy, setSortBy] = useState<'name' | 'created_at' | 'status'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 25;
  
  // Debounce search input for better performance (150ms delay)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 150);
    return () => clearTimeout(timer);
  }, [searchQuery]);
  
  // Load dynamic statuses
  const { statuses, refreshStatuses } = useStatuses();

  // Load statuses on component mount
  useEffect(() => {
    refreshStatuses();
  }, [refreshStatuses]);
  
  // Load outbound lists for filter
  useEffect(() => {
    const loadOutboundLists = async () => {
      try {
        const response = await http.get('/api/outbound/import-lists');
        if (response && (response as any).lists) {
          setOutboundLists((response as any).lists);
        }
      } catch (error) {
        console.error('Error loading outbound lists:', error);
      }
    };
    loadOutboundLists();
  }, []);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearch, selectedStatus, selectedSource, selectedDirection, selectedOutboundList, dateFrom, dateTo]);

  // Memoize filters using debounced search to prevent excessive API calls
  const filters = useMemo(() => ({
    search: debouncedSearch,
    status: selectedStatus === 'all' ? undefined : selectedStatus,
    source: selectedSource === 'all' ? undefined : selectedSource,
    direction: selectedDirection === 'all' ? undefined : selectedDirection,
    outbound_list_id: selectedOutboundList === 'all' ? undefined : selectedOutboundList,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    page: currentPage,
    pageSize: PAGE_SIZE,
  }), [debouncedSearch, selectedStatus, selectedSource, selectedDirection, selectedOutboundList, dateFrom, dateTo, currentPage]);

  const {
    leads,
    loading,
    error,
    total,
    createLead,
    updateLead,
    deleteLead,
    refreshLeads,
    setLeads,  // ✅ BUILD 170: For optimistic status updates
  } = useLeads(filters);
  
  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Sort and filter leads
  const sortedLeads = useMemo(() => {
    const statusOrder = statuses.reduce((acc, status, index) => {
      acc[status.name] = index;
      acc[status.name.toLowerCase()] = index;
      return acc;
    }, {} as Record<string, number>);
    
    const legacyMapping: Record<string, string> = {
      'New': 'new',
      'Attempting': 'attempting',
      'Contacted': 'contacted',
      'Qualified': 'qualified', 
      'Won': 'won',
      'Lost': 'lost',
      'Unqualified': 'unqualified'
    };

    // Filter by date range
    let filteredLeads = leads;
    if (dateFrom || dateTo) {
      filteredLeads = leads.filter(lead => {
        const leadDate = new Date(lead.created_at);
        leadDate.setHours(0, 0, 0, 0);
        
        if (dateFrom) {
          const fromDate = new Date(dateFrom);
          fromDate.setHours(0, 0, 0, 0);
          if (leadDate < fromDate) return false;
        }
        
        if (dateTo) {
          const toDate = new Date(dateTo);
          toDate.setHours(23, 59, 59, 999);
          if (leadDate > toDate) return false;
        }
        
        return true;
      });
    }

    const sorted = [...filteredLeads].sort((a, b) => {
      let aValue: any;
      let bValue: any;
      
      if (sortBy === 'name') {
        aValue = a.full_name || `${a.first_name} ${a.last_name}`;
        bValue = b.full_name || `${b.first_name} ${b.last_name}`;
      } else if (sortBy === 'status') {
        // ✅ Handle legacy status ordering with fallback
        let aStatus = a.status.toLowerCase();
        let bStatus = b.status.toLowerCase();
        
        // Try legacy mapping if direct lookup fails
        if (statusOrder[aStatus] === undefined && legacyMapping[a.status]) {
          aStatus = legacyMapping[a.status];
        }
        if (statusOrder[bStatus] === undefined && legacyMapping[b.status]) {
          bStatus = legacyMapping[b.status];
        }
        
        aValue = statusOrder[aStatus] ?? 999; // Unknown statuses go to end
        bValue = statusOrder[bStatus] ?? 999;
      } else if (sortBy === 'created_at') {
        aValue = new Date(a.created_at).getTime();
        bValue = new Date(b.created_at).getTime();
      }
      
      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    
    return sorted;
  }, [leads, sortBy, sortOrder, statuses, dateFrom, dateTo]);

  const handleSort = (column: 'name' | 'created_at' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleStatusChange = async (leadId: number, newStatus: LeadStatus) => {
    // ✅ BUILD 170: Optimistic update - immediately update UI without waiting for server
    setEditingStatus(null);
    
    // Find the old status for potential rollback
    const oldLead = leads.find(l => l.id === leadId);
    const oldStatus = oldLead?.status;
    
    // Optimistically update the local state immediately
    setLeads(prevLeads => 
      prevLeads.map(lead => 
        lead.id === leadId ? { ...lead, status: newStatus } : lead
      )
    );
    
    try {
      // Send update to server in background
      await http.post(`/api/leads/${leadId}/status`, { status: newStatus });
    } catch (error) {
      // Rollback on error
      console.error('Failed to update lead status:', error);
      if (oldStatus) {
        setLeads(prevLeads => 
          prevLeads.map(lead => 
            lead.id === leadId ? { ...lead, status: oldStatus } : lead
          )
        );
      }
      alert('שגיאה בעדכון הסטטוס');
    }
  };

  const handleWhatsAppOpen = (phone: string) => {
    if (!phone) {
      alert('אין מספר טלפון זמין ללקוח זה');
      return;
    }
    
    // פתיחת WhatsApp Web/Desktop עם המספר הספציפי
    const cleanPhone = phone.replace(/[^0-9]/g, '');
    const whatsappUrl = `https://wa.me/${cleanPhone}`;
    window.open(whatsappUrl, '_blank');
  };

  const handleCall = (phone: string) => {
    if (!phone) {
      alert('אין מספר טלפון זמין ללקוח זה');
      return;
    }
    
    // פתיחת אפליקציית הטלפון
    window.location.href = `tel:${phone}`;
  };

  const handleDeleteLead = async (leadId: number, leadName: string) => {
    const confirmed = window.confirm(`האם אתה בטוח שברצונך למחוק את הליד ${leadName}?`);
    if (!confirmed) return;
    
    try {
      await deleteLead(leadId);
      // ✅ FIX: deleteLead כבר מעדכן את ה-state - לא צריך refreshLeads!
      // הסרנו refreshLeads() כי זה גורם לליד לחזור אם המחיקה לא הצליחה בשרת
    } catch (error) {
      console.error('Failed to delete lead:', error);
      alert('שגיאה במחיקת הליד');
      // במקרה של שגיאה - רענן לסנכרן עם השרת
      await refreshLeads();
    }
  };

  const handleLeadCreate = async (leadData: Partial<Lead>) => {
    try {
      console.log('🔵 handleLeadCreate - Starting with data:', leadData);
      const newLead = await createLead(leadData);
      console.log('✅ handleLeadCreate - Success! Lead created:', newLead);
      setIsCreateModalOpen(false);
    } catch (error) {
      console.error('❌ handleLeadCreate - Failed to create lead:', error);
      const errorMessage = error instanceof Error ? error.message : 'שגיאה ביצירת הליד';
      alert(errorMessage);
      throw error; // Re-throw so modal shows error
    }
  };

  const handleToggleSelect = (leadId: number) => {
    setSelectedLeadIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(leadId)) {
        newSet.delete(leadId);
      } else {
        newSet.add(leadId);
      }
      return newSet;
    });
  };

  const handleToggleSelectAll = () => {
    if (selectedLeadIds.size === sortedLeads.length) {
      setSelectedLeadIds(new Set());
    } else {
      setSelectedLeadIds(new Set(sortedLeads.map(l => l.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedLeadIds.size === 0) return;
    
    const confirmMessage = `האם אתה בטוח שברצונך למחוק ${selectedLeadIds.size} לידים?`;
    if (!confirm(confirmMessage)) return;

    setIsDeleting(true);
    try {
      const response = await http.post('/api/leads/bulk-delete', {
        lead_ids: Array.from(selectedLeadIds)
      }) as any;
      
      console.log('✅ Bulk delete response:', response);
      
      // Clear selection and refresh
      setSelectedLeadIds(new Set());
      await refreshLeads();
      
      // Show success message
      const deletedCount = response?.deleted_count || selectedLeadIds.size;
      alert(`נמחקו ${deletedCount} לידים בהצלחה`);
    } catch (error: any) {
      console.error('Failed to bulk delete leads:', error);
      const errorMessage = error?.message || error?.error || 'שגיאה במחיקת לידים';
      alert(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <main className="container mx-auto px-2 sm:px-4 pb-24 max-w-full" dir="rtl">
      {/* Header - sticky at absolute top with no gap */}
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur-sm shadow-sm -mx-2 sm:-mx-4 px-2 sm:px-4 pt-3 pb-3 mb-4 border-b border-gray-100">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="text-center sm:text-right">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">לידים</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1 text-sm sm:text-base">ניהול ומעקב אחרי לידים בטבלה מקצועית</p>
          </div>
          <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
            {selectedLeadIds.size > 0 && (
              <Button
                onClick={handleBulkDelete}
                variant="primary"
                size="sm"
                disabled={isDeleting}
                className="w-full sm:w-auto bg-red-600 hover:bg-red-700 text-white"
                data-testid="button-bulk-delete"
              >
                <Trash2 className="w-4 h-4 ml-2" />
                מחק {selectedLeadIds.size} נבחרים
              </Button>
            )}
            <Button
              onClick={() => setIsStatusModalOpen(true)}
              variant="secondary"
              size="sm"
              className="text-gray-700 border-gray-300 hover:bg-gray-50 w-full sm:w-auto"
              data-testid="button-manage-statuses"
            >
              <Settings className="w-4 h-4 ml-2" />
              ניהול סטטוסים
            </Button>
            <Button 
              onClick={() => setIsCreateModalOpen(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white w-full sm:w-auto"
              data-testid="button-add-lead"
            >
              <Plus className="w-4 h-4 ml-2" />
              ליד חדש
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="relative flex-1 sm:max-w-md">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="חפש לפי שם או טלפון..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10 text-right"
              data-testid="input-search-leads"
            />
          </div>
          
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 flex-wrap">
            <Select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value as LeadStatus | 'all')}
              data-testid="select-status-filter"
              className="w-full sm:w-auto min-w-[140px]"
            >
              <SelectOption value="all">כל הסטטוסים</SelectOption>
              {statuses.map(status => (
                <SelectOption key={status.id} value={status.name}>
                  {status.label}
                </SelectOption>
              ))}
            </Select>
            
            <Select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value as LeadSource | 'all')}
              data-testid="select-source-filter"
              className="w-full sm:w-auto min-w-[120px]"
            >
              <SelectOption value="all">כל המקורות</SelectOption>
              <SelectOption value="phone">טלפון</SelectOption>
              <SelectOption value="whatsapp">ווצאפ</SelectOption>
            </Select>
            
            <Select
              value={selectedDirection}
              onChange={(e) => setSelectedDirection(e.target.value as 'all' | 'inbound' | 'outbound')}
              data-testid="select-direction-filter"
              className="w-full sm:w-auto min-w-[140px]"
            >
              <SelectOption value="all">כל השיחות</SelectOption>
              <SelectOption value="inbound">נכנסות</SelectOption>
              <SelectOption value="outbound">יוצאות</SelectOption>
            </Select>
            
            {outboundLists.length > 0 && (
              <Select
                value={selectedOutboundList}
                onChange={(e) => setSelectedOutboundList(e.target.value)}
                data-testid="select-outbound-list-filter"
                className="w-full sm:w-auto min-w-[150px]"
              >
                <SelectOption value="all">כל רשימות היבוא</SelectOption>
                {outboundLists.map(list => (
                  <SelectOption key={list.id} value={list.id.toString()}>
                    {list.name}
                  </SelectOption>
                ))}
              </Select>
            )}
            
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm w-32"
                data-testid="input-date-from"
              />
              <span className="text-gray-500">עד</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm w-32"
                data-testid="input-date-to"
              />
              {(dateFrom || dateTo) && (
                <button
                  onClick={() => { setDateFrom(''); setDateTo(''); }}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="נקה תאריכים"
                  data-testid="button-clear-dates"
                >
                  <X className="w-4 h-4 text-gray-500" />
                </button>
              )}
            </div>
            
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 justify-center sm:justify-start">
              <Filter className="w-4 h-4" />
              {sortedLeads.length} לידים
            </div>
          </div>
        </div>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="p-6 border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20">
          <p className="text-red-600 dark:text-red-400 text-center">שגיאה בטעינת לידים: {error}</p>
        </Card>
      )}

      {/* Loading State - Skeleton */}
      {loading && (
        <Card className="hidden md:block" data-testid="loading-leads">
          <div className="divide-y divide-gray-100">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="p-4 flex items-center gap-4 animate-pulse">
                <div className="w-5 h-5 bg-gray-200 rounded"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                  <div className="h-3 bg-gray-100 rounded w-1/6"></div>
                </div>
                <div className="h-6 bg-gray-200 rounded-full w-16"></div>
                <div className="h-4 bg-gray-100 rounded w-20"></div>
                <div className="h-4 bg-gray-100 rounded w-24"></div>
                <div className="flex gap-2">
                  <div className="h-8 w-8 bg-gray-200 rounded"></div>
                  <div className="h-8 w-8 bg-gray-200 rounded"></div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      
      {/* Mobile Loading Skeleton */}
      {loading && (
        <div className="md:hidden space-y-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="p-4 animate-pulse">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-gray-200 rounded-full"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                  <div className="h-3 bg-gray-100 rounded w-1/3"></div>
                </div>
              </div>
              <div className="flex gap-2">
                <div className="h-8 bg-gray-200 rounded flex-1"></div>
                <div className="h-8 bg-gray-200 rounded flex-1"></div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Desktop Table - Hidden on Mobile */}
      {!loading && (
        <Card className="hidden md:block">
          <Table data-testid="table-leads">
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedLeadIds.size === sortedLeads.length && sortedLeads.length > 0}
                    onCheckedChange={handleToggleSelectAll}
                    data-testid="checkbox-select-all"
                  />
                </TableHead>
                <TableHead 
                  sortable 
                  onClick={() => handleSort('name')}
                  className="cursor-pointer"
                >
                  שם הליד
                  {sortBy === 'name' && (
                    <span className={sortOrder === 'asc' ? 'text-blue-600' : 'text-blue-600'}>
                      ↑↓
                    </span>
                  )}
                </TableHead>
                <TableHead>טלפון</TableHead>
                <TableHead 
                  sortable 
                  onClick={() => handleSort('status')}
                  className="cursor-pointer"
                >
                  סטטוס (לפי pipeline)
                  {sortBy === 'status' && (
                    <span className={sortOrder === 'asc' ? 'text-blue-600' : 'text-blue-600'}>
                      ↑↓
                    </span>
                  )}
                </TableHead>
                <TableHead>מקור</TableHead>
                <TableHead 
                  sortable 
                  onClick={() => handleSort('created_at')}
                  className="cursor-pointer"
                >
                  תאריך יצירה
                  {sortBy === 'created_at' && (
                    <span className={sortOrder === 'asc' ? 'text-blue-600' : 'text-blue-600'}>
                      ↑↓
                    </span>
                  )}
                </TableHead>
                <TableHead>פעולות</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedLeads.map((lead) => (
                <TableRow
                  key={lead.id}
                  data-testid={`row-lead-${lead.id}`}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer"
                  onClick={() => navigate(`/app/leads/${lead.id}`)}
                >
                  <TableCell className="w-12">
                    <div onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                      <Checkbox
                        checked={selectedLeadIds.has(lead.id)}
                        onCheckedChange={() => handleToggleSelect(lead.id)}
                        data-testid={`checkbox-lead-${lead.id}`}
                      />
                    </div>
                  </TableCell>
                  <TableCell data-testid={`text-name-${lead.id}`} className="min-w-[150px]">
                    <div className="font-medium text-gray-900 dark:text-white hover:text-blue-600 transition-colors">
                      {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || lead.display_phone || lead.phone_e164 || '—'}
                    </div>
                    {lead.email && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                        {safe(lead.email)}
                      </div>
                    )}
                  </TableCell>
                  
                  <TableCell data-testid={`text-phone-${lead.id}`} className="min-w-[120px]">
                    <div dir="ltr" className="text-right text-sm">
                      {lead.display_phone || lead.phone_e164 || lead.phone || 'ללא טלפון'}
                    </div>
                  </TableCell>
                  
                  <TableCell data-testid={`text-status-${lead.id}`} className="min-w-[130px]">
                    <div onClick={(e) => e.stopPropagation()}>
                      <StatusDropdown
                        currentStatus={lead.status}
                        statuses={statuses}
                        onStatusChange={(newStatus) => handleStatusChange(lead.id, newStatus as LeadStatus)}
                        size="sm"
                        data-testid={`status-dropdown-${lead.id}`}
                      />
                    </div>
                  </TableCell>
                  
                  <TableCell data-testid={`text-source-${lead.id}`} className="min-w-[90px]">
                    <Badge className={`text-xs px-2 py-1 ${
                      safe(lead.source) === 'whatsapp' 
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
                        : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    }`}>
                      {safe(lead.source) === 'whatsapp' ? 'ווצאפ' : 'טלפון'}
                    </Badge>
                  </TableCell>
                  
                  <TableCell data-testid={`text-created-${lead.id}`} className="min-w-[100px]">
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {new Date(lead.created_at).toLocaleDateString('he-IL')}
                    </div>
                  </TableCell>
                  
                  <TableCell className="min-w-[140px]">
                    {/* Mobile: Show text buttons, Desktop: Show icon buttons */}
                    <div className="hidden sm:flex items-center gap-1 justify-start flex-wrap">
                      {(lead.phone || lead.phone_e164 || lead.display_phone) && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleWhatsAppOpen(lead.phone || lead.phone_e164 || lead.display_phone || '');
                            }}
                            className="h-8 w-8 p-0 bg-green-500 text-white hover:bg-green-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                            data-testid={`button-whatsapp-${lead.id}`}
                            title="פתח שיחה בווצאפ"
                          >
                            <MessageSquare className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCall(lead.phone || lead.phone_e164 || lead.display_phone || '');
                            }}
                            className="h-8 w-8 p-0 bg-blue-500 text-white hover:bg-blue-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                            data-testid={`button-call-${lead.id}`}
                            title="התקשר ללקוח"
                          >
                            <Phone className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/app/leads/${lead.id}`);
                        }}
                        className="h-8 w-8 p-0 bg-purple-500 text-white hover:bg-purple-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                        data-testid={`button-details-${lead.id}`}
                        title="צפה בדף הלקוח המלא"
                      >
                        <User className="w-4 h-4" />
                      </button>
                      {/* ⚠️ BILLING DISABLED - Hidden until payments feature is activated */}
                      {/* <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/app/billing?leadId=${lead.id}`);
                        }}
                        className="h-8 w-8 p-0 bg-indigo-500 text-white hover:bg-indigo-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                        data-testid={`button-invoice-${lead.id}`}
                        title="הוצא חשבונית"
                      >
                        <Receipt className="w-4 h-4" />
                      </button> */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteLead(lead.id, lead.name || lead.full_name || `${lead.first_name} ${lead.last_name}`);
                        }}
                        className="h-8 w-8 p-0 bg-red-500 text-white hover:bg-red-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                        data-testid={`button-delete-${lead.id}`}
                        title="מחק ליד"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Mobile: Text buttons with labels */}
                    <div className="flex sm:hidden flex-col gap-1 w-full">
                      {(lead.phone || lead.phone_e164 || lead.display_phone) && (
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleWhatsAppOpen(lead.phone || lead.phone_e164 || lead.display_phone || '');
                            }}
                            className="flex-1 h-7 px-2 text-xs text-green-600 border-green-200 hover:bg-green-50"
                            data-testid={`button-whatsapp-mobile-${lead.id}`}
                          >
                            <MessageSquare className="w-3 h-3 ml-1" />
                            ווצאפ
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCall(lead.phone || lead.phone_e164 || lead.display_phone || '');
                            }}
                            className="flex-1 h-7 px-2 text-xs text-blue-600 border-blue-200 hover:bg-blue-50"
                            data-testid={`button-call-mobile-${lead.id}`}
                          >
                            <Phone className="w-3 h-3 ml-1" />
                            חייג
                          </Button>
                        </div>
                      )}
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/app/leads/${lead.id}`);
                          }}
                          className="flex-1 h-7 px-2 text-xs text-purple-600 border-purple-200 hover:bg-purple-50"
                          data-testid={`button-details-mobile-${lead.id}`}
                        >
                          <User className="w-3 h-3 ml-1" />
                          פרטים
                        </Button>
                        {/* ⚠️ BILLING DISABLED - Hidden until payments feature is activated */}
                        {/* <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/app/billing?leadId=${lead.id}`);
                          }}
                          className="flex-1 h-7 px-2 text-xs text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                          data-testid={`button-invoice-mobile-${lead.id}`}
                        >
                          <Receipt className="w-3 h-3 ml-1" />
                          חשבונית
                        </Button> */}
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteLead(lead.id, lead.name || lead.full_name || `${lead.first_name} ${lead.last_name}`);
                          }}
                          className="flex-1 h-7 px-2 text-xs text-red-600 border-red-200 hover:bg-red-50"
                          data-testid={`button-delete-mobile-${lead.id}`}
                        >
                          <Trash2 className="w-3 h-3 ml-1" />
                          מחק
                        </Button>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
              </Table>
          
          {sortedLeads.length === 0 && !loading && (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">אין לידים להציג</p>
              <Button
                onClick={() => setIsCreateModalOpen(true)}
                className="mt-4 bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Plus className="w-4 h-4 ml-2" />
                צור ליד ראשון
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Mobile Cards View - Hidden on Desktop */}
      {!loading && (
        <div className="md:hidden space-y-3">
          {/* Mobile Bulk Actions Bar */}
          {selectedLeadIds.size > 0 && (
            <div className="sticky top-0 z-20 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-5 h-5 text-red-600" />
                <span className="font-medium text-red-800">{selectedLeadIds.size} נבחרו</span>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setSelectedLeadIds(new Set())}
                  className="h-8 px-3 text-gray-600"
                  data-testid="button-cancel-selection-mobile"
                >
                  <X className="w-4 h-4 ml-1" />
                  בטל
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handleBulkDelete}
                  disabled={isDeleting}
                  className="h-8 px-3 bg-red-600 hover:bg-red-700 text-white"
                  data-testid="button-bulk-delete-mobile"
                >
                  <Trash2 className="w-4 h-4 ml-1" />
                  מחק
                </Button>
              </div>
            </div>
          )}

          {/* Select All for Mobile */}
          {sortedLeads.length > 0 && (
            <div className="flex items-center gap-2 px-2 py-2 bg-gray-50 rounded-lg">
              <Checkbox
                checked={selectedLeadIds.size === sortedLeads.length && sortedLeads.length > 0}
                onCheckedChange={handleToggleSelectAll}
                data-testid="checkbox-select-all-mobile"
              />
              <span className="text-sm text-gray-600">
                {selectedLeadIds.size === sortedLeads.length ? 'בטל בחירת הכל' : 'בחר הכל'}
              </span>
            </div>
          )}

          {sortedLeads.length === 0 ? (
            <Card className="p-8 text-center">
              <p className="text-gray-500 dark:text-gray-400" data-testid="no-leads-message">
                {searchQuery || selectedStatus !== 'all' ? 'אין לידים התואמים לחיפוש' : 'אין לידים עדיין'}
              </p>
            </Card>
          ) : (
            sortedLeads.map((lead) => (
              <div 
                key={lead.id} 
                className={`cursor-pointer hover:shadow-md transition-shadow ${selectedLeadIds.has(lead.id) ? 'ring-2 ring-blue-500' : ''}`}
                onClick={(e) => {
                  // Only navigate if we're not clicking on status badge, checkbox, or action buttons
                  if (!e.defaultPrevented) {
                    navigate(`/app/leads/${lead.id}`);
                  }
                }}
                data-testid={`card-lead-mobile-${lead.id}`}
              >
                <Card className="p-3 space-y-2">
                {/* Header: Checkbox, Name and Status */}
                <div className="flex items-start gap-2">
                  {/* Checkbox */}
                  <div 
                    className="flex-shrink-0 pt-1"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleToggleSelect(lead.id);
                    }}
                  >
                    <Checkbox
                      checked={selectedLeadIds.has(lead.id)}
                      onCheckedChange={() => handleToggleSelect(lead.id)}
                      data-testid={`checkbox-lead-mobile-${lead.id}`}
                    />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-0.5 truncate" data-testid={`text-name-mobile-${lead.id}`}>
                      {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || lead.display_phone || lead.phone_e164 || '—'}
                    </h3>
                    {lead.email && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate" data-testid={`text-email-mobile-${lead.id}`}>
                        {safe(lead.email)}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    <div onClick={(e) => e.stopPropagation()}>
                      <StatusDropdown
                        currentStatus={lead.status}
                        statuses={statuses}
                        onStatusChange={(newStatus) => handleStatusChange(lead.id, newStatus as LeadStatus)}
                        size="sm"
                        data-testid={`status-dropdown-mobile-${lead.id}`}
                      />
                    </div>
                  </div>
                </div>

                {/* Contact Info & Meta - Compact */}
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 px-6">
                  <div className="flex items-center gap-1" data-testid={`text-phone-mobile-${lead.id}`}>
                    <Phone className="w-3 h-3" />
                    <span dir="ltr">
                      {lead.display_phone || lead.phone_e164 || lead.phone || 'ללא טלפון'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span data-testid={`text-source-mobile-${lead.id}`} className={
                      safe(lead.source) === 'whatsapp' ? 'text-green-600' : 'text-blue-600'
                    }>
                      {safe(lead.source) === 'whatsapp' ? 'ווצאפ' : 'טלפון'}
                    </span>
                    <span data-testid={`text-created-mobile-${lead.id}`}>
                      {new Date(lead.created_at).toLocaleDateString('he-IL')}
                    </span>
                  </div>
                </div>

                {/* Action Buttons - Simplified: Only WhatsApp, Call, Delete */}
                <div className="flex gap-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                  {(lead.phone || lead.phone_e164 || lead.display_phone) && (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleWhatsAppOpen(lead.phone || lead.phone_e164 || lead.display_phone || '');
                        }}
                        className="flex-1 h-8 text-xs text-green-600 border-green-200 hover:bg-green-50"
                        data-testid={`button-whatsapp-mobile-${lead.id}`}
                      >
                        <MessageSquare className="w-3.5 h-3.5 ml-1" />
                        ווצאפ
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCall(lead.phone || lead.phone_e164 || lead.display_phone || '');
                        }}
                        className="flex-1 h-8 text-xs text-blue-600 border-blue-200 hover:bg-blue-50"
                        data-testid={`button-call-mobile-${lead.id}`}
                      >
                        <Phone className="w-3.5 h-3.5 ml-1" />
                        חייג
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteLead(lead.id, lead.name || lead.full_name || `${lead.first_name} ${lead.last_name}`);
                    }}
                    className="h-8 px-3 text-xs bg-red-600 hover:bg-red-700 text-white"
                    data-testid={`button-delete-card-mobile-${lead.id}`}
                  >
                    <Trash2 className="w-3.5 h-3.5 ml-1" />
                    מחק
                  </Button>
                </div>
                </Card>
              </div>
            ))
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-6 pb-4" data-testid="pagination-controls">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1 || loading}
            data-testid="button-prev-page"
          >
            <ChevronRight className="w-4 h-4" />
            הקודם
          </Button>
          
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>עמוד</span>
            <span className="font-medium text-gray-900">{currentPage}</span>
            <span>מתוך</span>
            <span className="font-medium text-gray-900">{totalPages}</span>
            <span className="text-gray-400">({total} לידים)</span>
          </div>
          
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages || loading}
            data-testid="button-next-page"
          >
            הבא
            <ChevronLeft className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Modals */}
      <LeadCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleLeadCreate}
      />
      
      <StatusManagementModal
        isOpen={isStatusModalOpen}
        onClose={() => {
          setIsStatusModalOpen(false);
          refreshStatuses();
        }}
        onStatusChange={() => {
          refreshStatuses();
        }}
      />
    </main>
  );
}