import { describe, it, expect } from 'vitest';
import {
  ROLE_KEYS,
  ROLE_LEVEL,
  isAdminRole,
  meetsRoleRequirement,
} from '../shared/constants/roles';

describe('ROLE_KEYS constant', () => {
  it('defines all expected roles', () => {
    expect(ROLE_KEYS.AGENT).toBe('agent');
    expect(ROLE_KEYS.MANAGER).toBe('manager');
    expect(ROLE_KEYS.ADMIN).toBe('admin');
    expect(ROLE_KEYS.OWNER).toBe('owner');
    expect(ROLE_KEYS.SYSTEM_ADMIN).toBe('system_admin');
  });
});

describe('ROLE_LEVEL ordering', () => {
  it('assigns ascending privilege levels', () => {
    expect(ROLE_LEVEL.agent).toBeLessThan(ROLE_LEVEL.manager);
    expect(ROLE_LEVEL.manager).toBeLessThan(ROLE_LEVEL.admin);
    expect(ROLE_LEVEL.admin).toBeLessThan(ROLE_LEVEL.owner);
    expect(ROLE_LEVEL.owner).toBeLessThan(ROLE_LEVEL.system_admin);
  });
});

describe('isAdminRole', () => {
  it('returns true for admin-level roles', () => {
    expect(isAdminRole('admin')).toBe(true);
    expect(isAdminRole('owner')).toBe(true);
    expect(isAdminRole('system_admin')).toBe(true);
  });

  it('returns false for non-admin roles', () => {
    expect(isAdminRole('agent')).toBe(false);
    expect(isAdminRole('manager')).toBe(false);
  });

  it('returns false for null/undefined/empty', () => {
    expect(isAdminRole(null)).toBe(false);
    expect(isAdminRole(undefined)).toBe(false);
    expect(isAdminRole('')).toBe(false);
  });
});

describe('meetsRoleRequirement', () => {
  it('owner meets admin requirement', () => {
    expect(meetsRoleRequirement('owner', 'admin')).toBe(true);
  });

  it('agent does NOT meet admin requirement', () => {
    expect(meetsRoleRequirement('agent', 'admin')).toBe(false);
  });

  it('same role meets its own requirement', () => {
    expect(meetsRoleRequirement('manager', 'manager')).toBe(true);
  });

  it('returns false when userRole is null/undefined', () => {
    expect(meetsRoleRequirement(null, 'admin')).toBe(false);
    expect(meetsRoleRequirement(undefined, 'agent')).toBe(false);
  });
});
