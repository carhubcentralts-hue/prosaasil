import React from 'react';
import { Phone, Clock, User, ChevronLeft } from 'lucide-react';
import { Badge } from '../Badge';
import { formatDate } from '../../utils/format';

interface CallCardProps {
  call: {
    sid: string;
    lead_id?: number;
    lead_name?: string;
    from_e164: string;
    to_e164: string;
    duration: number;
    status: string;
    direction: 'inbound' | 'outbound';
    at: string;
    hasRecording?: boolean;
    hasTranscript?: boolean;
  };
  onCardClick: (call: any) => void;
  showStatus?: boolean;
  statusComponent?: React.ReactNode;
}

/**
 * Mobile Card View for Calls
 * 
 * Displays call information in a card format optimized for mobile devices.
 * Used in Recent Calls, Inbound Calls, and Outbound Calls pages on mobile.
 */
export function CallCard({ call, onCardClick, showStatus = false, statusComponent }: CallCardProps) {
  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}ש'`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'no-answer':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      'completed': 'הושלמה',
      'no-answer': 'לא נענה',
      'busy': 'תפוס',
      'canceled': 'בוטלה',
    };
    return labels[status] || status;
  };

  return (
    <div
      onClick={() => onCardClick(call)}
      className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer mobile-safe-flex"
    >
      {/* Header Row: Direction Icon + Name/Phone + Status */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className={`p-2 rounded-full flex-shrink-0 ${call.direction === 'inbound' ? 'bg-green-100' : 'bg-blue-100'}`}>
            <Phone className={`w-4 h-4 ${call.direction === 'inbound' ? 'text-green-600' : 'text-blue-600'}`} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 mobile-ellipsis">
              {call.lead_name || 'לקוח אלמוני'}
            </p>
            <p className="text-xs text-gray-500 mobile-ellipsis">{call.from_e164}</p>
          </div>
        </div>
        
        {/* Status Badge or Custom Status Component */}
        {showStatus && statusComponent ? (
          <div className="flex-shrink-0">{statusComponent}</div>
        ) : (
          <Badge variant={getStatusBadgeVariant(call.status)} className="flex-shrink-0">
            {getStatusLabel(call.status)}
          </Badge>
        )}
      </div>

      {/* Details Row: Duration + Date + Direction */}
      <div className="flex items-center justify-between text-xs text-gray-600">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>{formatDuration(call.duration)}</span>
          </div>
          <span className={`px-2 py-0.5 rounded ${call.direction === 'inbound' ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-700'}`}>
            {call.direction === 'inbound' ? 'נכנסת' : 'יוצאת'}
          </span>
        </div>
        <span className="text-gray-400">{formatDate(call.at)}</span>
      </div>

      {/* Indicators Row: Recording + Transcript */}
      {(call.hasRecording || call.hasTranscript) && (
        <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
          {call.hasRecording && (
            <span className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700">
              🎧 הקלטה
            </span>
          )}
          {call.hasTranscript && (
            <span className="text-xs px-2 py-1 rounded bg-purple-50 text-purple-700">
              📝 תמליל
            </span>
          )}
        </div>
      )}

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
