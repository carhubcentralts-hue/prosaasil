import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Badge } from '../../../shared/components/Badge';
import { Lead, LeadStatus } from '../types';
import LeadCard from './LeadCard';

interface KanbanColumnProps {
  status: {
    key: LeadStatus;
    label: string;
    color: string;
  };
  leads: Lead[];
  onLeadClick: (lead: Lead) => void;
  activeId: string | null;
}

export default function KanbanColumn({ 
  status, 
  leads, 
  onLeadClick, 
  activeId 
}: KanbanColumnProps) {
  const droppableId = `droppable-status-${status.key}`;
  
  const { setNodeRef, isOver } = useDroppable({
    id: droppableId,
  });

  return (
    <div
      className="flex flex-col"
      data-testid={`column-${status.key.toLowerCase()}`}
    >
      {/* Column Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-sm">{status.label}</h3>
          <Badge className={`${status.color} text-xs`}>
            {leads.length}
          </Badge>
        </div>
        <div className="h-1 bg-gray-200 rounded">
          <div 
            className={`h-full rounded ${status.color.split(' ')[0]}`}
            style={{ width: leads.length > 0 ? '100%' : '0%' }}
          />
        </div>
      </div>

      {/* Drop Zone */}
      <div
        ref={setNodeRef}
        className={`flex-1 min-h-[200px] p-2 rounded-lg border-2 transition-colors ${
          isOver 
            ? 'border-blue-400 bg-blue-50' 
            : 'border-dashed border-gray-200 bg-gray-50/50'
        }`}
        data-testid={`dropzone-${status.key.toLowerCase()}`}
      >
        <SortableContext
          items={leads.map(lead => lead.id.toString())}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-3">
            {leads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                onClick={() => onLeadClick(lead)}
                isDragging={activeId === lead.id.toString()}
              />
            ))}
          </div>
        </SortableContext>
        
        {/* Empty state */}
        {leads.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            גרור לידים לכאן
          </div>
        )}
      </div>
    </div>
  );
}