# Technical Debt Registry

Items that require backend changes or cross-team coordination before they can be resolved in the frontend.

---

## BM-USERS-COUNT

**File:** `pages/Admin/BusinessManagerPage.tsx`
**Description:** The `users` field on each business card is hardcoded to `0` because the server's `/api/admin/businesses` endpoint does not yet return a per-business user count.
**Why not now:** Requires a new aggregate query or JOIN on the backend; no frontend-only fix.
**Resolution:** Add `user_count` to the business list API response, then use it here.

---

## MC-USERS-API

**File:** `shared/components/ui/ManagementCard.tsx`
**Description:** Total user count on the admin dashboard is estimated (`businessCount * 3` or `5`) because there is no `/api/admin/users/count` endpoint.
**Why not now:** Requires a dedicated backend endpoint.
**Resolution:** Create `/api/admin/users/count` (or include `total_users` in `/api/admin/stats`) and consume it in ManagementCard.

---

## PRE-EXISTING-TS-ERRORS

**Description:** Several TypeScript strict-mode errors exist in the codebase (duplicate identifiers from copy-paste, missing module declarations for relative paths using `../Badge` instead of `../components/Badge`, `any` parameter types). These are pre-existing and do not block builds (Vite is lenient), but `tsc --noEmit` reports them.
**Why not now:** Fixing all would touch ~20 files across the project and risk regressions without full E2E coverage.
**Resolution:** Fix incrementally as each file is touched in future PRs.
