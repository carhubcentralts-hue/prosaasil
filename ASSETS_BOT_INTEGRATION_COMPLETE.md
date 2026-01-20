# Assets Library AI Bot Integration - Complete Documentation

## Issue Fixed
✅ **Fixed "Bot is not defined" error** in AssetsPage.tsx by adding missing import from lucide-react

## Overview
The Assets Library (מאגר) page now has a complete AI integration that allows the bot to access and use assets during conversations on both **phone calls** and **WhatsApp**.

## Features

### 1. **Toggle Control** (UI)
The AssetsPage now includes a toggle switch to enable/disable AI access to the assets library:

```tsx
// Location: client/src/pages/assets/AssetsPage.tsx (lines 429-449)
<div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
  <Bot className="h-5 w-5 text-blue-600" />
  <div className="flex-1">
    <p className="text-sm font-medium text-slate-900">גישת AI למאגר</p>
    <p className="text-xs text-slate-600">כאשר מופעל, ה-AI יכול לחפש ולהציג פריטים מהמאגר</p>
  </div>
  <label className="relative inline-flex items-center cursor-pointer">
    <input
      type="checkbox"
      checked={assetsUseAi}
      onChange={(e) => updateAiSetting(e.target.checked)}
      disabled={savingAiToggle}
      className="sr-only peer"
    />
    <!-- Toggle switch UI -->
  </label>
</div>
```

### 2. **Backend Settings** (Database)
The toggle state is stored in the `business_settings` table:

```python
# Location: server/models_sql.py (line 244)
assets_use_ai = db.Column(db.Boolean, default=True)  # Toggle for AI access to assets library
```

### 3. **AI Tools Registration** (Server)
The AI gets three powerful tools when assets are enabled:

#### Tool 1: `assets_search(query, category, tag, limit)`
Search for assets in the library:
```python
# Location: server/agent_tools/tools_assets.py (lines 88-183)
def assets_search_impl(business_id: int, query: str = None, category: str = None, 
                        tag: str = None, limit: int = 5) -> AssetsSearchOutput:
    """
    Search assets for a business
    
    Args:
        business_id: Business ID (required for multi-tenant)
        query: Search query for title/description/tags
        category: Filter by category
        tag: Filter by specific tag
        limit: Max results (default: 5)
    
    Returns:
        AssetsSearchOutput with list of matching assets
    """
```

**Returns:**
- `success`: bool
- `count`: number of results
- `items`: list of assets with:
  - `id`: Asset ID
  - `title`: Asset title
  - `short_description`: Truncated description (100 chars)
  - `tags`: List of tags
  - `category`: Category name
  - `cover_attachment_id`: ID of cover image (for displaying)

#### Tool 2: `assets_get(asset_id)`
Get complete details of a specific asset:
```python
# Location: server/agent_tools/tools_assets.py (lines 185-246)
def assets_get_impl(business_id: int, asset_id: int) -> AssetsGetOutput:
    """
    Get full asset details including all media
    
    Args:
        business_id: Business ID (required for multi-tenant)
        asset_id: Asset ID to retrieve
    
    Returns:
        AssetsGetOutput with full asset details and media
    """
```

**Returns:**
- `success`: bool
- `id`, `title`, `description`: Asset details
- `tags`: List of tags
- `category`: Category name
- `custom_fields`: Custom metadata (dict)
- `media`: List of all media items with:
  - `attachment_id`: For sending via WhatsApp
  - `role`: "cover" or "gallery"
  - `filename`: Original filename
  - `mime_type`: File type

#### Tool 3: `assets_get_media(asset_id)`
Get media list specifically for WhatsApp sending:
```python
# Location: server/agent_tools/tools_assets.py (lines 248-303)
def assets_get_media_impl(business_id: int, asset_id: int) -> AssetsGetMediaOutput:
    """
    Get media list for an asset (for WhatsApp sending)
    
    Args:
        business_id: Business ID (required for multi-tenant)
        asset_id: Asset ID to get media from
    
    Returns:
        AssetsGetMediaOutput with list of attachment_ids
    """
```

**Returns:**
- `success`: bool
- `count`: Number of media items
- `media`: List of media with:
  - `attachment_id`: ID to pass to `whatsapp_send()`
  - `role`: "cover" or "gallery"
  - `filename`: Original filename
  - `mime_type`: File type

### 4. **Integration with AI Agent** (Agent Factory)
The tools are automatically registered when assets are enabled:

```python
# Location: server/agent_tools/agent_factory.py (lines 1098-1150)
# 📦 Assets Library: Add assets tools if enabled for this business
try:
    from server.agent_tools.tools_assets import is_assets_enabled, assets_search_impl, assets_get_impl, assets_get_media_impl
    if is_assets_enabled(business_id):
        # Create wrapper tools with business_id pre-injected
        @function_tool
        def assets_search(query: str = "", category: str = "", tag: str = "", limit: int = 5):
            """חיפוש במאגר הפריטים של העסק"""
            result = assets_search_impl(business_id, query or None, category or None, tag or None, limit)
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        @function_tool
        def assets_get(asset_id: int):
            """שליפת פרטי פריט מלאים מהמאגר"""
            result = assets_get_impl(business_id, asset_id)
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        @function_tool
        def assets_get_media(asset_id: int):
            """שליפת רשימת תמונות של פריט לשליחה בוואטסאפ"""
            result = assets_get_media_impl(business_id, asset_id)
            return result.model_dump() if hasattr(result, 'model_dump') else result
        
        tools_to_use.extend([assets_search, assets_get, assets_get_media])
        logger.info(f"📦 Assets Library ENABLED for business {business_id} - assets tools added")
except Exception as e:
    logger.warning(f"⚠️ Could not load assets tools: {e}")
```

### 5. **Permission Check** (Security)
The AI can only use assets if BOTH conditions are met:

```python
# Location: server/agent_tools/tools_assets.py (lines 306-344)
def is_assets_enabled(business_id: int) -> bool:
    """
    Check if assets feature is enabled for the business AND if AI can use assets tools
    
    Args:
        business_id: Business ID to check
    
    Returns:
        True if BOTH conditions are met:
        1. 'assets' is in enabled_pages (page is accessible)
        2. assets_use_ai is True in business_settings (AI can use tools)
        
        False otherwise
    """
    try:
        from server.models_sql import Business, BusinessSettings
        
        business = Business.query.get(business_id)
        if not business:
            return False
        
        # Check if assets page is enabled
        enabled_pages = business.enabled_pages or []
        if 'assets' not in enabled_pages:
            logger.info(f"[ASSETS_TOOL] Assets page not enabled for business={business_id}")
            return False
        
        # Check if AI is allowed to use assets tools
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        if not settings or not getattr(settings, 'assets_use_ai', True):
            logger.info(f"[ASSETS_TOOL] AI tools disabled for assets in business={business_id}")
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"[ASSETS_TOOL] Could not check assets permission: {e}")
        return False
```

## Usage Scenarios

### Scenario 1: Phone Call - Information Lookup
**Customer**: "מה המחיר של הדירה ברמת גן?"

**AI Workflow**:
1. Calls `assets_search(query="דירה רמת גן")`
2. Gets list of matching assets
3. Calls `assets_get(asset_id=123)` for full details
4. Responds verbally: "הדירה ברמת גן עולה 1.5 מיליון שקלים, יש 4 חדרים ומרפסת גדולה"

**Note**: On phone calls, AI cannot send images - only verbal information.

### Scenario 2: WhatsApp - Send Images
**Customer via WhatsApp**: "תשלח לי תמונות של הדירה ברמת גן"

**AI Workflow**:
1. Calls `assets_search(query="דירה רמת גן")`
2. Gets asset ID
3. Calls `assets_get_media(asset_id=123)`
4. Gets list of `attachment_id`s
5. Calls `whatsapp_send(phone="+972...", message="הנה תמונות הדירה:", attachment_ids=[456, 457, 458])`
6. Responds: "שלחתי לך 3 תמונות של הדירה ברמת גן!"

**Note**: WhatsApp supports sending up to 5 images per message.

### Scenario 3: Search by Category
**Customer**: "מה יש לכם בקטגוריה דירות?"

**AI Workflow**:
1. Calls `assets_search(category="דירות", limit=5)`
2. Gets top 5 assets in category
3. Responds with summary of available apartments

### Scenario 4: Search by Tag
**Customer**: "יש לכם משהו עם מרפסת?"

**AI Workflow**:
1. Calls `assets_search(tag="מרפסת")`
2. Gets all assets tagged with "מרפסת"
3. Presents results to customer

## Technical Details

### Multi-Tenant Security
- All tools require `business_id` parameter
- Database queries filter by `business_id` to prevent cross-tenant data access
- Asset media checks ensure `is_deleted=False` on attachments

### Performance
- Search limited to 5 results by default (configurable)
- Description truncated to 100 chars in search results (full text in `assets_get`)
- Cover images prioritized in search results

### Error Handling
- All tools return structured responses with `success` flag
- Errors logged with `[ASSETS_TOOL]` prefix for monitoring
- Hebrew error messages for customer-facing responses

### Integration with WhatsApp
The `whatsapp_send` tool accepts `attachment_ids` from `assets_get_media`:

```python
# Location: server/agent_tools/tools_whatsapp.py (lines 25, 48-51)
class SendWhatsAppInput(BaseModel):
    attachment_ids: Optional[list[int]] = Field(None, description="List of attachment IDs to send as images (from assets_get_media or direct attachment IDs)")

# Documentation in tool:
# - Optional list of attachment IDs (from assets_get_media or direct attachment IDs)
# - Sends images/videos/documents from the system
# - Limit: 5 attachments per message
# - First image/media will include the message as caption
```

## API Endpoints (Frontend)

### Get Current Business Settings
```
GET /api/business/current
Response: { assets_use_ai: true/false, ... }
```

### Update AI Setting
```
PUT /api/business/current/settings
Body: { assets_use_ai: true/false }
Response: 200 OK or error
```

## Testing the Integration

### 1. Enable the Toggle
1. Navigate to Assets page (מאגר)
2. Toggle "גישת AI למאגר" to ON
3. Verify the setting is saved (page shows "מופעל")

### 2. Test on Phone Call
1. Make a test call to your business
2. Ask: "מה יש לכם במאגר?"
3. AI should use `assets_search()` and respond with available items

### 3. Test on WhatsApp
1. Send WhatsApp message: "תראה לי תמונות של המוצרים"
2. AI should:
   - Search assets
   - Get media
   - Send images via WhatsApp
   - Confirm: "שלחתי לך X תמונות"

### 4. Test Disable
1. Turn toggle OFF
2. Ask AI about assets - should politely decline:
   - "אין לי גישה למאגר כרגע" or similar

## Monitoring & Logs

Look for these log messages:
- `[ASSETS_TOOL] Assets page not enabled` - Page permission check
- `[ASSETS_TOOL] AI tools disabled for assets` - Toggle is OFF
- `[ASSETS_TOOL] assets_search business=X query='...' results=Y` - Search performed
- `[ASSETS_TOOL] assets_get business=X asset_id=Y media=Z` - Asset retrieved
- `[ASSETS_TOOL] assets_get_media business=X asset_id=Y count=Z` - Media retrieved
- `📦 Assets Library ENABLED for business X - assets tools added` - Tools registered

## Summary

✅ **Bot icon import fixed** - No more "Bot is not defined" error
✅ **Toggle control** - Enable/disable AI access from UI
✅ **Phone call support** - AI can lookup and verbally describe assets
✅ **WhatsApp support** - AI can search, retrieve, and send asset images
✅ **Security** - Multi-tenant isolation with business_id filtering
✅ **Permission system** - Two-level check (page enabled + AI toggle)
✅ **Error handling** - Graceful failures with Hebrew messages
✅ **Integration** - Seamlessly works with existing WhatsApp tools

The integration is **complete and production-ready**! 🎉
