import { describe, it, expect } from 'vitest';
import {
  getStatusColor,
  getStatusLabel,
  getStatusDotColor,
  parseStatusColorToHex,
} from '../shared/utils/status';
import type { StatusInfo } from '../shared/utils/status';

const sampleStatuses: StatusInfo[] = [
  { id: 1, name: 'new', label: 'חדש', color: 'bg-blue-100 text-blue-800' },
  { id: 2, name: 'won', label: 'נצחנו', color: 'bg-emerald-100 text-emerald-800' },
];

describe('getStatusColor', () => {
  it('returns color from status config when matched', () => {
    expect(getStatusColor('new', sampleStatuses)).toBe('bg-blue-100 text-blue-800');
  });

  it('is case-insensitive', () => {
    expect(getStatusColor('NEW', sampleStatuses)).toBe('bg-blue-100 text-blue-800');
  });

  it('falls back to gray when status unknown', () => {
    expect(getStatusColor('nonexistent', [])).toBe('bg-gray-100 text-gray-800');
  });
});

describe('getStatusLabel', () => {
  it('returns label from status config', () => {
    expect(getStatusLabel('won', sampleStatuses)).toBe('נצחנו');
  });

  it('uses fallback Hebrew label for known status without config', () => {
    expect(getStatusLabel('new', [])).toBe('חדש');
  });

  it('returns the raw status string when completely unknown', () => {
    expect(getStatusLabel('xyz_unknown', [])).toBe('xyz_unknown');
  });
});

describe('getStatusDotColor', () => {
  it('extracts hex color from Tailwind background class', () => {
    expect(getStatusDotColor('bg-blue-100 text-blue-800')).toBe('#3B82F6');
  });

  it('returns gray fallback for unrecognised class', () => {
    expect(getStatusDotColor('bg-fuchsia-999')).toBe('#6B7280');
  });
});

describe('parseStatusColorToHex', () => {
  it('returns hex directly when input starts with #', () => {
    expect(parseStatusColorToHex('#FF0000')).toBe('#FF0000');
  });

  it('extracts hex from Tailwind class', () => {
    expect(parseStatusColorToHex('bg-green-100 text-green-800')).toBe('#22C55E');
  });
});
