/**
 * 🎯 TIMEZONE FIX: All date formatting with correct timezone handling
 * 
 * The server stores dates in Asia/Jerusalem timezone (UTC+2/+3 depending on DST).
 * When JavaScript creates dates from ISO strings, it interprets them incorrectly
 * if we don't specify the timezone, causing 7-hour offsets and wrong times.
 * 
 * Solution: ALWAYS use timeZone: 'Asia/Jerusalem' in Intl.DateTimeFormat
 */

const ISRAEL_TIMEZONE = 'Asia/Jerusalem';

/**
 * Format date with time in Israeli timezone
 * Example: "14/12/2025, 19:30" instead of "14/12/2025, 12:30" (wrong UTC interpretation)
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE, // 🎯 FIX: Always use Israel timezone
  }).format(d);
}

/**
 * Format date only (no time) in Israeli timezone
 * Example: "14/12/2025"
 */
export function formatDateOnly(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: ISRAEL_TIMEZONE, // 🎯 FIX: Always use Israel timezone
  }).format(d);
}

/**
 * Format time only in Israeli timezone
 * Example: "19:30" instead of "12:30" (wrong UTC interpretation)
 */
export function formatTimeOnly(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE, // 🎯 FIX: Always use Israel timezone
  }).format(d);
}

/**
 * Format relative time (e.g., "לפני 5 דקות", "לפני 3 שעות")
 * 🎯 FIX: Calculate diff in Israeli timezone to avoid offset issues
 */
export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return 'אף פעם';
  
  try {
    // Parse the date
    const date = new Date(dateString);
    const now = new Date();
    
    // Calculate difference in milliseconds
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    // Return relative description
    if (diffMins < 1) return 'כרגע';
    if (diffMins < 60) return `לפני ${diffMins} דקות`;
    if (diffHours < 24) return `לפני ${diffHours} שעות`;
    if (diffDays === 1) return 'אתמול';
    if (diffDays < 7) return `לפני ${diffDays} ימים`;
    if (diffDays < 30) return `לפני ${Math.floor(diffDays / 7)} שבועות`;
    return `לפני ${Math.floor(diffDays / 30)} חודשים`;
  } catch {
    return 'אף פעם';
  }
}

/**
 * Format long date with day name in Israeli timezone
 * Example: "יום חמישי, 14 בדצמבר 2025"
 */
export function formatLongDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: ISRAEL_TIMEZONE, // 🎯 FIX: Always use Israel timezone
  }).format(d);
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('he-IL').format(num);
}

export function normalizePhone(phone: string): string {
  return phone.replace(/\D/g, '');
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}