# Fix: "Failed to fetch dynamically imported module" 

## Problem

This is a classic issue with Vite/React applications using lazy-loaded chunks. After deployment, users with cached HTML may try to fetch old chunk files that no longer exist, resulting in:

```
Failed to fetch dynamically imported module: /assets/LeadsPage-0MDetWmx.js
```

This happens because:
1. User's browser cached the old `index.html` (with references to old chunk hashes)
2. Server deployed new version with different chunk hashes
3. Browser tries to load old chunks → 404 error or HTML returned instead of JS

## Solution: 3-Layer Defense

### Layer 1: NGINX Cache Headers (Most Important) ✅

**Goal**: Ensure `index.html` is never cached, but hashed assets are cached forever.

#### Changes Made:

**All nginx configs** (`docker/nginx.conf`, `docker/nginx-ssl.conf`, `docker/nginx/frontend-static.conf`):

1. **Assets with hash** (`/assets/*.js`) - Long cache + immutable:
```nginx
location /assets/ {
    try_files $uri =404;  # ← CRITICAL: Return 404, not index.html
    expires 1y;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
}
```

2. **index.html** - No cache:
```nginx
location = /index.html {
    add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0" always;
    add_header Pragma "no-cache" always;
    add_header Expires "0" always;
}
```

3. **SPA fallback routes** - No cache:
```nginx
location / {
    try_files $uri $uri/ /index.html;
    add_header Cache-Control "no-store" always;
}
```

**Why `try_files $uri =404` is critical:**
- Without it, nginx returns `index.html` when a chunk is not found
- Browser receives HTML instead of JS → "Failed to fetch dynamically imported module"
- With `=404`, browser gets proper 404 status → can handle error correctly

### Layer 2: Service Worker ✅

**Status**: Already correctly configured in `/client/public/sw.js`

The service worker:
- ✅ Has `skipWaiting()` - activates immediately on update
- ✅ Has `clients.claim()` - takes control of all pages immediately  
- ✅ Does NOT cache HTML or JS chunks (only handles push notifications)
- ✅ Safe to keep enabled

### Layer 3: Client-Side Error Guard ✅

**File**: `/client/src/main.tsx`

**Added**: Auto-reload guard that catches chunk loading errors:

```typescript
// 🛡️ CLIENT GUARD: Auto-reload on chunk load errors
(function () {
  const KEY = "chunk_reload_once";
  window.addEventListener("error", (e) => {
    const msg = String(e?.message || "");
    if (msg.includes("Failed to fetch dynamically imported module") ||
        msg.includes("Loading chunk") ||
        msg.includes("ChunkLoadError")) {
      console.warn('[CHUNK-GUARD] Detected chunk load error, reloading once...', msg);
      if (!sessionStorage.getItem(KEY)) {
        sessionStorage.setItem(KEY, "1");
        location.reload(); // Hard reload once only
      } else {
        console.error('[CHUNK-GUARD] Already reloaded once, not reloading again to prevent loop');
      }
    }
  });
})();
```

**How it works**:
1. Detects chunk loading errors
2. Reloads the page ONCE (prevents infinite loop)
3. After reload, fresh `index.html` loads → correct chunks → problem solved

## Verification

### After Deployment:

1. **Check index.html is NOT cached**:
   - Open DevTools → Network tab
   - Load the site
   - Find `index.html` request
   - Verify headers: `Cache-Control: no-store`

2. **Check assets ARE cached**:
   - Find any `/assets/*.js` request
   - Verify headers: `Cache-Control: public, max-age=31536000, immutable`

3. **Test 404 behavior**:
   ```bash
   curl -I https://prosaas.pro/assets/nonexistent-chunk-abc123.js
   # Should return: HTTP 404 (NOT 200 with HTML)
   ```

4. **Simulate the bug** (before deploy):
   - Open app in browser
   - Note current chunk hashes in DevTools → Sources
   - Deploy new version
   - In old tab, navigate to trigger lazy load
   - Should auto-reload and work (thanks to Layer 3)

### Expected Behavior:

- ✅ Fresh visitors: Always get latest chunks (Layer 1)
- ✅ Users with stale cache: Auto-reload once and work (Layer 3)  
- ✅ No more "Failed to fetch dynamically imported module" in production
- ✅ No infinite reload loops (sessionStorage guard)

## Deployment Best Practices

To further minimize risk:

1. **Upload order**: Upload assets FIRST, then `index.html` last
2. **Atomic deploys**: Build to new directory, switch symlink atomically
3. **Monitor**: Watch for chunk errors in logs/Sentry after deploy

## Files Modified

- `docker/nginx.conf` - Main HTTP nginx config
- `docker/nginx-ssl.conf` - HTTPS nginx config  
- `docker/nginx/frontend-static.conf` - Static-only nginx config
- `client/src/main.tsx` - Client-side error guard

## References

- Vite caching guide: https://vitejs.dev/guide/build.html#browser-caching
- nginx cache control: https://nginx.org/en/docs/http/ngx_http_headers_module.html
