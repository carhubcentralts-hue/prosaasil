import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Select } from './Select';
import { LeadStatusConfig } from '../../types/status';

interface StatusCellProps {
  leadId: number;
  currentStatus: string;
  statuses: LeadStatusConfig[];
  onStatusChange: (leadId: number, newStatus: string) => Promise<void>;
  isUpdating?: boolean;
}

/**
 * StatusCell - Unified inline status editor for all lead list views
 * 
 * A reusable component that provides a dropdown for editing lead status inline.
 * Used across System, Active, and Import List table views to ensure consistency.
 * 
 * @component
 * @example
 * ```tsx
 * <StatusCell
 *   leadId={123}
 *   currentStatus="new"
 *   statuses={statusesFromAPI}
 *   onStatusChange={async (id, status) => {
 *     await updateLeadStatus(id, status);
 *   }}
 *   isUpdating={false}
 * />
 * ```
 * 
 * @param {StatusCellProps} props - Component properties
 * @param {number} props.leadId - Unique identifier of the lead
 * @param {string} props.currentStatus - Current status name of the lead
 * @param {LeadStatusConfig[]} props.statuses - Available status options from API
 * @param {Function} props.onStatusChange - Async callback when status changes
 * @param {boolean} [props.isUpdating=false] - External loading state
 * 
 * @returns {JSX.Element} Status dropdown or loading indicator
 * 
 * @remarks
 * - Shows loading spinner during update
 * - Prevents parent row click when interacting with dropdown
 * - Uses optimistic updates via parent component
 * - Single source of truth: statuses from /api/lead-statuses
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
