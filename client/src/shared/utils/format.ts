/**
 * Format phone number for Hebrew interface
 */
export function formatPhone(phone: string): string {
  if (!phone) return '';
  
  // Remove any non-digit characters
  const digits = phone.replace(/\D/g, '');
  
  // Israeli phone number format
  if (digits.startsWith('972')) {
    // International format: +972-XX-XXX-XXXX
    const local = digits.slice(3);
    if (local.length === 9) {
      return `+972-${local.slice(0, 2)}-${local.slice(2, 5)}-${local.slice(5)}`;
    }
  } else if (digits.startsWith('0') && digits.length === 10) {
    // Local format: 0XX-XXX-XXXX
    return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  
  return phone; // Return as-is if doesn't match expected format
}

/**
 * Format date for Hebrew interface
 */
export function formatDate(date: string | Date): string {
  const d = new Date(date);
  return new Intl.DateTimeFormat('he-IL', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(d);
}

/**
 * Format currency for Hebrew interface
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS'
  }).format(amount);
}

/**
 * Format large numbers with Hebrew separators
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('he-IL').format(num);
}