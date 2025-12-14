import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Lead } from '../types';

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

interface LeadKanbanColumnProps {
  status: LeadStatus;
  leads: Lead[];
  isDraggingOver: boolean;
  children: React.ReactNode;
}

export function LeadKanbanColumn({
  status,
  leads,
  isDraggingOver,
  children
}: LeadKanbanColumnProps) {
  const { isOver, setNodeRef } = useDroppable({
    id: status.name,
  });

  const bgColorClass = status.color.includes('bg-') 
    ? status.color.split(' ')[0] 
    : 'bg-gray-100';
  
  const textColorClass = status.color.includes('text-')
    ? status.color.split(' ').find(c => c.startsWith('text-'))
    : 'text-gray-800';

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
