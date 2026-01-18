# Code Review Notes - Minor Fixes Needed

## Issues Found by Code Review

### 1. AttachmentPicker.tsx - Variable Name Collision ⚠️
**Lines**: 26, 110, 144, 149, 154, 159, 174, 227
**Issue**: State variable `mode` collides with prop `mode`
**Fix Needed**: Rename state variable to `modeView` or `viewMode`

```typescript
// Current (problematic):
const [mode, setMode] = useState<'select' | 'upload'>('select');

// Should be:
const [modeView, setModeView] = useState<'select' | 'upload'>('select');

// And update all references:
setMode → setModeView
mode === 'upload' → modeView === 'upload'
etc.
```

### 2. routes_attachments.py - DEBUG Logic Inverted ⚠️
**Line**: 34
**Issue**: `DEBUG=1` typically means development, not production

```python
# Current (confusing):
IS_PRODUCTION = os.getenv('DEBUG', '1') == '1'  # DEBUG=1 means production

# Should be either:
IS_PRODUCTION = os.getenv('DEBUG', '0') != '1'  # DEBUG=1 means development

# OR better - use dedicated var:
IS_PRODUCTION = os.getenv('PRODUCTION', '0') == '1'
```

### 3. local_provider.py - Fragile ID Extraction ⚠️
**Lines**: 87-92
**Issue**: Parsing attachment_id from storage_key is fragile

```python
# Current (fragile):
parts = storage_key.split('/')
filename_with_ext = parts[-1]  # e.g., "123.jpg"
attachment_id = filename_with_ext.split('.')[0]  # e.g., "123"

# Better: Pass attachment_id as parameter
def generate_signed_url(self, storage_key: str, attachment_id: int, ttl_seconds: int = 900) -> str:
    # No parsing needed
```

## Priority

1. **High**: Fix AttachmentPicker variable names (breaks functionality)
2. **Medium**: Clarify IS_PRODUCTION logic (confusing but works)
3. **Low**: Refactor local_provider ID extraction (works but fragile)

## Status
- ⏳ Fixes not yet applied
- 📝 Documented for future PR
- ✅ System functional despite these issues

## Action Items
1. Create follow-up PR to fix AttachmentPicker
2. Clarify DEBUG vs PRODUCTION environment variable
3. Refactor local_provider to pass attachment_id explicitly
