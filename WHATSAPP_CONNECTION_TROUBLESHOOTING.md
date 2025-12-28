# WhatsApp Connection Troubleshooting Guide
## תיעוד פתרון בעיות חיבור WhatsApp

### Overview / סקירה כללית

This document provides comprehensive guidance for troubleshooting WhatsApp connection issues in the ProSaaS CRM system using Baileys.

מסמך זה מספק הדרכה מקיפה לפתרון בעיות חיבור WhatsApp במערכת ProSaaS CRM באמצעות Baileys.

---

## Recent Improvements / שיפורים אחרונים

### 🔧 Connection Timeout Improvements

**What Changed:**
- Increased `connectTimeoutMs` from 7s to 30s
- Increased `defaultQueryTimeoutMs` from 7s to 20s
- Increased HTTP timeout from 10s to 30s
- Added retry configuration: `retryRequestDelayMs: 500`, `maxMsgRetryCount: 5`
- Added keep-alive: `keepAliveIntervalMs: 30000`

**Why:**
- 7 seconds was too aggressive for slow or unstable mobile connections
- Users on 3G/4G or with poor signal need more time to establish connection
- WhatsApp Web protocol can take 15-20 seconds to complete handshake on slow connections

### 🔄 Reconnection Strategy Improvements

**What Changed:**
- Increased max reconnection attempts from 10 to 20
- Increased max backoff delay from 60s to 120s (2 minutes)
- Changed multiplier from 2.0 to 1.5 (gentler backoff curve)

**Why:**
- Previous settings gave up too quickly on temporary network issues
- Mobile connections often have intermittent drops that recover within minutes
- Gentler backoff prevents overwhelming the WhatsApp servers while still retrying

### 📊 Enhanced Logging & Diagnostics

**What Changed:**
- Added timestamp to all connection logs
- Log QR generation duration and size
- Log phone number on connection
- Log detailed disconnect reasons with full error context
- Added structured diagnostics endpoint

**Why:**
- Makes it easier to identify where connection is failing
- Helps distinguish between network issues, auth issues, and server issues
- Provides actionable information for support team

---

## Common Issues & Solutions / בעיות נפוצות ופתרונות

### Issue 1: QR Code Not Appearing / קוד QR לא מופיע

**Symptoms / תסמינים:**
- User clicks "Generate QR" but nothing happens
- QR code shows loading indefinitely
- Frontend shows "QR required" but no QR displayed

**Possible Causes / סיבות אפשריות:**
1. Baileys service not running
2. Session stuck in "starting" state
3. Network timeout before QR generated
4. File system permissions issue

**Solution Steps / שלבי פתרון:**

```bash
# 1. Check Baileys service status
curl -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/health

# 2. Check tenant-specific diagnostics
curl -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/diagnostics

# 3. Check session status
curl -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/status

# 4. Reset session if stuck
curl -X POST -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/reset

# 5. Start fresh session
curl -X POST -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/start
```

**Log Files to Check:**
- Baileys service logs: Look for "QR generated successfully"
- Check QR generation duration - should be under 1 second
- Look for "qr_code.txt" file creation in storage/whatsapp/business_X/auth/

### Issue 2: Connection Takes Too Long / חיבור לוקח זמן רב

**Symptoms / תסמינים:**
- User scans QR code successfully
- Phone shows "Connecting..."  for 30+ seconds
- Eventually times out or fails

**Possible Causes / סיבות אפשריות:**
1. Slow mobile network (3G or weak 4G signal)
2. WhatsApp servers overloaded
3. Firewall blocking WebSocket connections
4. DNS resolution issues

**Solution Steps / שלבי פתרון:**

1. **Check Connection State:**
```bash
# Monitor connection progress
watch -n 2 'curl -s -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/status'
```

2. **Verify Network Path:**
```bash
# From server, test connection to WhatsApp
ping web.whatsapp.com

# Check DNS resolution
nslookup web.whatsapp.com

# Test WebSocket connectivity
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" https://web.whatsapp.com/ws
```

3. **Increase Timeout (if needed):**

**Note:** Current timeouts are already optimized:
- `connectTimeoutMs: 30000` (30 seconds)
- `defaultQueryTimeoutMs: 20000` (20 seconds)

If you need even longer timeouts for extremely slow connections, edit `services/whatsapp/baileys_service.js`:
```javascript
const sock = makeWASocket({
  // ... other config
  connectTimeoutMs: 45000,  // Increase to 45s for very slow connections
  defaultQueryTimeoutMs: 30000  // Increase to 30s
});
```

**Warning:** Increasing timeouts beyond 45s is not recommended as it may cause other issues.

4. **Ask User to Improve Phone Connection:**
- Connect phone to WiFi instead of mobile data
- Move to area with better signal
- Restart phone's network connection
- Close other apps using network

### Issue 3: Frequent Disconnections / התנתקויות תכופות

**Symptoms / תסמינים:**
- Connection works initially
- Drops after a few minutes/hours
- Requires QR scan again frequently

**Possible Causes / סיבות אפשריות:**
1. Phone battery saver killing WhatsApp
2. Phone losing network connection
3. Server network instability
4. WhatsApp session expired

**Solution Steps / שלבי פתרון:**

1. **Check Reconnection Attempts:**
```bash
# Look at diagnostics
curl -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/diagnostics | jq '.session.reconnect_attempts'
```

2. **Check Logs for Disconnect Reasons:**
```bash
# Look for disconnect reasons in logs
docker logs prosaas-baileys | grep "Disconnected"
```

Common disconnect reasons:
- `428` - Connection lost (temporary network issue)
- `440` - Session replaced (user logged in from another device)
- `401` - Logged out (user logged out on phone)
- `515` - Restart required (WhatsApp server maintenance)

3. **Phone-Side Fixes:**
- Disable battery optimization for WhatsApp
- Keep WhatsApp open in background
- Enable "Keep Wi-Fi on during sleep"
- Ensure phone doesn't go into airplane mode

4. **Server-Side Fixes:**
- Ensure server has stable internet
- Check for network interface issues
- Verify Docker network is stable

### Issue 4: "Max Reconnect Attempts Reached" / "הגעת למספר הניסיונות המקסימלי"

**Symptoms / תסמינים:**
- System stops trying to reconnect
- Shows "Manual intervention required"
- WhatsApp stuck in disconnected state

**Possible Causes / סיבות אפשריות:**
1. Persistent network issue
2. Auth files corrupted
3. WhatsApp server blocking reconnection
4. Phone no longer has WhatsApp Web session

**Solution Steps / שלבי פתרון:**

1. **Full Reset:**
```bash
# Stop Baileys service
docker stop prosaas-baileys

# Clear auth files
rm -rf storage/whatsapp/business_1/auth/*

# Start Baileys service
docker start prosaas-baileys

# Generate new QR
curl -X POST -H "X-Internal-Secret: YOUR_SECRET" http://localhost:3300/whatsapp/business_1/start
```

2. **On User's Phone:**
- Open WhatsApp
- Go to Settings > Linked Devices
- Remove old "AgentLocator" session
- Scan new QR code

---

## Diagnostic Endpoints / נקודות קצה לאבחון

### GET /whatsapp/:tenantId/status
Returns current connection status.

**Response:**
```json
{
  "connected": true,
  "pushName": "Business Name",
  "hasQR": false,
  "hasSession": true,
  "hasSocket": true,
  "reconnectAttempts": 0,
  "sessionState": "connected",
  "timestamp": "2025-12-27T23:55:00.000Z"
}
```

### GET /whatsapp/:tenantId/diagnostics
Returns comprehensive diagnostic information.

**Response:**
```json
{
  "tenant_id": "business_1",
  "timestamp": "2025-12-27T23:55:00.000Z",
  "session": {
    "exists": true,
    "connected": true,
    "has_socket": true,
    "has_qr_data": false,
    "starting": false,
    "push_name": "Business Name",
    "reconnect_attempts": 0
  },
  "filesystem": {
    "auth_path": "/app/storage/whatsapp/business_1/auth",
    "auth_path_exists": true,
    "qr_file_exists": false,
    "creds_file_exists": true
  },
  "config": {
    "max_reconnect_attempts": 20,
    "base_delay_ms": 5000,
    "max_delay_ms": 120000,
    "connect_timeout_ms": 30000,
    "query_timeout_ms": 20000
  },
  "server": {
    "port": 3300,
    "host": "0.0.0.0",
    "total_sessions": 1,
    "uptime_seconds": 3600
  }
}
```

### GET /health
Basic health check - returns "ok" if service is running.

---

## Monitoring & Alerting / ניטור והתראות

### Key Metrics to Monitor

1. **Connection Success Rate**
   - Track successful connections vs failed attempts
   - Alert if success rate drops below 90%

2. **QR Generation Time**
   - Should be under 1 second
   - Alert if consistently over 2 seconds

3. **Reconnection Attempts**
   - Track average reconnection attempts per session
   - Alert if any session exceeds 10 attempts

4. **Session Uptime**
   - Track how long sessions stay connected
   - Alert if average uptime under 1 hour

### Log Patterns to Watch

**Good Connection:**
```
[WA] connection update: tenant=business_1, state=connecting
[WA] business_1: QR generated successfully in 234ms
[WA] business_1: QR saved to file
[WA] connection update: tenant=business_1, state=open
[WA] business_1: ✅ Connected! pushName=Business Name, phone=972501234567
```

**Network Timeout:**
```
[WA] connection update: tenant=business_1, state=connecting
[WA] connection update: tenant=business_1, state=close, reason=428
[WA] business_1: 🔄 Auto-reconnecting in 5s (attempt 1/20)
```

**Permanent Failure:**
```
[WA] business_1: 🔴 Max reconnect attempts (20) reached
[WA] business_1: Giving up after 20 attempts. Manual intervention required.
```

---

## Configuration Options / אפשרויות תצורה

### Timeout Settings

Located in `services/whatsapp/baileys_service.js`:

```javascript
// Socket configuration
const sock = makeWASocket({
  connectTimeoutMs: 30000,      // Time to establish connection
  defaultQueryTimeoutMs: 20000,  // Time for queries to complete
  retryRequestDelayMs: 500,      // Delay between retries
  maxMsgRetryCount: 5,           // Max retries for messages
  keepAliveIntervalMs: 30000     // Keep-alive interval
});

// HTTP configuration
const keepAliveAgent = new http.Agent({ 
  keepAlive: true, 
  maxSockets: 100,
  timeout: 30000  // HTTP timeout
});

axios.defaults.timeout = 30000;  // Axios timeout
```

### Reconnection Settings

```javascript
const RECONNECT_CONFIG = {
  baseDelay: 5000,      // Initial retry delay (5s)
  maxDelay: 120000,     // Maximum retry delay (2min)
  multiplier: 1.5,      // Backoff multiplier
  maxAttempts: 20       // Max retry attempts before giving up
};
```

---

## Best Practices / שיטות עבודה מומלצות

### For Users / למשתמשים:

1. **Use Stable Connection**
   - Connect via WiFi when possible
   - Ensure good mobile signal if using data
   - Avoid switching between WiFi and mobile data

2. **Keep Phone Active**
   - Disable battery optimization for WhatsApp
   - Keep WhatsApp running in background
   - Don't force-close WhatsApp

3. **One Device at a Time**
   - Don't scan QR while WhatsApp Web is open on computer
   - Remove old linked devices before connecting new one

### For Administrators / למנהלים:

1. **Monitor Logs Regularly**
   - Check for unusual disconnect patterns
   - Watch reconnection attempt counts
   - Alert on repeated failures

2. **Maintain Server Health**
   - Ensure stable network connection
   - Keep Docker containers running
   - Monitor disk space for auth files

3. **Update Dependencies**
   - Keep Baileys library updated
   - Update WhatsApp browser fingerprint if needed
   - Monitor WhatsApp Web API changes

---

## Support Contact / יצירת קשר לתמיכה

If issues persist after following this guide:

1. Collect diagnostic information:
```bash
# Save diagnostics to file
curl -H "X-Internal-Secret: YOUR_SECRET" \
  http://localhost:3300/whatsapp/business_1/diagnostics > diagnostics.json

# Save last 100 log lines
docker logs --tail 100 prosaas-baileys > baileys-logs.txt
```

2. Include in support ticket:
   - diagnostics.json
   - baileys-logs.txt
   - Description of issue
   - Steps to reproduce
   - User's phone model and OS version
   - Network type (WiFi/3G/4G/5G)

---

## Version History / היסטוריית גרסאות

### v1.0 (2025-12-27)
- Initial troubleshooting guide
- Increased connection timeouts
- Enhanced reconnection strategy
- Added diagnostic endpoints
- Improved logging

---

## Related Documentation / תיעוד קשור

- [Baileys GitHub](https://github.com/WhiskeySockets/Baileys)
- [WhatsApp Web API Documentation](https://github.com/WhiskeySockets/Baileys/wiki)
- [ProSaaS System Architecture](./README.md)
