import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Loader2 } from 'lucide-react';
import { LeadStatus } from '../../../features/statuses/hooks';
import { getStatusColor, getStatusLabel, getStatusDotColor } from '../../utils/status';
import { WebhookConfirmPopup, getWebhookPreference } from './WebhookConfirmPopup';
import { http } from '../../../services/http';

interface StatusDropdownWithWebhookProps {
  currentStatus: string;
  statuses: LeadStatus[];
  leadId: number;
  onStatusChange: (statusName: string) => void | Promise<void>;
  disabled?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  source?: string; // Where the status change is happening (e.g., 'lead_page', 'recent_calls_tab')
  hasWebhook?: boolean; // Whether business has status webhook configured
  'data-testid'?: string;
}

/**
 * StatusDropdown with Webhook Confirmation
 * 
 * Features:
 * - Portal-based dropdown menu (renders to document.body)
 * - RTL support with proper alignment
 * - High z-index (9999) to appear above all elements
 * - Webhook confirmation popup if business has status_webhook_url configured
 * - Remembers user preference (always/never/ask)
 * - Optimistic UI with rollback on error
 */
export function StatusDropdownWithWebhook({
  currentStatus,
  statuses,
  leadId,
  onStatusChange,
  disabled = false,
  size = 'md',
  className = '',
  source = 'unknown',
  hasWebhook = false,
  'data-testid': dataTestId = 'status-dropdown'
}: StatusDropdownWithWebhookProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 });
  const [showWebhookPopup, setShowWebhookPopup] = useState(false);
  const [pendingStatus, setPendingStatus] = useState<{ old: string; new: string } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Calculate dropdown position relative to button
  const updatePosition = () => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;
      const dropdownHeight = 300; // Approximate max height

      // Decide placement: bottom (default) or top (flip)
      const shouldFlip = spaceBelow < dropdownHeight && spaceAbove > spaceBelow;
      
      setPosition({
        top: shouldFlip ? rect.top - dropdownHeight - 8 : rect.bottom + 8,
        left: rect.left,
        width: rect.width < 180 ? 180 : rect.width,
      });
    }
  };

  // Update position when opening or on scroll/resize
  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition, true);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [isOpen]);

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const handleStatusSelect = async (statusName: string) => {
    if (statusName === currentStatus) {
      setIsOpen(false);
      return;
    }

    setSaving(true);
    setIsOpen(false);
    
    try {
      // Optimistic UI update
      await onStatusChange(statusName);
      
      // Check webhook preference
      if (hasWebhook) {
        const preference = getWebhookPreference();
        console.log(`[StatusDropdownWithWebhook] hasWebhook=${hasWebhook}, preference=${preference}`);
        
        if (preference === 'always') {
          // Dispatch webhook automatically
          await dispatchWebhook(leadId, currentStatus, statusName, source);
        } else if (preference === 'ask') {
          // Show popup to ask user
          setPendingStatus({ old: currentStatus, new: statusName });
          setShowWebhookPopup(true);
        }
        // If preference is 'never', don't dispatch webhook
      } else {
        console.log('[StatusDropdownWithWebhook] No webhook URL configured, skipping webhook dispatch');
      }
    } catch (error) {
      console.error('Failed to update status:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleWebhookConfirm = async () => {
    setShowWebhookPopup(false);
    if (pendingStatus) {
      const success = await dispatchWebhook(leadId, pendingStatus.old, pendingStatus.new, source);
      if (success) {
        // Show success message briefly
        setTimeout(() => {
          alert('✅ Webhook נשלח בהצלחה');
        }, 100);
      }
    }
    setPendingStatus(null);
  };

  const handleWebhookCancel = () => {
    setShowWebhookPopup(false);
    setPendingStatus(null);
  };

  const dispatchWebhook = async (
    leadId: number,
    oldStatus: string,
    newStatus: string,
    source: string
  ): Promise<boolean> => {
    try {
      await http.post('/api/webhooks/status/dispatch', {
        lead_id: leadId,
        old_status: oldStatus,
        new_status: newStatus,
        source,
      });
      console.log('✅ Webhook dispatched successfully');
      return true;
    } catch (error) {
      console.error('❌ Failed to dispatch webhook:', error);
      // Show error to user
      setTimeout(() => {
        alert('❌ שגיאה בשליחת Webhook. אנא נסה שוב.');
      }, 100);
      return false;
    }
  };

  const currentStatusObj = statuses.find(s => s.name.toLowerCase() === currentStatus.toLowerCase());

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleToggle}
        disabled={disabled || saving}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-full 
          ${size === 'sm' ? 'text-xs' : 'text-sm'} 
          font-medium transition-opacity
          ${getStatusColor(currentStatus, statuses)}
          ${disabled || saving ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80 cursor-pointer'}
          ${className}
        `}
        data-testid={`${dataTestId}-trigger`}
        type="button"
      >
        {saving ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : null}
        {getStatusLabel(currentStatus, statuses)}
        <ChevronDown className="w-3 h-3" />
      </button>

      {/* Portal-based dropdown */}
      {isOpen && createPortal(
        <>
          {/* Backdrop to close on outside click */}
          <div 
            className="fixed inset-0 z-[9998]" 
            onClick={() => setIsOpen(false)}
            data-testid={`${dataTestId}-backdrop`}
          />
          
          {/* Dropdown menu */}
          <div 
            className="fixed bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-[9999] max-h-[300px] overflow-y-auto"
            style={{
              top: `${position.top}px`,
              left: `${position.left}px`,
              minWidth: `${position.width}px`,
            }}
            data-testid={`${dataTestId}-menu`}
          >
            {statuses.length > 0 ? (
              statuses.map((status) => (
                <button
                  key={status.id}
                  onClick={() => handleStatusSelect(status.name)}
                  disabled={saving}
                  className={`
                    w-full px-4 py-2 text-sm text-right hover:bg-gray-50 
                    flex items-center gap-2 transition-colors
                    ${status.name.toLowerCase() === currentStatus.toLowerCase() ? 'bg-blue-50' : ''}
                    ${saving ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                  data-testid={`${dataTestId}-option-${status.name}`}
                  type="button"
                >
                  <span 
                    className="w-3 h-3 rounded-full flex-shrink-0" 
                    style={{ backgroundColor: getStatusDotColor(status.color) }}
                  />
                  <span className="flex-1">{status.label}</span>
                  {status.name.toLowerCase() === currentStatus.toLowerCase() && (
                    <span className="text-blue-600 font-bold">✓</span>
                  )}
                </button>
              ))
            ) : (
              <div className="px-4 py-2 text-sm text-gray-500">טוען סטטוסים...</div>
            )}
          </div>
        </>,
        document.body
      )}

      {/* Webhook confirmation popup */}
      {showWebhookPopup && pendingStatus && (
        <WebhookConfirmPopup
          isOpen={showWebhookPopup}
          onConfirm={handleWebhookConfirm}
          onCancel={handleWebhookCancel}
          oldStatus={getStatusLabel(pendingStatus.old, statuses)}
          newStatus={getStatusLabel(pendingStatus.new, statuses)}
        />
      )}
    </>
  );
}
