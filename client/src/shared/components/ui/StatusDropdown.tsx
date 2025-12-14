import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Loader2 } from 'lucide-react';
import { LeadStatus } from '../../../features/statuses/hooks';
import { getStatusColor, getStatusLabel, getStatusDotColor } from '../../utils/status';

interface StatusDropdownProps {
  currentStatus: string;
  statuses: LeadStatus[];
  onStatusChange: (statusName: string) => void | Promise<void>;
  disabled?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  'data-testid'?: string;
}

/**
 * StatusDropdown Component with Portal Support
 * 
 * Features:
 * - Portal-based dropdown menu (renders to document.body)
 * - RTL support with proper alignment
 * - High z-index (9999) to appear above all elements
 * - Flip support when insufficient space
 * - No clipping issues
 * - Accessible and keyboard-friendly
 */
export function StatusDropdown({
  currentStatus,
  statuses,
  onStatusChange,
  disabled = false,
  size = 'md',
  className = '',
  'data-testid': dataTestId = 'status-dropdown'
}: StatusDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0 });
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
        top: shouldFlip ? rect.top - dropdownHeight - 8 : rect.bottom + 8, // 8px gap, account for dropdown height when flipping
        left: rect.left,
        width: rect.width < 180 ? 180 : rect.width, // Minimum 180px
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
    setSaving(true);
    try {
      await onStatusChange(statusName);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to update status:', error);
    } finally {
      setSaving(false);
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
    </>
  );
}
