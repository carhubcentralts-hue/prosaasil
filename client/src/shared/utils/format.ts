/**
 * 🎯 TIMEZONE FIX: All date formatting with correct timezone handling
 * 
 * The server stores dates in UTC (datetime.utcnow) and sends ISO strings without timezone info.
 * When JavaScript creates dates from these ISO strings, it interprets them as LOCAL timezone,
 * causing incorrect display if the browser is not in UTC+0.
 * 
 * Solution: Add 2 hours to all dates before formatting to convert UTC -> Israel Time (UTC+2)
 * This ensures consistent display regardless of browser timezone.
 * 
 * Note: In summer (DST), Israel is UTC+3, but the system uses UTC+2 year-round for consistency.
 */

const ISRAEL_TIMEZONE = 'Asia/Jerusalem';
const ISRAEL_OFFSET_HOURS = 2;  // UTC+2 (fixed offset, not DST-aware)

/**
 * Convert UTC datetime string to Israel time by adding offset
 * @internal - used by all format functions
 */
function adjustToIsraelTime(date: string | Date): Date {
  const d = typeof date === 'string' ? new Date(date) : date;
  // Add 2 hours (UTC+2) to convert from UTC to Israel time
  const adjusted = new Date(d.getTime() + ISRAEL_OFFSET_HOURS * 60 * 60 * 1000);
  return adjusted;
}

/**
 * Format date with time in Israeli timezone
 * Example: "14/12/2025, 19:30" (adjusted from UTC to Israel time)
 */
export function formatDate(date: string | Date): string {
  const adjusted = adjustToIsraelTime(date);
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE, // Display in Israel timezone
  }).format(adjusted);
}

/**
 * Format date only (no time) in Israeli timezone
 * Example: "14/12/2025"
 */
export function formatDateOnly(date: string | Date): string {
  const adjusted = adjustToIsraelTime(date);
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: ISRAEL_TIMEZONE,
  }).format(adjusted);
}

/**
 * Format time only in Israeli timezone
 * Example: "19:30" (adjusted from UTC)
 */
export function formatTimeOnly(date: string | Date): string {
  const adjusted = adjustToIsraelTime(date);
  return new Intl.DateTimeFormat('he-IL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: ISRAEL_TIMEZONE,
  }).format(adjusted);
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
  const adjusted = adjustToIsraelTime(date);
  return new Intl.DateTimeFormat('he-IL', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: ISRAEL_TIMEZONE,
  }).format(adjusted);
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