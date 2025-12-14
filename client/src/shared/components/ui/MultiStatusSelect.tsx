import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, X } from 'lucide-react';
import { LeadStatus } from '../../../features/statuses/hooks';
import { getStatusDotColor } from '../../utils/status';

interface MultiStatusSelectProps {
  statuses: LeadStatus[];
  selectedStatuses: string[];
  onChange: (selectedStatuses: string[]) => void;
  placeholder?: string;
  className?: string;
  'data-testid'?: string;
}

/**
 * MultiStatusSelect Component with Portal Support
 * 
 * Features:
 * - Portal-based dropdown menu (renders to document.body)
 * - RTL support with proper alignment
 * - High z-index (9999) to appear above all elements
 * - Multi-selection with checkboxes
 * - Shows selected count in the trigger
 */
export function MultiStatusSelect({
  statuses,
  selectedStatuses,
  onChange,
  placeholder = 'בחר סטטוסים',
  className = '',
  'data-testid': dataTestId = 'multi-status-select'
}: MultiStatusSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
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
        top: shouldFlip ? rect.top - 8 : rect.bottom + 8, // 8px gap
        left: rect.left,
        width: rect.width < 200 ? 200 : rect.width, // Minimum 200px
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
    setIsOpen(!isOpen);
  };

  const handleStatusToggle = (statusName: string) => {
    const newSelection = selectedStatuses.includes(statusName)
      ? selectedStatuses.filter(s => s !== statusName)
      : [...selectedStatuses, statusName];
    onChange(newSelection);
  };

  const handleClearAll = () => {
    onChange([]);
  };

  const handleSelectAll = () => {
    onChange(statuses.map(s => s.name));
  };

  const selectedCount = selectedStatuses.length;
  const allSelected = selectedCount === statuses.length && statuses.length > 0;

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleToggle}
        className={`
          flex items-center justify-between gap-2 px-3 py-2 
          border border-gray-300 rounded-md bg-white
          hover:border-gray-400 transition-colors
          text-sm text-right
          ${className}
        `}
        data-testid={`${dataTestId}-trigger`}
        type="button"
      >
        <span className="flex-1 truncate">
          {selectedCount === 0
            ? placeholder
            : selectedCount === 1
            ? statuses.find(s => s.name === selectedStatuses[0])?.label || selectedStatuses[0]
            : `${selectedCount} סטטוסים נבחרו`}
        </span>
        {selectedCount > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleClearAll();
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
            title="נקה הכל"
          >
            <X className="w-3 h-3 text-gray-500" />
          </button>
        )}
        <ChevronDown className="w-4 h-4 text-gray-500" />
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
            {/* Select All / Clear All */}
            <div className="px-3 py-2 border-b border-gray-200">
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={handleSelectAll}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  type="button"
                >
                  בחר הכל
                </button>
                <button
                  onClick={handleClearAll}
                  className="text-xs text-gray-600 hover:text-gray-700 font-medium"
                  type="button"
                >
                  נקה הכל
                </button>
              </div>
            </div>

            {/* Status options */}
            {statuses.length > 0 ? (
              statuses.map((status) => {
                const isSelected = selectedStatuses.includes(status.name);
                return (
                  <button
                    key={status.id}
                    onClick={() => handleStatusToggle(status.name)}
                    className={`
                      w-full px-4 py-2 text-sm text-right hover:bg-gray-50 
                      flex items-center gap-2 transition-colors
                      ${isSelected ? 'bg-blue-50' : ''}
                    `}
                    data-testid={`${dataTestId}-option-${status.name}`}
                    type="button"
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      readOnly
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 pointer-events-none"
                    />
                    <span 
                      className="w-3 h-3 rounded-full flex-shrink-0" 
                      style={{ backgroundColor: getStatusDotColor(status.color) }}
                    />
                    <span className="flex-1">{status.label}</span>
                  </button>
                );
              })
            ) : (
              <div className="px-4 py-2 text-sm text-gray-500">אין סטטוסים</div>
            )}
          </div>
        </>,
        document.body
      )}
    </>
  );
}
