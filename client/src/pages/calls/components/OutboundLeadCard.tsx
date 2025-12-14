import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Phone, Clock, GripVertical } from 'lucide-react';
import { formatRelativeTime } from '../../../shared/utils/format';

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

interface OutboundLeadCardProps {
  lead: Lead;
  isSelected: boolean;
  onSelect: (leadId: number, isShiftKey?: boolean) => void;
  onClick?: (leadId: number) => void;
  isDragOverlay?: boolean;
}

export function OutboundLeadCard({
  lead,
  isSelected,
  onSelect,
  onClick,
  isDragOverlay = false
}: OutboundLeadCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: lead.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  // 🎯 REMOVED: Use centralized formatRelativeTime from utils with timezone fix
  // const formatRelativeTime = (dateString: string | null | undefined): string => { ... }

  const formatPhone = (phone: string | null | undefined): string => {
    if (!phone) return '';
    // Convert +972501234567 to 050-123-4567
    const cleaned = phone.replace('+972', '0');
    if (cleaned.length === 10) {
      return `${cleaned.slice(0, 3)}-${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
    }
    return phone;
  };

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    onSelect(lead.id, e.shiftKey);
  };

  const handleCardClick = (e: React.MouseEvent) => {
    // Don't trigger card click if clicking on checkbox area or drag handle
    const target = e.target as HTMLElement;
    if (target.closest('[data-checkbox-wrapper]') || target.closest('[data-drag-handle]')) {
      return;
    }
    if (!isDragOverlay && onClick) {
      onClick(lead.id);
    }
  };

  const name = lead.full_name || lead.first_name || 'ללא שם';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        bg-white rounded-lg border shadow-sm p-3
        hover:shadow-md transition-shadow cursor-pointer
        ${isSelected ? 'ring-2 ring-blue-500 bg-blue-50' : ''}
        ${isDragOverlay ? 'shadow-xl' : ''}
      `}
      onClick={handleCardClick}
    >
      <div className="flex items-start gap-2">
        {/* Checkbox */}
        <label
          data-checkbox-wrapper
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={handleCheckboxClick}
          className="flex items-center gap-2 cursor-pointer mt-0.5"
        >
          <input
            type="checkbox"
            checked={isSelected}
            readOnly
            aria-label={`בחר ליד ${lead.full_name || lead.first_name || 'ללא שם'}`}
            className="accent-blue-600 pointer-events-auto h-4 w-4 rounded border-gray-300"
          />
        </label>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Name */}
          <div className="font-semibold text-sm truncate">
            {name}
          </div>

          {/* Phone */}
          {lead.phone_e164 && (
            <div className="flex items-center gap-1 text-xs text-gray-600 mt-1">
              <Phone className="w-3 h-3" />
              <span className="truncate">{formatPhone(lead.phone_e164)}</span>
            </div>
          )}

          {/* Summary */}
          {lead.summary && (
            <div className="text-xs text-gray-500 mt-2 line-clamp-2">
              {lead.summary}
            </div>
          )}

          {/* Last Contact */}
          {lead.last_contact_at && (
            <div className="flex items-center gap-1 text-xs text-gray-400 mt-2">
              <Clock className="w-3 h-3" />
              <span>{formatRelativeTime(lead.last_contact_at)}</span>
            </div>
          )}
        </div>

        {/* Drag Handle */}
        <div 
          {...attributes} 
          {...listeners} 
          className="cursor-grab active:cursor-grabbing mt-1"
          data-drag-handle
        >
          <GripVertical className="w-4 h-4 text-gray-400" />
        </div>
      </div>
    </div>
  );
}
