# Blueprint Registration Analysis

## Current State

### Blueprints WITH url_prefix='/api'
- `search_api` (routes_search.py) - Has `url_prefix='/api'`, routes like `/search`

### Blueprints WITHOUT url_prefix (routes include full /api/ path)
- `api_adapter_bp` - Routes like `/api/dashboard/stats`
- `admin_bp` - Routes like `/api/admin/businesses`
- `biz_mgmt_bp` - Routes like `/api/business/current`
- `leads_bp` - Routes like `/api/leads`, `/api/notifications`
- `health_bp` - Routes like `/api/health` (ADDED)
- `whatsapp_bp` - Has `url_prefix='/api/whatsapp'`, routes like `/status`
- `crm_bp` - Need to check
- `status_management_bp` - Need to check

## Issues Found

1. **Critical blueprints registered at END of try-except block** 
   - If any earlier import fails, `api_adapter_bp` and `health_bp` don't get registered
   - Solution: Move to separate try-except or earlier in registration

2. **Need to verify all blueprint route definitions are consistent**

## Frontend → Backend Mapping

| Frontend Call | Expected Backend Route | Blueprint | File |
|--------------|----------------------|-----------|------|
| /api/dashboard/stats | /api/dashboard/stats | api_adapter_bp | api_adapter.py |
| /api/dashboard/activity | /api/dashboard/activity | api_adapter_bp | api_adapter.py |
| /api/notifications | /api/notifications | leads_bp | routes_leads.py |
| /api/business/current | /api/business/current | biz_mgmt_bp | routes_business_management.py |
| /api/admin/businesses | /api/admin/businesses | admin_bp | routes_admin.py |
| /api/search | /api/search | search_api | routes_search.py |
| /api/whatsapp/status | /api/whatsapp/status | whatsapp_bp | routes_whatsapp.py |
| /api/whatsapp/templates | /api/whatsapp/templates | whatsapp_bp | routes_whatsapp.py |
| /api/crm/threads | /api/crm/threads | crm_bp | routes_crm.py |
| /api/statuses | /api/statuses | status_management_bp | routes_status_management.py |
