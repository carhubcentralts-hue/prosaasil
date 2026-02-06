/**
 * Tests for conversation display name utilities
 */

import { getConversationDisplayName, normalizePhoneForDisplay } from '../conversation';

describe('normalizePhoneForDisplay', () => {
  it('should remove WhatsApp JID suffixes', () => {
    expect(normalizePhoneForDisplay('972525951893@s.whatsapp.net')).toBe('972525951893');
    expect(normalizePhoneForDisplay('972525951893@c.us')).toBe('972525951893');
  });

  it('should return empty string for @lid identifiers', () => {
    expect(normalizePhoneForDisplay('82399031480511@lid')).toBe('');
    expect(normalizePhoneForDisplay('lid@8762345')).toBe('');
  });

  it('should handle null/undefined', () => {
    expect(normalizePhoneForDisplay(null)).toBe('');
    expect(normalizePhoneForDisplay(undefined)).toBe('');
    expect(normalizePhoneForDisplay('')).toBe('');
  });
});

describe('getConversationDisplayName', () => {
  it('should prioritize lead_name', () => {
    const thread = {
      lead_name: 'אברהם אלפנדרי',
      push_name: 'Abraham',
      name: 'Some Name',
      phone_e164: '+972525951893'
    };
    expect(getConversationDisplayName(thread)).toBe('אברהם אלפנדרי');
  });

  it('should use push_name when lead_name is not available', () => {
    const thread = {
      push_name: 'Abraham Contact',
      name: 'Some Name',
      phone_e164: '+972525951893'
    };
    expect(getConversationDisplayName(thread)).toBe('Abraham Contact');
  });

  it('should use formatted phone when names are not available', () => {
    const thread = {
      phone_e164: '972525951893'
    };
    expect(getConversationDisplayName(thread)).toBe('+972525951893');
  });

  it('should never return @lid identifiers', () => {
    const thread = {
      name: '82399031480511@lid',
      phone: '82399031480511@lid',
      phone_e164: '82399031480511@lid'
    };
    expect(getConversationDisplayName(thread)).toBe('ללא שם');
  });

  it('should use custom fallback', () => {
    const thread = {};
    expect(getConversationDisplayName(thread, 'Unknown')).toBe('Unknown');
  });

  it('should not use phone-like push_name', () => {
    const thread = {
      push_name: '+972525951893',
      phone_e164: '+972525951893'
    };
    expect(getConversationDisplayName(thread)).toBe('+972525951893');
  });

  it('should handle WhatsApp JID in name field', () => {
    const thread = {
      name: '972525951893@s.whatsapp.net',
      phone_e164: '972525951893'
    };
    // Should skip name with @ and use formatted phone
    expect(getConversationDisplayName(thread)).toBe('+972525951893');
  });
});
