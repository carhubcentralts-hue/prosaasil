/**
 * Conversation display name utilities
 * Single source of truth for how to display conversation/thread names
 */

/**
 * Normalize a phone number or JID to a clean display format
 * Removes WhatsApp JID suffixes and formats phone numbers
 * 
 * @param phone - Raw phone number or JID (e.g., "972525951893@s.whatsapp.net", "lid@8762...")
 * @returns Clean phone number without JID suffix
 */
export function normalizePhoneForDisplay(phone: string | undefined | null): string {
  if (!phone) return '';
  
  // Check if it's a lid@ identifier first (e.g., 'lid@8762345')
  if (/^lid@/i.test(phone)) {
    return '';
  }
  
  // Remove WhatsApp JID suffixes
  const normalized = phone
    .replace(/@s\.whatsapp\.net/g, '')
    .replace(/@c\.us/g, '')
    .replace(/@lid/g, '')
    .replace(/@broadcast/g, '')
    .replace(/@g\.us/g, '')
    .trim();
  
  // LID identifiers are very long numbers (14+ digits) without typical phone patterns
  // Real phone numbers in E.164 format are typically 10-13 digits (e.g., 972525951893)
  // WhatsApp @lid identifiers are 14+ digit internal IDs
  const MIN_LID_DIGITS = 14;
  if (normalized.length >= MIN_LID_DIGITS && /^\d+$/.test(normalized) && !normalized.startsWith('+')) {
    // This is likely an @lid identifier, not a real phone number
    return '';
  }
  
  return normalized;
}

/**
 * Get the display name for a conversation/thread
 * Priority: lead_name > push_name > contact_name > phone (formatted) > fallback
 * 
 * NEVER returns @lid or raw JID identifiers - always a human-readable name
 * 
 * @param thread - Thread object with potential name fields
 * @param fallback - Optional fallback text (default: "ללא שם")
 * @returns Display name for the conversation
 */
export function getConversationDisplayName(
  thread: {
    lead_name?: string | null;
    push_name?: string | null;
    name?: string | null;
    peer_name?: string | null;
    phone?: string | null;
    phone_e164?: string | null;
  },
  fallback: string = 'ללא שם'
): string {
  // Priority 1: Lead name (from CRM)
  if (thread.lead_name && thread.lead_name.trim()) {
    return thread.lead_name.trim();
  }
  
  // Priority 2: Push name (from WhatsApp contact)
  if (thread.push_name && thread.push_name.trim()) {
    // Don't use push_name if it looks like a phone number or lid
    const pushName = thread.push_name.trim();
    if (!pushName.match(/^\+?\d+$/) && !pushName.includes('@')) {
      return pushName;
    }
  }
  
  // Priority 3: Generic name field (could be from various sources)
  if (thread.name && thread.name.trim()) {
    const name = thread.name.trim();
    // Don't use name if it's a JID, lid@, or looks like raw phone
    if (!name.includes('@') && !name.match(/^lid\d+/) && name !== 'לא ידוע') {
      // If it's just digits and looks like phone, format it nicely
      if (name.match(/^\+?\d{10,}$/)) {
        return formatPhoneNumber(name);
      }
      return name;
    }
  }
  
  // Priority 4: Peer name
  if (thread.peer_name && thread.peer_name.trim()) {
    const peerName = thread.peer_name.trim();
    if (!peerName.includes('@') && !peerName.match(/^lid\d+/)) {
      return peerName;
    }
  }
  
  // Priority 5: Phone number (formatted)
  const phone = thread.phone_e164 || thread.phone;
  if (phone && phone.trim()) {
    const normalized = normalizePhoneForDisplay(phone);
    if (normalized && !normalized.match(/^lid/i)) {
      return formatPhoneNumber(normalized);
    }
  }
  
  // Fallback: Only if we have absolutely nothing else
  return fallback;
}

/**
 * Format a phone number for display
 * Adds + prefix if missing and number looks valid
 */
function formatPhoneNumber(phone: string): string {
  if (!phone) return '';
  
  const cleaned = phone.replace(/[^\d+]/g, '');
  
  // If it's just digits and reasonable length, add + prefix
  if (cleaned.match(/^\d{10,15}$/)) {
    return '+' + cleaned;
  }
  
  return cleaned || phone;
}
