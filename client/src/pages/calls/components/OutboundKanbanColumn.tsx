import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { CheckSquare, Square } from 'lucide-react';

interface Lead {
  id: number;
  [key: string]: any;
}

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

interface OutboundKanbanColumnProps {
  status: LeadStatus;
  leads: Lead[];
  isDraggingOver: boolean;
  selectedCount: number;
  children: React.ReactNode;
  selectedLeadIds?: Set<number>;
  onSelectAll?: (leadIds: number[]) => void;
  onClearSelection?: () => void;
  showCallableOnly?: boolean;
  callableLeadIds?: Set<number>;
}

export function OutboundKanbanColumn({
  status,
  leads,
  isDraggingOver,
  selectedCount,
  children,
  selectedLeadIds = new Set(),
  onSelectAll,
  onClearSelection,
  showCallableOnly = false,
  callableLeadIds = new Set()
}: OutboundKanbanColumnProps) {
  const { isOver, setNodeRef } = useDroppable({
    id: status.name,
  });

  const bgColorClass = status.color.includes('bg-') 
    ? status.color.split(' ')[0] 
    : 'bg-gray-100';
  
  const textColorClass = status.color.includes('text-')
    ? status.color.split(' ').find(c => c.startsWith('text-'))
    : 'text-gray-800';

  // Get lead IDs based on callable filter
  const getLeadIds = () => {
    if (showCallableOnly) {
      return leads.filter(l => callableLeadIds.has(l.id)).map(l => l.id);
    }
    return leads.map(l => l.id);
  };

  const leadIds = getLeadIds();
  const allSelected = leadIds.length > 0 && leadIds.every(id => selectedLeadIds.has(id));
  const someSelected = leadIds.some(id => selectedLeadIds.has(id));

  const handleSelectToggle = () => {
    if (allSelected && onClearSelection) {
      onClearSelection();
    } else if (onSelectAll) {
      onSelectAll(leadIds);
    }
  };

  return (
    <div className="flex-shrink-0 w-80 flex flex-col">
      {/* Column Header */}
      <div className={`p-3 rounded-t-lg ${bgColorClass} border-b-2 ${isOver ? 'border-blue-500' : 'border-transparent'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className={`font-semibold ${textColorClass}`}>
              {status.label}
            </h3>
            <span className={`text-sm ${textColorClass} opacity-75`}>
              ({leads.length})
            </span>
          </div>
          <div className="flex items-center gap-2">
            {selectedCount > 0 && (
              <span className="text-xs bg-blue-500 text-white px-2 py-1 rounded-full">
                {selectedCount} נבחר
              </span>
            )}
            {/* Select All button */}
            {leads.length > 0 && onSelectAll && (
              <button
                onClick={handleSelectToggle}
                className={`p-1 rounded hover:bg-black/10 transition-colors ${textColorClass}`}
                title={showCallableOnly ? (allSelected ? 'נקה בחירה' : 'בחר ניתנים לחיוג') : (allSelected ? 'נקה בחירה' : 'בחר הכל')}
              >
                {allSelected ? (
                  <CheckSquare className="w-4 h-4" />
                ) : someSelected ? (
                  <CheckSquare className="w-4 h-4 opacity-50" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Column Body - Droppable Area */}
      <div
        ref={setNodeRef}
        className={`
          flex-1 p-2 bg-gray-50 rounded-b-lg
          min-h-[400px] 
          ${isOver ? 'bg-blue-50 ring-2 ring-blue-300' : ''}
          transition-colors duration-200
          overflow-y-auto
        `}
      >
        <div className="space-y-2">
          {children}
        </div>

        {/* Empty state */}
        {leads.length === 0 && (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            אין לידים בסטטוס זה
          </div>
        )}
      </div>
    </div>
  );
}
