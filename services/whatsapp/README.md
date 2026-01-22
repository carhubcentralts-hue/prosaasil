# WhatsApp Service (Baileys)

## Setup

Before building the Docker image, you must install dependencies locally:

```bash
cd services/whatsapp
npm ci --omit=dev
```

This is required because npm ci times out (~70 seconds) in GitHub Actions Runner during Docker build. The Dockerfile copies the pre-installed node_modules to avoid this timeout.

## Building

```bash
# From repository root
docker build -f Dockerfile.baileys -t baileys:latest .
```

## Running

```bash
docker run -d \
  -p 3300:3300 \
  -v $(pwd)/auth_info_baileys:/app/auth_info_baileys \
  baileys:latest
```

## Dependencies

- @whiskeysockets/baileys: 6.7.5
- express: 4.22.1 (updated for security patches)
- axios: 1.12.0 (updated for security patches)
- qrcode: 1.5.3
- cors: 2.8.5

All versions are locked to exact versions (no ^ or ~) to ensure consistency.

**Security Note**: Dependencies are regularly updated to patch vulnerabilities. Current configuration has 0 known vulnerabilities.
