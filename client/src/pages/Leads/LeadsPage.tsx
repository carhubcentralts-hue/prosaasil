import { useState, useEffect } from 'react';
import { Plus, Search, Filter, MoreHorizontal } from 'lucide-react';
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  pointerWithin,
  useDroppable,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import LeadCard from './components/LeadCard';
import LeadCreateModal from './components/LeadCreateModal';
import LeadDetailModal from './components/LeadDetailModal';
import KanbanColumn from './components/KanbanColumn';
import { useLeads } from './hooks/useLeads';
import { Lead, LeadStatus } from './types';

const STATUSES: { key: LeadStatus; label: string; color: string }[] = [
  { key: 'New', label: 'חדש', color: 'bg-blue-100 text-blue-800' },
  { key: 'Attempting', label: 'בניסיון קשר', color: 'bg-yellow-100 text-yellow-800' },
  { key: 'Contacted', label: 'נוצר קשר', color: 'bg-purple-100 text-purple-800' },
  { key: 'Qualified', label: 'מוכשר', color: 'bg-green-100 text-green-800' },
  { key: 'Won', label: 'זכיה', color: 'bg-emerald-100 text-emerald-800' },
  { key: 'Lost', label: 'אובדן', color: 'bg-red-100 text-red-800' },
  { key: 'Unqualified', label: 'לא מוכשר', color: 'bg-gray-100 text-gray-800' },
];

export default function LeadsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<LeadStatus | 'all'>('all');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const {
    leads,
    loading,
    error,
    createLead,
    updateLead,
    moveLead,
    refreshLeads,
  } = useLeads({
    search: searchQuery,
    status: selectedStatus === 'all' ? undefined : selectedStatus,
  });

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Group leads by status
  const leadsByStatus = STATUSES.reduce((acc, status) => {
    acc[status.key] = leads.filter(lead => lead.status === status.key);
    return acc;
  }, {} as Record<LeadStatus, Lead[]>);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    
    if (!over) {
      setActiveId(null);
      return;
    }

    const activeId = active.id as string;
    const overId = over.id as string;

    // Find the lead being dragged
    const draggedLead = leads.find(lead => lead.id.toString() === activeId);
    if (!draggedLead) {
      setActiveId(null);
      return;
    }

    // Check if we're dropping on a status column (droppable container)
    const isDroppableContainer = overId.startsWith('droppable-status-');
    const isLeadCard = !isDroppableContainer;

    if (isDroppableContainer) {
      // Moving to a different status column
      const newStatus = overId.replace('droppable-status-', '') as LeadStatus;
      
      if (newStatus !== draggedLead.status) {
        const targetLeads = leadsByStatus[newStatus];
        const afterId = targetLeads.length > 0 ? targetLeads[targetLeads.length - 1].id : undefined;
        
        try {
          await moveLead(draggedLead.id, {
            status: newStatus,
            afterId,
          });
          await refreshLeads();
        } catch (error) {
          console.error('Failed to move lead:', error);
        }
      }
    } else if (isLeadCard) {
      // Handle drops on lead cards - both same column reordering and cross-column moves
      const targetLead = leads.find(lead => lead.id.toString() === overId);
      if (targetLead) {
        if (targetLead.status === draggedLead.status) {
          // Reordering within the same column
          const status = draggedLead.status;
          const statusLeads = leadsByStatus[status];
          const oldIndex = statusLeads.findIndex(lead => lead.id.toString() === activeId);
          const newIndex = statusLeads.findIndex(lead => lead.id.toString() === overId);

          if (oldIndex !== newIndex && oldIndex !== -1 && newIndex !== -1) {
            const reorderedLeads = arrayMove(statusLeads, oldIndex, newIndex);
            const beforeId = newIndex > 0 ? reorderedLeads[newIndex - 1].id : undefined;
            const afterId = newIndex < reorderedLeads.length - 1 ? reorderedLeads[newIndex + 1].id : undefined;

            try {
              await moveLead(draggedLead.id, {
                status,
                beforeId,
                afterId,
              });
              await refreshLeads();
            } catch (error) {
              console.error('Failed to reorder lead:', error);
            }
          }
        } else {
          // Cross-column move: move to target status and position relative to target lead
          const newStatus = targetLead.status;
          const targetStatusLeads = leadsByStatus[newStatus];
          const targetIndex = targetStatusLeads.findIndex(lead => lead.id === targetLead.id);
          
          // Place after the target lead
          const afterId = targetLead.id;
          const beforeId = targetIndex < targetStatusLeads.length - 1 ? 
            targetStatusLeads[targetIndex + 1].id : undefined;

          try {
            await moveLead(draggedLead.id, {
              status: newStatus,
              beforeId,
              afterId,
            });
            await refreshLeads();
          } catch (error) {
            console.error('Failed to move lead to new status:', error);
          }
        }
      }
    }

    setActiveId(null);
  };

  const handleLeadClick = (lead: Lead) => {
    setSelectedLead(lead);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">טוען לידים...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-red-600">שגיאה בטעינת לידים: {error}</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">ניהול לידים</h1>
        <Button onClick={() => setIsCreateModalOpen(true)} data-testid="button-add-lead">
          <Plus className="w-4 h-4 ml-2" />
          הוסף ליד חדש
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="חפש לפי שם, טלפון או מייל..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pr-10"
            data-testid="input-search-leads"
          />
        </div>
        
        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value as LeadStatus | 'all')}
          className="px-3 py-2 border rounded-md bg-white"
          data-testid="select-status-filter"
        >
          <option value="all">כל הסטטוסים</option>
          {STATUSES.map(status => (
            <option key={status.key} value={status.key}>
              {status.label}
            </option>
          ))}
        </select>

        <Button variant="secondary" size="sm">
          <Filter className="w-4 h-4 ml-2" />
          פילטרים נוספים
        </Button>
      </div>

      {/* Kanban Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-6 min-h-[600px]">
          {STATUSES.map((status) => {
            const statusLeads = leadsByStatus[status.key];
            
            return (
              <KanbanColumn
                key={status.key}
                status={status}
                leads={statusLeads}
                onLeadClick={handleLeadClick}
                activeId={activeId}
              />
            );
          })}
        </div>
      </DndContext>

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
    </div>
  );
}