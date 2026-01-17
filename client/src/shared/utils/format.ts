/**
 * 🎯 TIMEZONE FIX: All date formatting with correct timezone handling
 * 
 * The server stores dates as naive datetime in Israel local time using datetime.now().
 * It then adds timezone info (+02:00 or +03:00) via localize_datetime_to_israel() before sending.
 * The ISO strings sent to frontend include proper timezone offset.
 * 
 * Example from backend: "2024-01-20T19:00:00+02:00"
 * This means 19:00 (7 PM) in Israel timezone (UTC+2).
 * 
 * JavaScript correctly interprets these timezone-aware ISO 8601 strings.
 * We simply need to format with Asia/Jerusalem timezone - NO manual offset adjustment needed.
 * 
 * Note: The Intl.DateTimeFormat with timeZone: 'Asia/Jerusalem' handles DST automatically.
 */

const ISRAEL_TIMEZONE = 'Asia/Jerusalem';

/**
 * Format date with time in Israeli timezone
 * Example: "14/12/2025, 19:30"
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE, // Display in Israel timezone
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
    timeZone: ISRAEL_TIMEZONE,
  }).format(d);
}

/**
 * Format time only in Israeli timezone
 * Example: "19:30"
 */
export function formatTimeOnly(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('he-IL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE,
  }).format(d);
}

/**
 * Format relative time (e.g., "לפני 5 דקות", "לפני 3 שעות")
 * 
 * Note: This function calculates time differences using JavaScript Date.getTime()
 * which works correctly regardless of browser timezone, as long as the input
 * dateString is a valid ISO 8601 string with timezone info (e.g., "2024-01-20T19:00:00+02:00").
 * JavaScript automatically converts all dates to UTC internally for calculations.
 */
export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return 'אף פעם';
  
  try {
    // Parse the date - JavaScript handles timezone-aware strings correctly
    // e.g., "2024-01-20T19:00:00+02:00" is correctly converted to UTC internally
    const date = new Date(dateString);
    const now = new Date();
    
    // Calculate difference in milliseconds
    // This is timezone-safe because Date.getTime() returns milliseconds since Unix epoch (UTC)
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
    timeZone: ISRAEL_TIMEZONE,
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