import React, { forwardRef } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Phone, Mail, User, Calendar, Tag, MoreVertical, Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { Lead } from '../types';
import { cn } from '../../../shared/utils/cn';
import { formatDate } from '../../../shared/utils/format';

interface LeadCardProps {
  lead: Lead;
  onClick: () => void;
  isDragging?: boolean;
}

const LeadCard = forwardRef<HTMLDivElement, LeadCardProps>(
  ({ lead, onClick, isDragging }, ref) => {
    const navigate = useNavigate();
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging: isSortableDragging,
    } = useSortable({
      id: lead.id.toString(),
    });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
    };

    const isBeingDragged = isDragging || isSortableDragging;

    const getSourceColor = (source: string) => {
      switch (source) {
        case 'call':
          return 'bg-blue-100 text-blue-800';
        case 'whatsapp':
          return 'bg-green-100 text-green-800';
        case 'form':
          return 'bg-purple-100 text-purple-800';
        case 'manual':
          return 'bg-gray-100 text-gray-800';
        default:
          return 'bg-gray-100 text-gray-800';
      }
    };

    const getSourceLabel = (source: string) => {
      switch (source) {
        case 'call':
          return 'שיחה';
        case 'whatsapp':
          return 'וואטסאפ';
        case 'form':
          return 'טופס';
        case 'manual':
          return 'ידני';
        default:
          return source;
      }
    };

    return (
      <div
        ref={setNodeRef}
        style={style}
        className={cn(
          'cursor-pointer transition-all duration-200',
          isBeingDragged && 'opacity-50 scale-105 rotate-2 z-50'
        )}
        {...attributes}
        {...listeners}
        data-testid={`card-lead-${lead.id}`}
      >
        <div onClick={onClick} className="cursor-pointer">
          <Card
            className={cn(
              'p-4 hover:shadow-md transition-shadow bg-white border border-gray-200',
              isBeingDragged && 'shadow-lg border-blue-300'
            )}
          >
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-base text-gray-900 mb-1.5" data-testid={`text-lead-name-${lead.id}`}>
                {lead.full_name || 
                 (lead.first_name && lead.last_name ? `${lead.first_name} ${lead.last_name}` : lead.first_name || lead.last_name) || 
                 (lead.phone_e164 ? lead.display_phone || lead.phone_e164 : 'ללא שם')}
              </h4>
              <div className="flex items-center gap-2">
                <Badge className={`${getSourceColor(lead.source)} text-xs`}>
                  {getSourceLabel(lead.source)}
                </Badge>
                {lead.tags && lead.tags.length > 0 && (
                  <Badge variant="neutral" className="text-xs">
                    <Tag className="w-3 h-3 ml-1" />
                    {lead.tags.length}
                  </Badge>
                )}
              </div>
            </div>
            <button className="p-1 hover:bg-gray-100 rounded">
              <MoreVertical className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          {/* Contact Info */}
          <div className="space-y-2">
            {lead.phone_e164 && (
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <Phone className="w-3 h-3" />
                <span className="truncate" data-testid={`text-lead-phone-${lead.id}`}>
                  {lead.display_phone || lead.phone_e164}
                </span>
              </div>
            )}
            
            {lead.email && (
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <Mail className="w-3 h-3" />
                <span className="truncate" data-testid={`text-lead-email-${lead.id}`}>
                  {lead.email}
                </span>
              </div>
            )}

            {lead.owner_user_id && (
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <User className="w-3 h-3" />
                <span className="truncate">
                  נציג #{lead.owner_user_id}
                </span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Calendar className="w-3 h-3" />
              <span data-testid={`text-lead-created-${lead.id}`}>
                {formatDate(lead.created_at)}
              </span>
            </div>
            
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/app/leads/${lead.id}`);
              }}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors"
              data-testid={`button-view-details-${lead.id}`}
            >
              <Eye className="w-3 h-3" />
              פרטים
            </button>
          </div>

          {/* Notes Preview */}
          {lead.notes && (
            <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600 line-clamp-2">
              {lead.notes}
            </div>
          )}
          </Card>
        </div>
      </div>
    );
  }
);

LeadCard.displayName = 'LeadCard';

export default LeadCard;