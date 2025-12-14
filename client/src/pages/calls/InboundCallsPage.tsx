import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Phone, Loader2, Search, LayoutGrid, List, CheckSquare } from 'lucide-react';
import { http } from '../../services/http';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { LeadKanbanView } from '../Leads/components/LeadKanbanView';
import LeadCard from '../Leads/components/LeadCard';

// Lead interface aligned with main Leads page
interface Lead {
  id: number;
  full_name: string;
  first_name?: string;
  last_name?: string;
  phone_e164: string;
  display_phone: string;
  email?: string;
  status: string;
  source: string;
  summary?: string;
  notes?: string;
  tags?: string[];
  last_contact_at: string;
  created_at: string;
  owner_user_id?: number;
  last_call_direction?: string;
}

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

type ViewMode = 'kanban' | 'list';

export function InboundCallsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const pageSize = 25;

  // Fetch lead statuses for Kanban
  const { data: statusesData, isLoading: statusesLoading } = useQuery<LeadStatus[]>({
    queryKey: ['/api/lead-statuses'],
    enabled: viewMode === 'kanban',
    retry: 1,
  });

  // Fetch inbound leads
  const { data: leadsResponse, isLoading: leadsLoading, error } = useQuery({
    queryKey: ['/api/leads', 'inbound', page, searchQuery],
    queryFn: async () => {
      const params = new URLSearchParams({
        direction: 'inbound',
        page: page.toString(),
        pageSize: pageSize.toString(),
      });
      
      if (searchQuery) {
        params.append('q', searchQuery);
      }

      return await http.get(`/api/leads?${params.toString()}`);
    },
    retry: 1,
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ leadId, newStatus }: { leadId: number; newStatus: string }) => {
      return await http.patch(`/api/leads/${leadId}/status`, { status: newStatus });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['/api/leads'] });
    },
  });

  const leads: Lead[] = (leadsResponse as any)?.items || [];
  const total = (leadsResponse as any)?.total || 0;
  const totalPages = Math.ceil(total / pageSize);
  const statuses = statusesData || [];

  const handleLeadClick = (leadId: number) => {
    navigate(`/app/leads/${leadId}`);
  };

  const handleLeadSelect = (leadId: number) => {
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

  const handleSelectMany = (leadIds: number[]) => {
    setSelectedLeadIds(new Set(leadIds));
  };

  const handleClearSelection = () => {
    setSelectedLeadIds(new Set());
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    await updateStatusMutation.mutateAsync({ leadId, newStatus });
  };

  const loading = leadsLoading || statusesLoading;

  if (loading && leads.length === 0) {
    return (
      <div className="flex items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-100 rounded-full">
            <Phone className="h-6 w-6 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">שיחות נכנסות</h1>
            <p className="text-slate-600 mt-1">לידים שמקורם משיחות נכנסות</p>
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode('kanban')}
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
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === 'list'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="button-list-view"
            >
              <List className="h-4 w-4" />
              רשימה
            </button>
          </div>
          
          {selectedLeadIds.size > 0 && (
            <div className="flex items-center gap-2 bg-blue-50 px-4 py-2 rounded-lg">
              <CheckSquare className="h-4 w-4 text-blue-600" />
              <span className="text-sm text-blue-900">
                {selectedLeadIds.size} נבחרו
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 z-10" />
          <Input
            type="search"
            placeholder="חפש לפי שם או טלפון..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full pl-3 pr-10"
            data-testid="input-search-inbound"
          />
        </div>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-red-800">שגיאה בטעינת הנתונים. אנא רענן את הדף.</p>
        </Card>
      )}

      {/* Empty State */}
      {!loading && leads.length === 0 && (
        <Card className="p-12 text-center">
          <Phone className="h-12 w-12 mx-auto mb-4 text-slate-400" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">אין שיחות נכנסות</h3>
          <p className="text-slate-600">
            {searchQuery ? 'לא נמצאו לידים התואמים לחיפוש' : 'עדיין לא היו שיחות נכנסות במערכת'}
          </p>
        </Card>
      )}

      {/* Kanban View */}
      {!loading && leads.length > 0 && viewMode === 'kanban' && (
        <div className="min-h-[600px]">
          <LeadKanbanView
            leads={leads}
            statuses={statuses}
            loading={loading}
            selectedLeadIds={selectedLeadIds}
            onLeadSelect={handleLeadSelect}
            onLeadClick={handleLeadClick}
            onStatusChange={handleStatusChange}
            onSelectMany={handleSelectMany}
            onClearSelection={handleClearSelection}
          />
        </div>
      )}

      {/* List View */}
      {!loading && leads.length > 0 && viewMode === 'list' && (
        <div className="grid grid-cols-1 gap-4">
          {leads.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              onClick={() => handleLeadClick(lead.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <Button
            variant="secondary"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            data-testid="button-prev-page"
          >
            הקודם
          </Button>
          <span className="text-sm text-slate-600">
            עמוד {page} מתוך {totalPages}
          </span>
          <Button
            variant="secondary"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            data-testid="button-next-page"
          >
            הבא
          </Button>
        </div>
      )}
    </div>
  );
}

export default InboundCallsPage;
