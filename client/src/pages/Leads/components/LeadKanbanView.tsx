import React, { useState, useMemo } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy
} from '@dnd-kit/sortable';
import { Lead } from '../types';
import { LeadKanbanCard } from './LeadKanbanCard';
import { LeadKanbanColumn } from './LeadKanbanColumn';
import { Loader2 } from 'lucide-react';

export interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

interface LeadKanbanViewProps {
  leads: Lead[];
  statuses: LeadStatus[];
  loading: boolean;
  selectedLeadIds: Set<number>;
  onLeadSelect: (leadId: number) => void;
  onLeadClick: (leadId: number) => void;
  onStatusChange: (leadId: number, newStatus: string) => Promise<void>;
  onSelectMany?: (leadIds: number[]) => void;
  onClearSelection?: () => void;
}

export function LeadKanbanView({
  leads,
  statuses,
  loading,
  selectedLeadIds,
  onLeadSelect,
  onLeadClick,
  onStatusChange,
  onSelectMany,
  onClearSelection
}: LeadKanbanViewProps) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Group leads by status
  const leadsByStatus = useMemo(() => {
    const grouped: Record<string, Lead[]> = {};
    
    // Initialize all statuses with empty arrays
    statuses.forEach(status => {
      grouped[status.name] = [];
    });
    
    // Group leads
    leads.forEach(lead => {
      const status = lead.status?.toLowerCase() || 'new';
      if (grouped[status]) {
        grouped[status].push(lead);
      } else {
        // Fallback to 'new' if status not found
        if (grouped['new']) {
          grouped['new'].push(lead);
        }
      }
    });
    
    return grouped;
  }, [leads, statuses]);

  const activeLead = useMemo(() => {
    if (!activeId) return null;
    return leads.find(lead => lead.id === activeId) || null;
  }, [activeId, leads]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as number);
    setIsDragging(true);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    
    setActiveId(null);
    setIsDragging(false);

    if (!over) return;

    const leadId = active.id as number;
    const newStatus = over.id as string;
    
    const lead = leads.find(l => l.id === leadId);
    if (!lead) return;

    // Only update if status actually changed
    if (lead.status?.toLowerCase() === newStatus.toLowerCase()) {
      return;
    }

    // Call the parent's status change handler (optimistic update handled there)
    await onStatusChange(leadId, newStatus);
  };

  if (loading && leads.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4 min-h-[600px]">
        {statuses.map((status) => {
          const statusLeads = leadsByStatus[status.name] || [];
          const leadIds = statusLeads.map(lead => lead.id);

          return (
            <LeadKanbanColumn
              key={status.name}
              status={status}
              leads={statusLeads}
              isDraggingOver={isDragging}
              selectedLeadIds={selectedLeadIds}
              onSelectAll={onSelectMany}
              onClearSelection={() => {
                // Clear only this column's leads
                if (onClearSelection) {
                  const idsToKeep = Array.from(selectedLeadIds).filter(id => 
                    !leadIds.includes(id)
                  );
                  if (idsToKeep.length === 0) {
                    onClearSelection();
                  } else if (onSelectMany) {
                    onSelectMany(idsToKeep);
                  }
                }
              }}
            >
              <SortableContext
                items={leadIds}
                strategy={verticalListSortingStrategy}
              >
                {statusLeads.map((lead) => (
                  <LeadKanbanCard
                    key={lead.id}
                    lead={lead}
                    isSelected={selectedLeadIds.has(lead.id)}
                    onSelect={onLeadSelect}
                    onClick={onLeadClick}
                  />
                ))}
              </SortableContext>
            </LeadKanbanColumn>
          );
        })}
      </div>

      <DragOverlay>
        {activeId && activeLead ? (
          <div className="rotate-3 opacity-90">
            <LeadKanbanCard
              lead={activeLead}
              isSelected={selectedLeadIds.has(activeId)}
              onSelect={() => {}}
              onClick={() => {}}
              isDragOverlay
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
