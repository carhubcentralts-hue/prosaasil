# P1 CSRF Exemptions Audit Summary

## Overview

Analyzed 76 CSRF exemptions in the codebase using automated audit script.

## Findings

### ✅ Legitimate Exemptions (50 webhooks + auth endpoints)

**Webhooks (50)**: All Twilio, WhatsApp, n8n, and external webhooks are correctly exempt.
- These endpoints receive requests from external services
- Cannot send CSRF tokens
- Protected by other means (signature validation, internal secrets)

**Authentication Endpoints (4)**:
- `login` - Must be exempt (establishes session before CSRF token available)
- `refresh_token` - Must be exempt (token refresh flow)
- `logout` - Can be exempt (standard practice)
- `init_admin` - Setup endpoint, can be exempt

### ⚠️ Suspicious Exemptions (22 internal API endpoints)

These endpoints use session-based authentication (`@require_api_auth`) and modify state, but are marked as CSRF exempt:

**Business Management (6 endpoints)**:
- `update_current_business_settings` (POST/PUT)
- `create_faq`, `update_faq`, `delete_faq` (POST/PUT/DELETE)
- `update_business_pages` (POST/PUT)

**AI Topics (6 endpoints)**:
- `update_ai_settings` (POST/PUT)
- `create_topic`, `update_topic`, `delete_topic` (POST/PUT/DELETE)
- `rebuild_embeddings`, `reclassify_call_topic`, `reclassify_lead_topic` (POST)

**AI Prompts (5 endpoints)**:
- Various prompt management endpoints (GET/POST/PUT)

**Admin Channels (2 endpoints)**:
- `create_channel`, `remove_channel` (POST/DELETE)

**Other (3 endpoints)**:
- UI routes endpoints

## Risk Assessment

**Security Risk**: MEDIUM-HIGH
- These endpoints use session cookies for authentication
- Session cookies are automatically sent by browsers
- Without CSRF protection, vulnerable to CSRF attacks from malicious sites
- An attacker could trick a logged-in user into creating/updating/deleting business data

**Impact**: 
- Unauthorized modification of business settings
- Unauthorized CRUD operations on FAQs, topics, prompts
- Potential data loss or corruption

## Recommendation

### Immediate Action Required:

1. **Remove CSRF exemptions** from the 22 internal API endpoints that:
   - Use session-based authentication (`@require_api_auth`)
   - Perform state-changing operations (POST/PUT/PATCH/DELETE)
   - Are NOT webhooks or external integrations

2. **Verify frontend sends CSRF tokens**:
   - Check that the frontend includes CSRF tokens in API requests
   - The token should be read from the `csrf_token` cookie
   - Sent as `X-CSRFToken` header (already configured in app_factory.py)

3. **Test thoroughly** before deployment:
   - Test each affected endpoint
   - Verify no 403 CSRF errors in normal operation
   - Verify CSRF protection actually blocks unauthorized requests

### Implementation Notes:

The exemptions were likely added because:
1. Initial development without CSRF setup
2. Quick fixes to unblock development
3. Misunderstanding of when CSRF protection is needed

**Correct approach**:
- Webhooks: Exempt (external, can't send tokens)
- Auth endpoints: Exempt (establish session)
- Internal session-based APIs: Protected (use CSRF tokens)
- Token-based APIs (JWT in header): Don't need CSRF protection

## Files to Modify

```
server/routes_business_management.py (6 exemptions to remove)
server/routes_ai_topics.py (6 exemptions to remove)  
server/routes_ai_prompt.py (5 exemptions to remove)
server/routes_admin_channels.py (2 exemptions to remove)
server/ui/routes.py (3 exemptions to review)
```

## Testing Checklist

After removing exemptions:
- [ ] Test FAQ CRUD operations
- [ ] Test business settings updates
- [ ] Test AI topics CRUD
- [ ] Test AI prompt updates
- [ ] Test channel management
- [ ] Verify no 403 errors in normal operation
- [ ] Verify CSRF protection blocks attacks

## Audit Script

Created `scripts/audit_csrf_exemptions.py` for ongoing monitoring.
Run periodically to ensure no new suspicious exemptions are added.
