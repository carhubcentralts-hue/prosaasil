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
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { OutboundLeadCard } from './OutboundLeadCard';
import { OutboundKanbanColumn } from './OutboundKanbanColumn';

interface Lead {
  id: number;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  phone_e164: string;
  status: string;
  summary?: string;
  last_contact_at?: string;
  outbound_list_id?: number;
}

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

interface OutboundKanbanViewProps {
  leads: Lead[];
  statuses: LeadStatus[];
  loading: boolean;
  selectedLeadIds: Set<number>;
  onLeadSelect: (leadId: number, isShiftKey?: boolean) => void;
  onLeadClick?: (leadId: number) => void;
  onStatusChange?: (leadId: number, newStatus: string) => Promise<void>;
  onSelectAll?: (leadIds: number[]) => void;
  onClearSelection?: () => void;
  updatingStatusLeadId?: number;
}

export function OutboundKanbanView({
  leads,
  statuses,
  loading,
  selectedLeadIds,
  onLeadSelect,
  onLeadClick,
  onStatusChange,
  onSelectAll,
  onClearSelection,
  updatingStatusLeadId
}: OutboundKanbanViewProps) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [mobileColumnIndex, setMobileColumnIndex] = useState(0); // For mobile column pager
  const topScrollRef = React.useRef<HTMLDivElement>(null);
  const kanbanScrollRef = React.useRef<HTMLDivElement>(null);
  const isSyncingRef = React.useRef(false);

  // Detect mobile view
  const [isMobile, setIsMobile] = useState(false);
  
  React.useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768); // md breakpoint
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Synchronize scrolling between top scrollbar and kanban
  React.useEffect(() => {
    const topScroll = topScrollRef.current;
    const kanbanScroll = kanbanScrollRef.current;
    
    if (!topScroll || !kanbanScroll) return;

    const handleTopScroll = () => {
      if (isSyncingRef.current) return;
      isSyncingRef.current = true;
      kanbanScroll.scrollLeft = topScroll.scrollLeft;
      setTimeout(() => { isSyncingRef.current = false; }, 0);
    };

    const handleKanbanScroll = () => {
      if (isSyncingRef.current) return;
      isSyncingRef.current = true;
      topScroll.scrollLeft = kanbanScroll.scrollLeft;
      setTimeout(() => { isSyncingRef.current = false; }, 0);
    };

    topScroll.addEventListener('scroll', handleTopScroll);
    kanbanScroll.addEventListener('scroll', handleKanbanScroll);

    return () => {
      topScroll.removeEventListener('scroll', handleTopScroll);
      kanbanScroll.removeEventListener('scroll', handleKanbanScroll);
    };
  }, []);

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

    if (!over || !onStatusChange || isUpdating) return;

    const leadId = active.id as number;
    const newStatusName = String(over.id); // This is the status.name from the column
    
    const lead = leads.find(l => l.id === leadId);
    if (!lead) {
      console.error(`❌ OutboundKanban: Lead ${leadId} not found`);
      return;
    }

    // Only update if status actually changed
    // Both values should be compared in their original case (status names are lowercase like 'new', 'contacted', etc.)
    const currentStatus = (lead.status || 'new').toLowerCase();
    const targetStatus = newStatusName.toLowerCase();
    
    console.log(`🔵 OutboundKanban: Drag ended - lead ${leadId} from '${currentStatus}' to '${targetStatus}'`);
    
    if (currentStatus === targetStatus) {
      console.log(`⏭️ OutboundKanban: Status unchanged, skipping update`);
      return;
    }

    try {
      setIsUpdating(true);
      console.log(`🔄 OutboundKanban: Calling onStatusChange for lead ${leadId} to '${newStatusName}'`);
      // Call the status change handler with the original status name (not lowercase)
      await onStatusChange(leadId, newStatusName);
      console.log(`✅ OutboundKanban: Successfully moved lead ${leadId} to ${newStatusName}`);
    } catch (error) {
      console.error(`❌ OutboundKanban: Failed to move lead ${leadId}:`, error);
    } finally {
      setIsUpdating(false);
    }
  };

  if (loading && leads.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  // Calculate total width for scrollbar based on number of columns
  const contentWidth = statuses.length * 320; // Each column is approximately 320px wide

  // Mobile column pager mode
  if (isMobile && statuses.length > 0) {
    const currentStatus = statuses[mobileColumnIndex];
    const statusLeads = currentStatus ? (leadsByStatus[currentStatus.name] || []) : [];
    const leadIds = statusLeads.map(lead => lead.id);

    const handleSelectAllInCurrentStatus = async () => {
      if (onSelectAll) {
        // Call onSelectAll with all lead IDs in the current status
        onSelectAll(leadIds);
      }
    };

    return (
      <div className="space-y-4">
        {/* Mobile status navigation */}
        <div className="flex items-center justify-between gap-2 bg-white p-4 rounded-lg border border-gray-200">
          {/* Previous button - in RTL, previous is to the right, so use ChevronRight */}
          <button
            onClick={() => setMobileColumnIndex(prev => Math.max(0, prev - 1))}
            disabled={mobileColumnIndex === 0}
            className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="עמודה קודמת"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          
          <div className="flex-1 text-center">
            <div className="font-semibold text-lg">{currentStatus?.label || ''}</div>
            <div className="text-sm text-gray-500">
              {mobileColumnIndex + 1} מתוך {statuses.length} • {statusLeads.length} לידים
            </div>
          </div>
          
          {/* Next button - in RTL, next is to the left, so use ChevronLeft */}
          <button
            onClick={() => setMobileColumnIndex(prev => Math.min(statuses.length - 1, prev + 1))}
            disabled={mobileColumnIndex === statuses.length - 1}
            className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="עמודה הבאה"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>

        {/* "Select all in this status" button */}
        {statusLeads.length > 0 && onSelectAll && (
          <div className="flex justify-center">
            <button
              onClick={handleSelectAllInCurrentStatus}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              data-testid="button-select-all-in-status-mobile"
            >
              בחר את כל הלידים בסטטוס: {currentStatus?.label || ''} ({statusLeads.length})
            </button>
          </div>
        )}

        {/* Status indicator dots */}
        <div className="flex justify-center gap-2">
          {statuses.map((status, index) => (
            <button
              key={status.name}
              onClick={() => setMobileColumnIndex(index)}
              className={`w-2 h-2 rounded-full transition-all ${
                index === mobileColumnIndex 
                  ? 'bg-blue-600 w-8' 
                  : 'bg-gray-300 hover:bg-gray-400'
              }`}
              aria-label={`עבור ל-${status.label}`}
            />
          ))}
        </div>

        {/* Lead cards for current status */}
        <div className="space-y-2 pb-4">
          {statusLeads.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              אין לידים בסטטוס זה
            </div>
          ) : (
            <SortableContext
              items={leadIds}
              strategy={verticalListSortingStrategy}
            >
              {statusLeads.map((lead) => (
                <OutboundLeadCard
                  key={lead.id}
                  lead={lead}
                  isSelected={selectedLeadIds.has(lead.id)}
                  onSelect={onLeadSelect}
                  onClick={onLeadClick}
                  statuses={statuses}
                  onStatusChange={onStatusChange}
                  isUpdatingStatus={updatingStatusLeadId === lead.id}
                />
              ))}
            </SortableContext>
          )}
        </div>
      </div>
    );
  }

  // Desktop kanban view
  return (
    <>
      {/* Top horizontal scrollbar */}
      <div 
        ref={topScrollRef}
        className="overflow-x-auto overflow-y-hidden mb-2"
        style={{ height: '12px' }}
      >
        <div style={{ width: `${contentWidth}px`, height: '1px' }} />
      </div>

      {/* Kanban board */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div 
          ref={kanbanScrollRef}
          className="flex gap-4 overflow-x-auto pb-4 min-h-[600px]"
          style={{
            scrollSnapType: 'x mandatory',
            WebkitOverflowScrolling: 'touch'
          }}
        >
          {statuses.map((status) => {
            const statusLeads = leadsByStatus[status.name] || [];
            const leadIds = statusLeads.map(lead => lead.id);

            return (
              <div 
                key={status.name}
                style={{ 
                  minWidth: '320px',
                  scrollSnapAlign: 'start'
                }}
              >
                <OutboundKanbanColumn
                  status={status}
                  leads={statusLeads}
                  isDraggingOver={isDragging}
                  selectedCount={statusLeads.filter(l => selectedLeadIds.has(l.id)).length}
                  selectedLeadIds={selectedLeadIds}
                  onSelectAll={onSelectAll}
                  onClearSelection={onClearSelection}
                >
                  <SortableContext
                    items={leadIds}
                    strategy={verticalListSortingStrategy}
                  >
                    {statusLeads.map((lead) => (
                      <OutboundLeadCard
                        key={lead.id}
                        lead={lead}
                        isSelected={selectedLeadIds.has(lead.id)}
                        onSelect={onLeadSelect}
                        onClick={onLeadClick}
                        statuses={statuses}
                        onStatusChange={onStatusChange}
                        isUpdatingStatus={updatingStatusLeadId === lead.id}
                      />
                    ))}
                  </SortableContext>
                </OutboundKanbanColumn>
              </div>
            );
          })}
        </div>

        <DragOverlay>
          {activeId && activeLead ? (
            <div className="rotate-3 opacity-90">
              <OutboundLeadCard
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
    </>
  );
}
