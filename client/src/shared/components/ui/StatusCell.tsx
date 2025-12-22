import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Select } from './Select';

interface LeadStatus {
  name: string;
  label: string;
  color: string;
  order_index: number;
  is_system?: boolean;
}

interface StatusCellProps {
  leadId: number;
  currentStatus: string;
  statuses: LeadStatus[];
  onStatusChange: (leadId: number, newStatus: string) => Promise<void>;
  isUpdating?: boolean;
}

/**
 * StatusCell - Unified inline status editor for all lead list views
 * 
 * Features:
 * - Dropdown for status selection
 * - Loading state during update
 * - Single source of truth from API statuses
 * - Used in System, Active, and Import List table views
 */
export function StatusCell({
  leadId,
  currentStatus,
  statuses,
  onStatusChange,
  isUpdating = false
}: StatusCellProps) {
  const [localUpdating, setLocalUpdating] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value;
    if (newStatus === currentStatus) return;

    try {
      setLocalUpdating(true);
      await onStatusChange(leadId, newStatus);
    } catch (error) {
      console.error(`[StatusCell] Failed to update status for lead ${leadId}:`, error);
    } finally {
      setLocalUpdating(false);
    }
  };

  const isLoading = isUpdating || localUpdating;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
        <span className="text-xs text-gray-500">שומר...</span>
      </div>
    );
  }

  return (
    <Select
      value={currentStatus}
      onChange={handleChange}
      className="text-xs h-7 py-0 px-2 min-w-[100px]"
      data-testid={`status-cell-${leadId}`}
      onClick={(e) => e.stopPropagation()} // Prevent row click when clicking dropdown
    >
      {statuses.map((status) => (
        <option key={status.name} value={status.name}>
          {status.label}
        </option>
      ))}
    </Select>
  );
}
