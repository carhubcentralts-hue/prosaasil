# Push Notifications Setup Guide

## Overview

ProSaaS CRM supports Web Push notifications to send alerts to users' devices (desktop and mobile) even when they're not actively using the site.

## Environment Variables

Add these environment variables to your deployment:

```bash
# VAPID Keys for Web Push authentication
VAPID_PUBLIC_KEY=your_base64_encoded_public_key
VAPID_PRIVATE_KEY=your_base64_encoded_private_key
VAPID_SUBJECT=mailto:admin@your-domain.com
```

## Generating VAPID Keys

You can generate VAPID keys using one of these methods:

### Method 1: Using Python (with pywebpush)

```python
from pywebpush import vapid

vapid_keys = vapid.generate()
print(f"VAPID_PUBLIC_KEY={vapid_keys['publicKey']}")
print(f"VAPID_PRIVATE_KEY={vapid_keys['privateKey']}")
```

### Method 2: Using Node.js (with web-push)

```bash
npm install -g web-push
web-push generate-vapid-keys
```

### Method 3: Using OpenSSL

```bash
# Generate private key
openssl ecparam -name prime256v1 -genkey -noout -out vapid_private.pem

# Extract public key
openssl ec -in vapid_private.pem -pubout -out vapid_public.pem

# Convert to base64 (implementation varies by platform)
```

## Usage - Unified Notification Function

**IMPORTANT**: Always use the unified `notify_user()` function to send notifications.
This ensures both the bell (in-app) and push notifications are sent consistently.

```python
from server.services.notifications import notify_user, notify_business_owners

# After committing a DB transaction, notify a specific user:
notify_user(
    event_type='appointment_reminder',
    title='⏰ תזכורת לפגישה',
    body='יש לך פגישה בעוד שעה',
    url='/app/calendar',
    user_id=123,
    business_id=1,
    priority='high'
)

# Notify all business owners/admins (for system alerts):
notify_business_owners(
    event_type='whatsapp_disconnect',
    title='⚠️ חיבור WhatsApp נותק',
    body='יש להיכנס להגדרות ולחבר מחדש',
    url='/app/settings',
    business_id=1,
    priority='high'
)
```

### Parameters

- `event_type`: Type of notification (e.g., 'appointment_reminder', 'task_due', 'whatsapp_disconnect')
- `title`: Hebrew notification title
- `body`: Hebrew notification body text
- `url`: Deep link URL to open when notification is clicked
- `user_id`: Target user ID
- `business_id`: Business/tenant ID
- `entity_id`: Optional related entity ID
- `priority`: 'low', 'medium', or 'high'
- `save_to_bell`: Set to `False` if already saved elsewhere (default: `True`)

### When to Call

**ALWAYS** call `notify_user()` or `notify_business_owners()` AFTER `db.session.commit()`.
This ensures the notification is sent only after the related data is persisted.

## Features

### What notifications are sent as push:

1. **Task Reminders** - New reminders/tasks created
2. **WhatsApp Disconnect** - When the business's WhatsApp connection is lost
3. **Appointment Reminders** - Upcoming appointments
4. **Lead Updates** - When leads are assigned or updated

### Multi-device support

- Users can enable push notifications on multiple devices
- Each device gets its own subscription
- Deactivating on one device doesn't affect others

### Security

- All push endpoints require authentication
- Business isolation is enforced (users can only subscribe for their business)
- Invalid subscriptions (HTTP 404/410) are automatically deactivated
- VAPID private key is never exposed to the frontend

## API Endpoints

### GET /api/push/vapid-public-key
Returns the VAPID public key for client-side subscription.

### POST /api/push/subscribe
Register a new push subscription.

### POST /api/push/unsubscribe
Unregister a push subscription.

### POST /api/push/test
Send a test push notification.

### GET /api/push/status
Get push notification status for current user. Returns:
```json
{
  "supported": true,
  "vapid_configured": true,
  "subscribed": true,
  "active_subscriptions_count": 1,
  "user_id": 123,
  "business_id": 1
}
```

## Frontend Integration

The frontend handles:
1. Checking browser support
2. Requesting notification permission
3. Registering the service worker (on app boot)
4. Creating and sending the subscription to the backend

## Service Worker

The service worker (`sw.js`) is located at `/client/public/sw.js` and is served at `/sw.js` in production.

Verify it's working by:
1. Open browser DevTools → Application → Service Workers
2. Should see `sw.js` with status "Activated"
3. Or navigate directly to `https://YOUR_DOMAIN/sw.js`

## PWA / iOS Notes

On iOS Safari, push notifications only work when:
1. The site is added to the home screen ("Add to Home Screen")
2. The user grants notification permission

The UI displays guidance for iOS users to add the site to their home screen.

