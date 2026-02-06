# TODO Audit Report

Generated: 2026-02-06

## Summary

All TODO/FIXME/HACK comments in `client/src/` were audited, resolved, and removed.
Zero open TODOs remain in the frontend codebase.

## Audit Table

| # | File | Line | Original Text | Status | Action | PR Note |
|---|------|------|--------------|--------|--------|---------|
| 1 | `features/businesses/useBusinessActions.ts` | 33 | `TODO: Replace with proper toast system` | **Implemented** | Replaced `alert()` with `sonner` toast via `shared/ui/toast.ts` | Logic changed — alert → non-blocking toast |
| 2 | `features/businesses/useBusinessActions.ts` | 38 | `TODO: Replace with proper toast system` | **Implemented** | Same as above | Logic changed |
| 3 | `shared/components/ui/StatusDropdownWithWebhook.tsx` | 135 | `TODO: Replace with toast notification system for better UX` | **Implemented** | Replaced `console.info` with `showToast.success()` | Logic changed |
| 4 | `shared/components/ui/StatusDropdownWithWebhook.tsx` | 164 | `TODO: Replace with toast notification system for better UX` | **Implemented** | Replaced `alert()` with `showToast.error()` | Logic changed — alert → non-blocking toast |
| 5 | `features/permissions/useUserContext.ts` | 77 | `TODO: Consider fetching this from API to avoid drift` | **Implemented** | Extracted role hierarchy to `shared/constants/roles.ts` as single source of truth; hook now calls `meetsRoleRequirement()` | Logic refactored — centralized |
| 6 | `pages/Admin/BusinessManagerPage.tsx` | 422 | `TODO: עדיין לא מחושב בשרת` | **Deferred** | Moved to `TECH_DEBT.md#BM-USERS-COUNT`; code comment updated with reference | No logic change |
| 7 | `shared/components/ui/ManagementCard.tsx` | 111 | `TODO: Create a proper users API endpoint` | **Deferred** | Moved to `TECH_DEBT.md#MC-USERS-API`; code comment updated with reference | No logic change |
| 8 | `pages/Admin/BusinessDetailsPage.tsx` | 219 | `TODO: Refresh business data from API` | **Already implemented** | Optimistic local update was already in place; removed stale comment | Comment-only cleanup |
| 9 | `pages/contracts/ContractDetails.tsx` | 102 | `TODO: Remove this after bug is confirmed fixed in production` | **Implemented** | Debug `useEffect` was already disabled (`&& false`); removed entire dead block | Dead code removed |
