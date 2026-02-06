import { describe, it, expect } from 'vitest';
import { cn } from '../shared/utils/cn';

describe('cn – Tailwind class merge helper', () => {
  it('combines multiple class strings', () => {
    const result = cn('px-4', 'py-2');
    expect(result).toContain('px-4');
    expect(result).toContain('py-2');
  });

  it('deduplicates conflicting Tailwind utilities', () => {
    // tailwind-merge should keep only the last padding-x value
    const result = cn('px-4', 'px-8');
    expect(result).toBe('px-8');
  });

  it('filters out falsy values', () => {
    const result = cn('text-sm', undefined, null, false, 'font-bold');
    expect(result).toContain('text-sm');
    expect(result).toContain('font-bold');
    expect(result).not.toContain('undefined');
  });

  it('returns empty string when given no args', () => {
    expect(cn()).toBe('');
  });
});
