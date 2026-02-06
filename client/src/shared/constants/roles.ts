/**
 * ProSaaS Role Definitions — Single Source of Truth
 * Mirrors backend ROLE_HIERARCHY from server/security/page_registry.py
 * Any change here must be reflected in the backend.
 */

export const ROLE_KEYS = {
  AGENT: 'agent',
  MANAGER: 'manager',
  ADMIN: 'admin',
  OWNER: 'owner',
  SYSTEM_ADMIN: 'system_admin',
} as const;

export type RoleKey = (typeof ROLE_KEYS)[keyof typeof ROLE_KEYS];

/**
 * Numeric privilege level per role — higher = more access.
 * Must stay in sync with backend ROLE_HIERARCHY.
 */
export const ROLE_LEVEL: Record<RoleKey, number> = {
  [ROLE_KEYS.AGENT]: 0,
  [ROLE_KEYS.MANAGER]: 1,
  [ROLE_KEYS.ADMIN]: 2,
  [ROLE_KEYS.OWNER]: 3,
  [ROLE_KEYS.SYSTEM_ADMIN]: 4,
};

/** Roles that are considered "admin-level" for UI gating */
const ADMIN_ROLES: ReadonlySet<string> = new Set([
  ROLE_KEYS.ADMIN,
  ROLE_KEYS.OWNER,
  ROLE_KEYS.SYSTEM_ADMIN,
]);

/** Check whether a role string has admin-or-above privileges */
export function isAdminRole(role: string | undefined | null): boolean {
  if (!role) return false;
  return ADMIN_ROLES.has(role);
}

/** Compare two roles: does `userRole` meet the minimum of `requiredRole`? */
export function meetsRoleRequirement(
  userRole: string | undefined | null,
  requiredRole: string,
): boolean {
  if (!userRole) return false;
  const userLevel = ROLE_LEVEL[userRole as RoleKey] ?? 0;
  const requiredLevel = ROLE_LEVEL[requiredRole as RoleKey] ?? 0;
  return userLevel >= requiredLevel;
}
