# Assets AI Toggle Feature - Implementation Summary

## Problem Solved
Added an enable/disable toggle in the Assets (מאגר) page that controls whether the AI can use assets-related tools during conversations. When disabled, the AI cannot call any assets tools.

## Visual Implementation

```
┌──────────────────────────────────────────────────────────────┐
│  📦 מאגר                                    [+ פריט חדש]    │
│  45 פריטים                                                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 🤖  גישת AI למאגר                  [●──────] מופעל   │ │
│  │     כאשר מופעל, ה-AI יכול לחפש ולהציג פריטים מהמאגר  │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Technical Changes

### Database (Migration 82)
- Added `assets_use_ai` BOOLEAN field to `business_settings` table
- Default value: TRUE (enabled by default for backward compatibility)

### Backend Changes
1. **models_sql.py**: Added field definition
2. **db_migrate.py**: Migration 82 creates the column
3. **tools_assets.py**: Updated `is_assets_enabled()` to check both:
   - `enabled_pages` contains 'assets' (page permission)
   - `assets_use_ai` is True (AI tools permission)
4. **routes_business_management.py**: Added API support for GET/PUT

### Frontend Changes
1. **AssetsPage.tsx**: Added UI toggle with:
   - Fetch setting from API on load
   - Save setting on toggle change
   - Visual feedback during save
   - Hebrew labels and explanations

### Agent Factory
- No changes needed - existing `is_assets_enabled()` check already works
- Tools are only registered when function returns True

## Behavior

### When ENABLED (default):
✅ AI can call `assets_search()` to find assets
✅ AI can call `assets_get()` to retrieve details
✅ AI can call `assets_get_media()` to fetch images
✅ AI can share asset information in conversations

### When DISABLED:
❌ AI cannot call any assets tools
❌ Assets tools are not registered in agent
❌ AI will not access or mention assets

## Security Model

Two-layer permission system:
1. **Page Permission** (`enabled_pages`): Controls who can VIEW the assets page
2. **AI Permission** (`assets_use_ai`): Controls whether AI can ACCESS assets via tools

Both must be enabled for AI tools to work.

## Testing

All logic tests pass ✅:
- Assets enabled + AI enabled → TRUE
- Assets enabled + AI disabled → FALSE  
- Assets disabled + AI enabled → FALSE
- Assets disabled + AI disabled → FALSE

## User Experience

- Toggle is prominently displayed at top of Assets page
- Clear Hebrew explanation of what it does
- Immediate save on toggle
- Loading indicator during save
- Agent cache automatically cleared on change

## Migration Path

Existing businesses:
- `assets_use_ai` defaults to TRUE
- No change in behavior unless explicitly disabled
- Migration 82 runs automatically on next deployment
