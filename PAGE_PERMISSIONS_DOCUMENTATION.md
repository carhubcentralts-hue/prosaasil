# מערכת הרשאות דפים - תיעוד מלא
# Page Permissions System - Complete Documentation

## סקירה כללית / Overview

מערכת הרשאות דפים מאפשרת שליטה מלאה על הדפים/מודולים הזמינים לכל עסק ולכל תפקיד.
The page permissions system provides complete control over which pages/modules are available to each business and role.

## ארכיטקטורה / Architecture

### 1. Page Registry (מרשם דפים)
**קובץ:** `server/security/page_registry.py`

מקור אמת מרכזי לכל הדפים במערכת. כל דף חדש חייב להירשם כאן.
Single source of truth for all pages in the system. Every new page must be registered here.

```python
PAGE_REGISTRY = {
    "crm_leads": PageConfig(
        page_key="crm_leads",
        title_he="לידים",
        route="/app/leads",
        min_role="agent",
        category="crm",
        api_tags=["leads", "crm"],
        icon="Users",
        description="ניהול לידים ולקוחות פוטנציאליים"
    ),
    # ... more pages
}
```

### 2. Database Schema

**טבלה:** `business`
**עמודה חדשה:** `enabled_pages` (JSON/JSONB)

```sql
ALTER TABLE business ADD COLUMN enabled_pages JSON NOT NULL DEFAULT '[]';
```

**ברירת מחדל לעסקים קיימים:**
כל העסקים הקיימים מקבלים אוטומטית את כל הדפים (למעט דפי מנהל מערכת).

### 3. Backend Enforcement

**Decorator:** `require_page_access(page_key)`

```python
from server.security.permissions import require_page_access

@leads_bp.route("/api/leads", methods=["GET"])
@require_api_auth()
@require_page_access("crm_leads")
def list_leads():
    # ...
```

הדקורטור בודק:
1. המשתמש מאומת
2. הדף פעיל עבור העסק (business.enabled_pages)
3. תפקיד המשתמש עומד בדרישות המינימום (min_role)
4. cross-tenant protection

### 4. API Endpoints

#### GET /api/me/context
מחזיר הקשר משתמש עם הרשאות:
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "role": "admin"
  },
  "business": {
    "id": 1,
    "name": "My Business"
  },
  "enabled_pages": ["dashboard", "crm_leads", "calls_inbound", ...],
  "page_registry": {
    "crm_leads": {
      "page_key": "crm_leads",
      "title_he": "לידים",
      "route": "/app/leads",
      ...
    }
  }
}
```

#### GET /api/admin/businesses/:id/pages
מחזיר רשימת דפים עבור עסק (system_admin בלבד):
```json
{
  "business_id": 1,
  "enabled_pages": ["dashboard", "crm_leads", ...],
  "pages_by_category": {
    "crm": [
      {
        "key": "crm_leads",
        "title": "לידים",
        "enabled": true,
        "min_role": "agent"
      }
    ]
  }
}
```

#### PATCH /api/admin/businesses/:id/pages
עדכון הרשאות דפים לעסק (system_admin בלבד):
```json
{
  "enabled_pages": ["dashboard", "crm_leads", "calls_inbound"]
}
```

Creates audit log in security_events table.

#### POST /api/admin/business
יצירת עסק חדש עם הגדרות הרשאות (system_admin בלבד):
```json
{
  "name": "My Business",
  "phone_e164": "+972501234567",
  "owner_email": "owner@example.com",
  "owner_password": "password123",
  "owner_name": "Business Owner",
  "enabled_pages": ["dashboard", "crm_leads", "calls_inbound"]
}
```

אם `enabled_pages` לא מסופק, ברירת המחדל היא כל הדפים הזמינים (DEFAULT_ENABLED_PAGES).

#### PUT /api/admin/business/:id
עדכון עסק קיים כולל הרשאות דפים (system_admin בלבד):
```json
{
  "name": "Updated Business Name",
  "enabled_pages": ["dashboard", "crm_leads"]
}
```

## Frontend Components

### 1. useUserContext Hook
```typescript
import { useUserContext } from '@/features/permissions/useUserContext';

function MyComponent() {
  const { context, canAccessPage, hasRoleAccess } = useUserContext();
  
  if (canAccessPage('crm_leads')) {
    // Show content
  }
}
```

### 2. PageGuard Component
```typescript
import { PageGuard } from '@/features/permissions/PageGuard';

<Route 
  path="leads" 
  element={
    <PageGuard pageKey="crm_leads">
      <LeadsPage />
    </PageGuard>
  } 
/>
```

### 3. BusinessPagesManager Component
מרכיב ניהול הרשאות דפים מלא עבור עסק:
```typescript
import { BusinessPagesManager } from '@/features/businesses/components/BusinessPagesManager';

<BusinessPagesManager 
  businessId={businessId}
  businessName={businessName}
  onClose={() => setPagesModalOpen(false)}
  onSave={() => {
    // Refresh data
    fetchBusinesses();
  }}
/>
```

**שימוש בעמוד ניהול עסקים:**
- בעמוד `/app/admin/businesses` יש כפתור Shield (🛡️) בכל שורת עסק
- לחיצה על הכפתור פותחת מודל ניהול הרשאות
- ניתן לבחור/לבטל בחירה של דפים לפי קטגוריות
- השינויים נשמרים ישירות לדאטהבייס
- מתבצע audit log אוטומטי בטבלת security_events

### 4. Business Create/Edit Workflow
**תהליך יצירת עסק חדש:**
1. System admin לוחץ על "עסק חדש" בעמוד ניהול עסקים
2. ממלא פרטי עסק (שם, טלפון, וכו')
3. (אופציונלי) יכול לשנות את enabled_pages בבקשה
4. אם לא מסופק, מוגדרים כל הדפים כברירת מחדל
5. העסק נוצר עם ההרשאות המבוקשות

**תהליך עריכת הרשאות:**
1. System admin לוחץ על כפתור Shield בשורת העסק
2. נפתח מודל BusinessPagesManager
3. רואה את כל הדפים לפי קטגוריות עם סטטוס enabled/disabled
4. יכול לחפש דפים, לבחור הכל, או לנקות הכל
5. לוחץ "שמור שינויים" - הנתונים נשמרים ישירות
6. השינויים משתקפים מיד במערכת

## Role Hierarchy

```
agent (0)     -> יכול לגשת לדפי agent בלבד
manager (1)   -> יכול לגשת לדפי agent + manager
admin (2)     -> יכול לגשת לדפי agent + manager + admin
owner (3)     -> יכול לגשת לכל הדפים העסקיים
system_admin (4) -> יכול לגשת לכל הדפים כולל דפי מנהל מערכת
```

## Categories

```
dashboard       - סקירה כללית
crm            - CRM, לידים, לקוחות
calls          - שיחות נכנסות ויוצאות
whatsapp       - WhatsApp והודעות
communications - מיילים ותקשורת
calendar       - לוח שנה ופגישות
reports        - דוחות וסטטיסטיקות
finance        - חשבוניות וחוזים
settings       - הגדרות וניהול משתמשים
admin          - דפי מנהל מערכת (לא נכללים בהרשאות עסק)
```

## הוספת דף חדש / Adding a New Page

### צעדים:

1. **הוסף את הדף ל-PAGE_REGISTRY:**
```python
# server/security/page_registry.py
PAGE_REGISTRY["my_new_page"] = PageConfig(
    page_key="my_new_page",
    title_he="הדף החדש שלי",
    route="/app/my-page",
    min_role="agent",
    category="general",
    api_tags=["my_page"],
    icon="FileText",
    description="תיאור הדף"
)
```

2. **הוסף את הדף ל-MainLayout sidebar** (אם רצוי):
```typescript
// client/src/app/layout/MainLayout.tsx
const menuItems = [
  // ...
  { 
    icon: FileText, 
    label: 'הדף החדש שלי',
    to: '/app/my-page',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
];
```

3. **הגן על ה-route עם PageGuard:**
```typescript
// client/src/app/routes.tsx
<Route
  path="my-page"
  element={
    <PageGuard pageKey="my_new_page">
      <MyNewPage />
    </PageGuard>
  }
/>
```

4. **הגן על ה-API endpoints:**
```python
# server/routes_my_page.py
@my_bp.route("/api/my-page", methods=["GET"])
@require_api_auth()
@require_page_access("my_new_page")
def get_my_data():
    # ...
```

## Security Considerations

### 1. Backward Compatibility
- כל העסקים הקיימים מקבלים את כל הדפים כברירת מחדל
- אין שבירה של פונקציונליות קיימת
- רק עסקים חדשים יכולים להיווצר עם הרשאות מוגבלות

### 2. Multi-Tenant Isolation
- כל בדיקת הרשאה כוללת גם בדיקת business_id
- system_admin חייב לבחור business context לגישה לדפים עסקיים
- חסימת cross-tenant access ברמת הדקורטור

### 3. Audit Trail
- כל שינוי הרשאות נרשם ב-security_events
- שומר before/after state
- כולל מידע על המבצע והזמן

### 4. Fail-Safe Defaults
- ברירת מחדל: **כל הדפים מופעלים**
- מניעת נעילת משתמשים מחוץ למערכת
- system_admin תמיד יכול לגשת לדפי admin

## Testing

### Run Tests
```bash
# Unit tests
python test_permissions_system.py

# Integration tests  
python test_permissions_integration.py
```

### Test Cases Covered
- ✅ Page registry structure
- ✅ Default enabled pages
- ✅ Role hierarchy
- ✅ Page key validation
- ✅ Category grouping
- ✅ Permission enforcement
- ✅ Backward compatibility
- ✅ Cross-tenant protection

## Migration

### Migration 71: Add enabled_pages

```python
# Applied automatically in db_migrate.py
ALTER TABLE business ADD COLUMN enabled_pages JSON NOT NULL DEFAULT '[]';

UPDATE business 
SET enabled_pages = '[all default pages]' 
WHERE enabled_pages = '[]';
```

**Safe to run multiple times** - idempotent

## Troubleshooting

### User can't access a page:
1. Check business.enabled_pages includes the page_key
2. Check user.role meets page min_role requirement
3. Check page is not is_system_admin_only (unless user is system_admin)
4. Check /api/me/context returns the page in enabled_pages

### Page doesn't appear in sidebar:
1. Check menuItems in MainLayout includes the page
2. Check user role is in the page's roles array
3. Check useUserContext().canAccessPage returns true

### 403 errors:
1. Check decorator @require_page_access is applied
2. Check page_key matches PAGE_REGISTRY
3. Check business has page enabled
4. Check cross-tenant isolation (business_id matches)

## Future Enhancements

- [ ] Page-specific feature flags
- [ ] Time-based page access (trial periods)
- [ ] Usage quotas per page
- [ ] Dynamic page bundles/packages
- [ ] Role-based page customization
- [ ] Page access analytics

## Support

For issues or questions:
- Check logs: `grep "page_not_enabled" server.log`
- Check audit: `SELECT * FROM security_events WHERE event_type = 'business_pages_updated'`
- Contact: system admin
