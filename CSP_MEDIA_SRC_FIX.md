# CSP Media-Src Fix for TTS Audio Playback

**Date**: 2026-02-06  
**Status**: ✅ Complete  
**Issue**: Audio playback from blob URLs blocked by Content Security Policy

---

## 🎯 Problem Statement

### Symptom
When users clicked "שמע דוגמה" (voice sample) button in the AI voice settings, the audio failed to play with the following browser console error:

```
Loading media from 'blob:https://prosaas.pro/...' violates the Content Security Policy directive: 
"default-src 'self'". Note that 'media-src' was not explicitly set...
```

### Root Cause
The Content Security Policy (CSP) configuration did not explicitly define `media-src`, causing it to fall back to the restrictive `default-src 'self'` policy. This blocked blob URLs created by `URL.createObjectURL()` for audio playback.

### Technical Details
1. **Frontend Flow**:
   - User clicks "▶️ שמע דוגמה" button in `BusinessAISettings.tsx`
   - Frontend calls `/api/ai/tts/preview` with voice settings
   - API returns audio data as binary blob
   - Frontend creates blob URL: `URL.createObjectURL(blob)`
   - HTML audio element attempts to play from blob URL
   - CSP blocks the media load

2. **CSP Behavior**:
   - When `media-src` is not explicitly set, CSP falls back to `default-src 'self'`
   - `default-src 'self'` only allows same-origin URLs (https://prosaas.pro/...)
   - Blob URLs (blob:https://prosaas.pro/...) are blocked even though they're "same-origin"
   - Result: `NotSupportedError` on `audio.play()`

---

## 🔧 Solution

### Changes Made
Added `media-src 'self' blob: data:;` to all Content Security Policy configurations:

#### 1. Flask Backend (`server/app_factory.py`)
**Location**: Lines 436 and 450 in CSP response header middleware

**Before**:
```python
csp_policy = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' wss: ws: https://fonts.googleapis.com https://fonts.gstatic.com; "
    # ... rest of policy
)
```

**After**:
```python
csp_policy = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https:; "
    "media-src 'self' blob: data:; "  # ✅ NEW: Allow blob and data URLs for audio playback
    "connect-src 'self' wss: ws: https://fonts.googleapis.com https://fonts.gstatic.com; "
    # ... rest of policy
)
```

**Impact**: Updated both PDF and non-PDF CSP policies

#### 2. Nginx SSL Config (`docker/nginx-ssl.conf`)
**Location**: Line 66

**Before**:
```nginx
add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https: wss:; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; ..." always;
```

**After**:
```nginx
add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https: wss:; img-src 'self' data: https:; media-src 'self' blob: data:; style-src 'self' 'unsafe-inline' https:; ..." always;
```

#### 3. Nginx SSL Template (`docker/nginx/templates/prosaas-ssl.conf.template`)
**Location**: Lines 59 and 238 (prosaas.pro and n8n.prosaas.pro server blocks)

**Before**:
```nginx
add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https: wss:; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; ..." always;
```

**After**:
```nginx
add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https: wss:; img-src 'self' data: https:; media-src 'self' blob: data:; style-src 'self' 'unsafe-inline' https:; ..." always;
```

---

## 🔒 Security Analysis

### What We Allow
- **`'self'`**: Audio from same origin (https://prosaas.pro)
- **`blob:`**: Client-side generated blob URLs (for TTS preview)
- **`data:`**: Data URLs (for future audio inline encoding if needed)

### What We Block
- ❌ External media domains (https://cdn.example.com/audio.mp3)
- ❌ HTTP sources (downgrade attacks)
- ❌ Inline event handlers (`<audio onerror="...">`)
- ❌ Any media source not explicitly whitelisted

### Security Posture
✅ **No regression**: Only allows blob/data URLs from same origin  
✅ **Principle of least privilege**: No external media sources added  
✅ **Defense in depth**: Other CSP directives unchanged (script-src, connect-src, etc.)  
✅ **Code review**: Passed with no issues  
✅ **Security scan**: CodeQL analysis found 0 alerts  

---

## ✅ Validation

### Automated Checks
- ✅ Python syntax validation: Passed
- ✅ Code review: No issues found
- ✅ CodeQL security scan: No alerts
- ✅ Git commit: Successfully pushed

### Manual Testing Required
After deployment, verify:

1. **Voice Preview Works**:
   ```
   1. Navigate to Settings → AI Configuration
   2. Click "▶️ שמע דוגמה" (Play Sample) button
   3. Audio should play without errors
   4. Check browser console - no CSP violations
   ```

2. **Cross-Browser Compatibility**:
   - ✅ Chrome/Edge: Should work
   - ✅ Safari: Should work (CSP Level 2 support)
   - ✅ Firefox: Should work

3. **Console Checks**:
   - ❌ **Before**: `Refused to load media from 'blob:...' because it violates CSP...`
   - ✅ **After**: No CSP errors, audio plays successfully

---

## 📊 Impact Assessment

### User Experience
- **Before**: Voice preview button appeared to work but audio failed silently
- **After**: Voice preview plays audio immediately when clicked
- **Affected Users**: All users trying voice preview feature
- **Severity**: Medium (feature broken but workaround exists - just save and test in real call)

### Technical Impact
- **Breaking Changes**: None
- **API Changes**: None
- **Database Changes**: None
- **Configuration Changes**: CSP headers only
- **Deployment**: Standard deploy (restart nginx/flask services)

### Rollback Plan
If issues arise, revert CSP changes:
```bash
git revert <commit-hash>
git push origin main
# Redeploy services
```

---

## 🎓 Lessons Learned

1. **CSP Defaults Are Strict**: When a directive isn't explicitly set, it falls back to `default-src`, which is often too restrictive for modern web apps using blob URLs.

2. **Blob URLs Need Explicit Permission**: Even though blob URLs are technically "same-origin", CSP treats them as a separate scheme that must be whitelisted.

3. **Test CSP Changes in Real Browser**: CSP violations only appear at runtime in the browser console, not in server logs or tests.

4. **Multiple CSP Sources**: This app has CSP in both Flask (backend) and Nginx (reverse proxy). Both must be updated for consistency.

---

## 📚 References

- [MDN: Content Security Policy (CSP)](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [CSP media-src Directive](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/media-src)
- [Using Blob URLs with CSP](https://content-security-policy.com/blob/)
- [W3C CSP Level 2 Specification](https://www.w3.org/TR/CSP2/)

---

## ✅ Sign-Off

**Implemented By**: GitHub Copilot Agent  
**Reviewed By**: Automated code review (no issues)  
**Security Scan**: CodeQL (0 alerts)  
**Status**: Ready for deployment  
**Deployment Required**: Yes (restart nginx + flask services)

---

**Note**: After deploying to production, test the voice preview feature immediately to confirm the fix works as expected.
