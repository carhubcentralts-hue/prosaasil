import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatDateOnly,
  formatTimeOnly,
  formatRelativeTime,
  formatNumber,
  normalizePhone,
  formatDuration,
} from '../shared/utils/format';

describe('format utilities', () => {
  // Use a known ISO string with explicit timezone so the test is deterministic
  const ISO_DATE = '2025-06-15T14:30:00+03:00'; // 14:30 Israel Summer Time

  it('formatDate includes date and time', () => {
    const result = formatDate(ISO_DATE);
    // Should contain 15 (day) and 30 (minutes)
    expect(result).toContain('15');
    expect(result).toContain('30');
  });

  it('formatDateOnly omits time', () => {
    const result = formatDateOnly(ISO_DATE);
    expect(result).toContain('15');
    // Should NOT contain hour:minute separator for "14:30"
    expect(result).not.toContain('14:30');
  });

  it('formatTimeOnly omits date', () => {
    const result = formatTimeOnly(ISO_DATE);
    expect(result).toContain('14:30');
  });

  it('formatRelativeTime returns "אף פעם" for null/undefined', () => {
    expect(formatRelativeTime(null)).toBe('אף פעם');
    expect(formatRelativeTime(undefined)).toBe('אף פעם');
  });

  it('formatRelativeTime returns a Hebrew relative string for a past date', () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86_400_000).toISOString();
    const result = formatRelativeTime(twoDaysAgo);
    // Should contain the Hebrew word "לפני" (ago)
    expect(result).toContain('לפני');
  });

  it('formatNumber formats with locale separators', () => {
    const result = formatNumber(1234567);
    // Hebrew locale uses comma or period as thousands separator
    expect(result.replace(/[,.\s]/g, '')).toBe('1234567');
  });

  it('normalizePhone strips non-digit chars', () => {
    expect(normalizePhone('+972-50-123-4567')).toBe('972501234567');
  });

  it('formatDuration formats seconds as m:ss', () => {
    expect(formatDuration(65)).toBe('1:05');
    expect(formatDuration(0)).toBe('0:00');
    expect(formatDuration(3600)).toBe('60:00');
  });
});
