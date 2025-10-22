import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Filter, MessageSquare, Edit, Phone, Trash2, Settings, User, CheckSquare, Receipt } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Checkbox } from '../../shared/components/ui/Checkbox';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../shared/components/ui/Table';
import { Select, SelectOption } from '../../shared/components/ui/Select';
import LeadCreateModal from './components/LeadCreateModal';
import LeadDetailModal from './components/LeadDetailModal';
import StatusManagementModal from './components/StatusManagementModal';
import { useLeads } from './hooks/useLeads';
import { Lead, LeadStatus } from './types';
import { useStatuses } from '../../features/statuses/hooks';
import { http } from '../../services/http';

// Dynamic statuses loaded from API

// Safe value helper function as per guidelines
const safe = (val: any, dash: string = '—'): string => {
  if (val === null || val === undefined || val === '') return dash;
  return String(val);
};

export default function LeadsPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<LeadStatus | 'all'>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'created_at' | 'status'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [editingStatus, setEditingStatus] = useState<number | null>(null);
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Load dynamic statuses
  const { statuses, refreshStatuses } = useStatuses();

  // Load statuses on component mount
  useEffect(() => {
    refreshStatuses();
  }, [refreshStatuses]);

  // Memoize filters to prevent infinite loop
  const filters = useMemo(() => ({
    search: searchQuery,
    status: selectedStatus === 'all' ? undefined : selectedStatus,
  }), [searchQuery, selectedStatus]);

  const {
    leads,
    loading,
    error,
    createLead,
    updateLead,
    deleteLead,
    refreshLeads,
  } = useLeads(filters);

  // Sort and filter leads
  const sortedLeads = useMemo(() => {
    const statusOrder = statuses.reduce((acc, status, index) => {
      acc[status.name] = index;
      // ✅ Legacy compatibility: Add case-insensitive mappings
      acc[status.name.toLowerCase()] = index;
      return acc;
    }, {} as Record<string, number>);
    
    // ✅ Legacy fallback mapping for capitalized statuses
    const legacyMapping: Record<string, string> = {
      'New': 'new',
      'Attempting': 'attempting',
      'Contacted': 'contacted',
      'Qualified': 'qualified', 
      'Won': 'won',
      'Lost': 'lost',
      'Unqualified': 'unqualified'
    };

    const sorted = [...leads].sort((a, b) => {
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
  }, [leads, sortBy, sortOrder, statuses]);

  const handleSort = (column: 'name' | 'created_at' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const handleStatusChange = async (leadId: number, newStatus: LeadStatus) => {
    try {
      // Use the specific status update endpoint
      await http.put(`/api/leads/${leadId}/status`, { status: newStatus });
      await refreshLeads();
      setEditingStatus(null);
    } catch (error) {
      console.error('Failed to update lead status:', error);
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

  const getStatusColor = (status: LeadStatus): string => {
    // Simple synchronous color mapping
    const colorMap: Record<string, string> = {
      'new': 'bg-blue-100 text-blue-800',
      'attempting': 'bg-yellow-100 text-yellow-800',
      'contacted': 'bg-purple-100 text-purple-800',
      'qualified': 'bg-green-100 text-green-800',
      'won': 'bg-emerald-100 text-emerald-800',
      'lost': 'bg-red-100 text-red-800',
      'unqualified': 'bg-gray-100 text-gray-800',
      // Legacy capitalized mappings
      'New': 'bg-blue-100 text-blue-800',
      'Attempting': 'bg-yellow-100 text-yellow-800',
      'Contacted': 'bg-purple-100 text-purple-800',
      'Qualified': 'bg-green-100 text-green-800',
      'Won': 'bg-emerald-100 text-emerald-800',
      'Lost': 'bg-red-100 text-red-800',
      'Unqualified': 'bg-gray-100 text-gray-800'
    };
    
    return colorMap[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: LeadStatus): string => {
    // Simple synchronous label mapping
    const labelMap: Record<string, string> = {
      'new': 'חדש',
      'attempting': 'מנסה ליצור קשר',
      'contacted': 'יצרנו קשר',
      'qualified': 'מתאים',
      'won': 'נצחנו',
      'lost': 'איבדנו',
      'unqualified': 'לא מתאים',
      // Legacy capitalized mappings
      'New': 'חדש',
      'Attempting': 'מנסה ליצור קשר',
      'Contacted': 'יצרנו קשר',
      'Qualified': 'מתאים',
      'Won': 'נצחנו',
      'Lost': 'איבדנו',
      'Unqualified': 'לא מתאים'
    };
    
    return labelMap[status] || status;
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

  const handleLeadUpdate = async (updatedLead: Lead) => {
    try {
      await updateLead(updatedLead.id, updatedLead);
      // ✅ FIX: updateLead already updates state with response
      setSelectedLead(null);
    } catch (error) {
      console.error('Failed to update lead:', error);
      alert('שגיאה בעדכון הליד');
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
      await http.post('/api/leads/bulk-delete', {
        lead_ids: Array.from(selectedLeadIds)
      });
      
      setSelectedLeadIds(new Set());
      refreshLeads();
    } catch (error) {
      console.error('Failed to bulk delete leads:', error);
      alert('שגיאה במחיקת לידים');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <main className="container mx-auto px-2 sm:px-4 pb-24 pt-2 max-w-full" dir="rtl">
      {/* Header - sticky top */}
      <div className="sticky top-[env(safe-area-inset-top)] z-30 bg-white/80 backdrop-blur -mx-2 sm:-mx-4 px-2 sm:px-4 py-3 mb-6">
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
              placeholder="חפש לפי שם, טלפון או מייל..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10 text-right"
              data-testid="input-search-leads"
            />
          </div>
          
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
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

      {/* Loading State */}
      {loading && (
        <Card className="p-12 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="text-gray-600 dark:text-gray-400 mt-4" data-testid="loading-leads">טוען לידים...</p>
        </Card>
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
                      {safe(lead.name) || safe(lead.full_name) || safe(`${lead.first_name || ''} ${lead.last_name || ''}`.trim()) || safe(lead.phone_e164)}
                    </div>
                    {lead.email && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                        {safe(lead.email)}
                      </div>
                    )}
                  </TableCell>
                  
                  <TableCell data-testid={`text-phone-${lead.id}`} className="min-w-[120px]">
                    <div dir="ltr" className="text-right text-sm">
                      {safe(lead.phone) || safe(lead.phone_e164) || safe(lead.display_phone, 'ללא טלפון')}
                    </div>
                  </TableCell>
                  
                  <TableCell data-testid={`text-status-${lead.id}`} className="min-w-[130px]">
                    {editingStatus === lead.id ? (
                      <div onClick={(e) => e.stopPropagation()}>
                        <Select
                          value={lead.status}
                          onChange={(e) => handleStatusChange(lead.id, e.target.value as LeadStatus)}
                          onBlur={() => setEditingStatus(null)}
                          className="w-32"
                          data-testid={`select-status-${lead.id}`}
                          autoFocus
                        >
                          {statuses.map(status => (
                            <SelectOption key={status.id} value={status.name}>
                              {status.label}
                            </SelectOption>
                          ))}
                        </Select>
                      </div>
                    ) : (
                      <div className="relative group flex items-center gap-2">
                        <div 
                          className={`${getStatusColor(lead.status)} cursor-pointer hover:opacity-80 hover:scale-105 text-xs px-3 py-1.5 transition-all duration-200 hover:ring-2 hover:ring-blue-400 hover:shadow-md rounded-full inline-flex items-center gap-1.5 font-medium`}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Status badge clicked for lead', lead.id);
                            setEditingStatus(lead.id);
                          }}
                          data-testid={`badge-status-${lead.id}`}
                          role="button"
                          tabIndex={0}
                        >
                          {getStatusLabel(lead.status)}
                          <Edit className="w-3 h-3 opacity-70" />
                        </div>
                        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-1.5 bg-gray-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10 whitespace-nowrap pointer-events-none shadow-lg">
                          לחץ לשינוי סטטוס
                        </div>
                      </div>
                    )}
                  </TableCell>
                  
                  <TableCell data-testid={`text-source-${lead.id}`} className="min-w-[90px]">
                    <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 text-xs px-2 py-1">
                      {safe(lead.source) === 'call' || safe(lead.source) === 'phone' ? 'טלפון' : 
                       safe(lead.source) === 'whatsapp' ? 'ווצאפ' :
                       safe(lead.source) === 'form' || safe(lead.source) === 'website' ? 'טופס' :
                       safe(lead.source) === 'manual' ? 'ידני' : safe(lead.source, 'לא ידוע')}
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
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/app/billing?leadId=${lead.id}`);
                        }}
                        className="h-8 w-8 p-0 bg-indigo-500 text-white hover:bg-indigo-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                        data-testid={`button-invoice-${lead.id}`}
                        title="הוצא חשבונית"
                      >
                        <Receipt className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedLead(lead);
                        }}
                        className="h-8 w-8 p-0 bg-gray-500 text-white hover:bg-gray-600 border-0 rounded-md shadow-sm inline-flex items-center justify-center transition-colors"
                        data-testid={`button-edit-${lead.id}`}
                        title="ערוך ליד"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
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
                        <Button
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
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedLead(lead);
                          }}
                          className="flex-1 h-7 px-2 text-xs text-gray-600 border-gray-200 hover:bg-gray-50"
                          data-testid={`button-edit-mobile-${lead.id}`}
                        >
                          <Edit className="w-3 h-3 ml-1" />
                          ערוך
                        </Button>
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
        <div className="md:hidden space-y-4">
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
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={(e) => {
                  // Only navigate if we're not clicking on status badge or action buttons
                  if (!e.defaultPrevented && editingStatus !== lead.id) {
                    setSelectedLead(lead);
                  }
                }}
                data-testid={`card-lead-mobile-${lead.id}`}
              >
                <Card className="p-4 space-y-3">
                {/* Header: Name and Status */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 dark:text-white text-base mb-1 truncate" data-testid={`text-name-mobile-${lead.id}`}>
                      {safe(lead.name) || safe(lead.full_name) || safe(`${lead.first_name || ''} ${lead.last_name || ''}`.trim()) || safe(lead.phone_e164)}
                    </h3>
                    {lead.email && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 truncate" data-testid={`text-email-mobile-${lead.id}`}>
                        {safe(lead.email)}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    <div onClick={(e) => e.stopPropagation()}>
                      {editingStatus === lead.id ? (
                        <Select
                          value={lead.status}
                          onChange={(e) => handleStatusChange(lead.id, e.target.value as LeadStatus)}
                          onBlur={() => setEditingStatus(null)}
                          className="w-32 text-xs"
                          data-testid={`select-status-mobile-${lead.id}`}
                          autoFocus
                        >
                          {statuses.map(status => (
                            <SelectOption key={status.id} value={status.name}>
                              {status.label}
                            </SelectOption>
                          ))}
                        </Select>
                      ) : (
                        <div className="relative group">
                          <div className="flex items-center gap-2">
                            <div 
                              className={`${getStatusColor(lead.status)} cursor-pointer hover:opacity-80 text-xs px-3 py-2 transition-all duration-200 rounded-full inline-flex items-center font-medium`}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                console.log('Mobile status badge clicked for lead', lead.id);
                                setEditingStatus(lead.id);
                              }}
                              data-testid={`badge-status-mobile-${lead.id}`}
                              role="button"
                              tabIndex={0}
                            >
                              {getStatusLabel(lead.status)}
                            </div>
                            <span className="text-xs text-gray-400">לחץ לעריכה</span>
                          </div>
                          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-black text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10 whitespace-nowrap pointer-events-none">
                            לחץ לשינוי סטטוס
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-2" data-testid={`text-phone-mobile-${lead.id}`}>
                    <Phone className="w-4 h-4 text-gray-400" />
                    <span dir="ltr" className="text-gray-700 dark:text-gray-300">
                      {safe(lead.phone) || safe(lead.phone_e164) || safe(lead.display_phone, 'ללא טלפון')}
                    </span>
                  </div>
                </div>

                {/* Meta Info */}
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <div className="flex items-center gap-4">
                    <span data-testid={`text-source-mobile-${lead.id}`}>
                      מקור: {safe(lead.source) === 'call' || safe(lead.source) === 'phone' ? 'טלפון' : 
                            safe(lead.source) === 'whatsapp' ? 'ווצאפ' :
                            safe(lead.source) === 'form' || safe(lead.source) === 'website' ? 'טופס' :
                            safe(lead.source) === 'manual' ? 'ידני' : safe(lead.source, 'לא ידוע')}
                    </span>
                    <span data-testid={`text-created-mobile-${lead.id}`}>
                      {new Date(lead.created_at).toLocaleDateString('he-IL')}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
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
                        className="flex-1 h-9 text-green-600 border-green-200 hover:bg-green-50"
                        data-testid={`button-whatsapp-mobile-${lead.id}`}
                      >
                        <MessageSquare className="w-4 h-4 ml-1" />
                        ווצאפ
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCall(lead.phone || lead.phone_e164 || lead.display_phone || '');
                        }}
                        className="flex-1 h-9 text-blue-600 border-blue-200 hover:bg-blue-50"
                        data-testid={`button-call-mobile-${lead.id}`}
                      >
                        <Phone className="w-4 h-4 ml-1" />
                        חייג
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/app/leads/${lead.id}`);
                    }}
                    className="flex-1 h-9 text-purple-600 border-purple-200 hover:bg-purple-50"
                    data-testid={`button-details-fullpage-mobile-${lead.id}`}
                  >
                    <User className="w-4 h-4 ml-1" />
                    צפה בלקוח
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedLead(lead);
                    }}
                    className="flex-1 h-9 text-gray-600 border-gray-200 hover:bg-gray-50"
                    data-testid={`button-edit-mobile-${lead.id}`}
                  >
                    <Edit className="w-4 h-4 ml-1" />
                    ערוך
                  </Button>
                </div>
                </Card>
              </div>
            ))
          )}
        </div>
      )}

      {/* Modals */}
      <LeadCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleLeadCreate}
      />

      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          isOpen={!!selectedLead}
          onClose={() => setSelectedLead(null)}
          onUpdate={handleLeadUpdate}
        />
      )}
      
      <StatusManagementModal
        isOpen={isStatusModalOpen}
        onClose={() => {
          setIsStatusModalOpen(false);
          refreshStatuses(); // Refresh statuses when modal closes
        }}
      />
    </main>
  );
}