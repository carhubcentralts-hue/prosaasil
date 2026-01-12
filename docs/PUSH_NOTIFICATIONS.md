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

## Features

### What notifications are sent as push:

1. **WhatsApp Disconnect** - When the business's WhatsApp connection is lost
2. **Appointment Reminders** - Upcoming appointments (coming soon)
3. **New Leads** - When a new lead is created (coming soon)
4. **Task Reminders** - Due and overdue tasks (coming soon)

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
Get push notification status for current user.

## Frontend Integration

The frontend handles:
1. Checking browser support
2. Requesting notification permission
3. Registering the service worker
4. Creating and sending the subscription to the backend

## PWA / iOS Notes

On iOS Safari, push notifications only work when:
1. The site is added to the home screen ("Add to Home Screen")
2. The user grants notification permission

The UI displays guidance for iOS users to add the site to their home screen.
