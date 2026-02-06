import React from 'react';
import { User, Phone, Mail, Calendar, ChevronLeft } from 'lucide-react';
import { Badge } from './Badge';
import { formatDate } from '../utils/format';

interface LeadCardProps {
  lead: {
    id: number;
    first_name?: string;
    last_name?: string;
    full_name?: string;
    phone_e164?: string;
    email?: string;
    status: string;
    source?: string;
    created_at: string;
    service_type?: string;
    city?: string;
  };
  onCardClick: (lead: any) => void;
  statusComponent?: React.ReactNode;
}

/**
 * Mobile Card View for Leads
 * 
 * Displays lead information in a card format optimized for mobile devices.
 * Used in Leads list page on mobile.
 */
export function LeadCard({ lead, onCardClick, statusComponent }: LeadCardProps) {
  const fullName = lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם';

  const getSourceLabel = (source?: string) => {
    const labels: Record<string, string> = {
      'phone': 'טלפון',
      'whatsapp': 'WhatsApp',
      'form': 'טופס',
      'manual': 'ידני',
      'imported_outbound': 'יבוא',
    };
    return source ? labels[source] || source : 'לא צוין';
  };

  const getSourceIcon = (source?: string) => {
    switch (source) {
      case 'phone':
        return '📞';
      case 'whatsapp':
        return '💬';
      case 'form':
        return '📋';
      case 'manual':
        return '✍️';
      case 'imported_outbound':
        return '📥';
      default:
        return '📌';
    }
  };

  return (
    <div
      onClick={() => onCardClick(lead)}
      className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer mobile-safe-flex"
    >
      {/* Header Row: Icon + Name + Status */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="p-2 rounded-full bg-blue-100 flex-shrink-0">
            <User className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 mobile-ellipsis">
              {fullName}
            </p>
            {lead.phone_e164 && (
              <p className="text-xs text-gray-500 mobile-ellipsis flex items-center gap-1 mt-0.5">
                <Phone className="w-3 h-3" />
                {lead.phone_e164}
              </p>
            )}
          </div>
        </div>
        
        {/* Status Component */}
        {statusComponent && (
          <div className="flex-shrink-0">{statusComponent}</div>
        )}
      </div>

      {/* Email Row (if exists) */}
      {lead.email && (
        <div className="flex items-center gap-2 text-xs text-gray-600 mb-2">
          <Mail className="w-3 h-3" />
          <span className="mobile-ellipsis">{lead.email}</span>
        </div>
      )}

      {/* Details Row: Service + City */}
      {(lead.service_type || lead.city) && (
        <div className="flex items-center gap-3 text-xs text-gray-600 mb-2">
          {lead.service_type && (
            <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 mobile-ellipsis">
              {lead.service_type}
            </span>
          )}
          {lead.city && (
            <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 mobile-ellipsis">
              📍 {lead.city}
            </span>
          )}
        </div>
      )}

      {/* Footer Row: Source + Date */}
      <div className="flex items-center justify-between text-xs text-gray-500 pt-3 border-t border-gray-100">
        <span className="flex items-center gap-1">
          <span>{getSourceIcon(lead.source)}</span>
          {getSourceLabel(lead.source)}
        </span>
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          {formatDate(lead.created_at)}
        </span>
      </div>

      {/* Click indicator */}
      <div className="flex items-center justify-center mt-3 pt-3 border-t border-gray-100">
        <span className="text-xs text-blue-600 flex items-center gap-1">
          לחץ לפרטים
          <ChevronLeft className="w-3 h-3" />
        </span>
      </div>
    </div>
  );
}
