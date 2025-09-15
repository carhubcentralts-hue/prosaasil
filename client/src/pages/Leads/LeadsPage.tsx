import { useState, useEffect, useMemo } from 'react';
import { Plus, Search, Filter, MessageSquare, Edit, Phone, Trash2, Settings } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../shared/components/ui/Table';
import { Select, SelectOption } from '../../shared/components/ui/Select';
import LeadCreateModal from './components/LeadCreateModal';
import LeadDetailModal from './components/LeadDetailModal';
import StatusManagementModal from './components/StatusManagementModal';
import { useLeads } from './hooks/useLeads';
import { Lead, LeadStatus } from './types';
import { useStatuses } from '../../features/statuses/hooks';

// Dynamic statuses loaded from API

// Safe value helper function as per guidelines
const safe = (val: any, dash: string = '—'): string => {
  if (val === null || val === undefined || val === '') return dash;
  return String(val);
};

export default function LeadsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<LeadStatus | 'all'>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'created_at' | 'status'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [editingStatus, setEditingStatus] = useState<number | null>(null);
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  
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
      await updateLead(leadId, { status: newStatus });
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
    // ✅ Legacy compatibility: case-insensitive matching + fallback mapping
    let statusConfig = statuses.find(s => s.name.toLowerCase() === status.toLowerCase());
    
    // Fallback mapping for legacy capitalized statuses
    if (!statusConfig) {
      const legacyMapping: Record<string, string> = {
        'New': 'new',
        'Attempting': 'attempting', 
        'Contacted': 'contacted',
        'Qualified': 'qualified',
        'Won': 'won',
        'Lost': 'lost',
        'Unqualified': 'unqualified'
      };
      const normalizedStatus = legacyMapping[status] || status.toLowerCase();
      statusConfig = statuses.find(s => s.name === normalizedStatus);
    }
    
    return statusConfig?.color || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: LeadStatus): string => {
    // ✅ Legacy compatibility: case-insensitive matching + fallback mapping
    let statusConfig = statuses.find(s => s.name.toLowerCase() === status.toLowerCase());
    
    // Fallback mapping for legacy capitalized statuses
    if (!statusConfig) {
      const legacyMapping: Record<string, string> = {
        'New': 'new',
        'Attempting': 'attempting',
        'Contacted': 'contacted', 
        'Qualified': 'qualified',
        'Won': 'won',
        'Lost': 'lost',
        'Unqualified': 'unqualified'
      };
      const normalizedStatus = legacyMapping[status] || status.toLowerCase();
      statusConfig = statuses.find(s => s.name === normalizedStatus);
    }
    
    return statusConfig?.label || status;
  };

  const handleDeleteLead = async (leadId: number, leadName: string) => {
    const confirmed = window.confirm(`האם אתה בטוח שברצונך למחוק את הליד ${leadName}?`);
    if (!confirmed) return;
    
    try {
      await deleteLead(leadId);
      await refreshLeads();
    } catch (error) {
      console.error('Failed to delete lead:', error);
      alert('שגיאה במחיקת הליד');
    }
  };

  const handleLeadUpdate = async (updatedLead: Lead) => {
    try {
      await updateLead(updatedLead.id, updatedLead);
      await refreshLeads();
      setSelectedLead(null);
    } catch (error) {
      console.error('Failed to update lead:', error);
    }
  };

  const handleLeadCreate = async (leadData: Partial<Lead>) => {
    try {
      await createLead(leadData);
      await refreshLeads();
      setIsCreateModalOpen(false);
    } catch (error) {
      console.error('Failed to create lead:', error);
    }
  };

  return (
    <main className="container mx-auto px-4 pb-24 pt-2" dir="rtl">
      {/* Header - sticky top */}
      <div className="sticky top-[env(safe-area-inset-top)] z-30 bg-white/80 backdrop-blur -mx-4 px-4 py-3 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">לידים</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">ניהול ומעקב אחרי לידים בטבלה מקצועית</p>
          </div>
          <div className="flex items-center gap-3">
          <Button
            onClick={() => setIsStatusModalOpen(true)}
            variant="secondary"
            size="sm"
            className="text-gray-700 border-gray-300 hover:bg-gray-50"
            data-testid="button-manage-statuses"
          >
            <Settings className="w-4 h-4 ml-2" />
            ניהול סטטוסים
          </Button>
          <Button 
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
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
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="חפש לפי שם, טלפון או מייל..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10 text-right"
              data-testid="input-search-leads"
            />
          </div>
          
          <Select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value as LeadStatus | 'all')}
            data-testid="select-status-filter"
          >
            <SelectOption value="all">כל הסטטוסים</SelectOption>
            {statuses.map(status => (
              <SelectOption key={status.id} value={status.name}>
                {status.label}
              </SelectOption>
            ))}
          </Select>
          
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <Filter className="w-4 h-4" />
            {sortedLeads.length} לידים
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

      {/* Leads Table */}
      {!loading && (
        <Card>
          <Table data-testid="table-leads">
            <TableHeader>
              <TableRow>
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
                  onClick={() => window.location.href = `/app/leads/${lead.id}`}
                >
                  <TableCell data-testid={`text-name-${lead.id}`}>
                    <div className="font-medium text-gray-900 dark:text-white hover:text-blue-600 transition-colors">
                      {safe(lead.name) || safe(lead.full_name) || safe(`${lead.first_name || ''} ${lead.last_name || ''}`.trim()) || safe(lead.phone_e164)}
                    </div>
                    {lead.email && (
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {safe(lead.email)}
                      </div>
                    )}
                  </TableCell>
                  
                  <TableCell data-testid={`text-phone-${lead.id}`}>
                    <div dir="ltr" className="text-right">
                      {safe(lead.phone) || safe(lead.phone_e164) || safe(lead.display_phone, 'ללא טלפון')}
                    </div>
                  </TableCell>
                  
                  <TableCell data-testid={`text-status-${lead.id}`}>
                    {editingStatus === lead.id ? (
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
                    ) : (
                      <Badge 
                        className={`${getStatusColor(lead.status)} cursor-pointer hover:opacity-80`}
                        onClick={() => setEditingStatus(lead.id)}
                        data-testid={`badge-status-${lead.id}`}
                      >
                        {getStatusLabel(lead.status)}
                      </Badge>
                    )}
                  </TableCell>
                  
                  <TableCell data-testid={`text-source-${lead.id}`}>
                    <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200">
                      {safe(lead.source) === 'call' || safe(lead.source) === 'phone' ? 'טלפון' : 
                       safe(lead.source) === 'whatsapp' ? 'ווצאפ' :
                       safe(lead.source) === 'form' || safe(lead.source) === 'website' ? 'טופס' :
                       safe(lead.source) === 'manual' ? 'ידני' : safe(lead.source, 'לא ידוע')}
                    </Badge>
                  </TableCell>
                  
                  <TableCell data-testid={`text-created-${lead.id}`}>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {new Date(lead.created_at).toLocaleDateString('he-IL')}
                    </div>
                  </TableCell>
                  
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {(lead.phone || lead.phone_e164 || lead.display_phone) && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleWhatsAppOpen(lead.phone || lead.phone_e164 || lead.display_phone || '')}
                            className="h-7 w-7 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                            data-testid={`button-whatsapp-${lead.id}`}
                            title="פתח שיחה בווצאפ"
                          >
                            <MessageSquare className="w-3 h-3" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleCall(lead.phone || lead.phone_e164 || lead.display_phone || '')}
                            className="h-7 w-7 p-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                            data-testid={`button-call-${lead.id}`}
                            title="התקשר ללקוח"
                          >
                            <Phone className="w-3 h-3" />
                          </Button>
                        </>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedLead(lead)}
                        className="h-7 w-7 p-0 text-gray-600 hover:text-gray-700 hover:bg-gray-50"
                        data-testid={`button-edit-${lead.id}`}
                        title="ערוך ליד"
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDeleteLead(lead.id, lead.name || lead.full_name || `${lead.first_name} ${lead.last_name}`)}
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                        data-testid={`button-delete-${lead.id}`}
                        title="מחק ליד"
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
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