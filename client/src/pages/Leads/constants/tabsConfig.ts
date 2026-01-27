/**
 * Shared constants for lead tabs configuration
 */

// All available tabs
export const ALL_AVAILABLE_TAB_KEYS = [
  'activity',
  'reminders', 
  'documents',
  'overview',
  'whatsapp',
  'calls',
  'email',
  'contracts',
  'appointments',
  'ai_notes',
  'notes'
] as const;

// Default configuration if not set
export const DEFAULT_PRIMARY_TABS = ['activity', 'reminders', 'documents'];

// Secondary tabs default: ALL tabs that are not in primary
// This will be calculated dynamically
