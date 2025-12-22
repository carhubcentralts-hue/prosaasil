/**
 * Shared type definitions for status management
 */

/**
 * Lead status configuration from API
 * Returned by /api/lead-statuses endpoint
 */
export interface LeadStatusConfig {
  /** Internal status name (e.g., "new", "contacted") */
  name: string;
  
  /** Display label (e.g., "חדש", "נוצר קשר") */
  label: string;
  
  /** Tailwind CSS classes for styling (e.g., "bg-blue-100 text-blue-800") */
  color: string;
  
  /** Sort order for display */
  order_index: number;
  
  /** Whether this is a system-defined status (cannot be deleted) */
  is_system?: boolean;
}
