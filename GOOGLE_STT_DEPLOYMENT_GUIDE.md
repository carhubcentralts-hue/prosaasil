# Google STT Docker Configuration - Deployment Guide

## Overview

This guide explains the Google Cloud Speech-to-Text (STT) configuration changes made to fix the error:
```
GOOGLE_APPLICATION_CREDENTIALS environment variable is not set
```

## What Was Fixed

The following changes were made to ensure Google STT works in production:

1. **Environment Variable**: Added `GOOGLE_APPLICATION_CREDENTIALS` pointing to the service account JSON file
2. **Volume Mount**: Mounted the service account JSON file from the host into the containers with read-only access
3. **Services Updated**: Applied to all services that may use Google STT:
   - `backend` (legacy)
   - `worker`
   - `prosaas-api`
   - `prosaas-calls`

## Prerequisites

Before deploying, ensure:
- The service account JSON file exists on the server at: `/root/secrets/gcp-stt-sa.json`
- The file has proper permissions (readable by the Docker daemon)
- The service account has the necessary Google Cloud STT API permissions

## Configuration Details

### Environment Variable
```yaml
GOOGLE_APPLICATION_CREDENTIALS: /root/secrets/gcp-stt-sa.json
```

This tells the Google Cloud SDK where to find the service account credentials.

### Volume Mount
```yaml
volumes:
  - /root/secrets/gcp-stt-sa.json:/root/secrets/gcp-stt-sa.json:ro
```

- Source: `/root/secrets/gcp-stt-sa.json` (on the host server)
- Target: `/root/secrets/gcp-stt-sa.json` (inside the container)
- Mode: `ro` (read-only for security)

## Deployment Instructions

### For Production Deployment

1. **Stop running containers:**
   ```bash
   docker compose down
   ```

2. **Rebuild and restart with force recreate:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
   ```

   The `--force-recreate` flag is **mandatory** because:
   - Environment variables are set during container creation
   - Volume mounts are configured during container creation
   - Simply restarting containers won't pick up the new configuration

### For Development Environment

1. **Stop running containers:**
   ```bash
   docker compose down
   ```

2. **Rebuild and restart:**
   ```bash
   docker compose up -d --force-recreate
   ```

## Verification

After deployment, verify the configuration:

1. **Check if the environment variable is set:**
   ```bash
   # For prosaas-api
   docker compose exec prosaas-api env | grep GOOGLE_APPLICATION_CREDENTIALS
   
   # For worker
   docker compose exec worker env | grep GOOGLE_APPLICATION_CREDENTIALS
   
   # For prosaas-calls
   docker compose exec prosaas-calls env | grep GOOGLE_APPLICATION_CREDENTIALS
   ```

2. **Check if the file is accessible:**
   ```bash
   # For prosaas-api
   docker compose exec prosaas-api ls -l /root/secrets/gcp-stt-sa.json
   
   # For worker
   docker compose exec worker ls -l /root/secrets/gcp-stt-sa.json
   
   # For prosaas-calls
   docker compose exec prosaas-calls ls -l /root/secrets/gcp-stt-sa.json
   ```

3. **Verify the file is readable (read-only):**
   ```bash
   # Should show read-only permissions
   docker compose exec prosaas-api cat /root/secrets/gcp-stt-sa.json > /dev/null && echo "✅ File is readable"
   ```

## Troubleshooting

### File Not Found Error
If you see errors like "No such file or directory":
- Verify the file exists on the host: `ls -l /root/secrets/gcp-stt-sa.json`
- Check file permissions: `chmod 644 /root/secrets/gcp-stt-sa.json`
- Ensure the path is correct in the docker-compose files

### Permission Denied Error
If containers can't read the file:
- Make the file readable: `chmod 644 /root/secrets/gcp-stt-sa.json`
- Ensure the parent directory is accessible: `chmod 755 /root/secrets`

### Environment Variable Not Set
If the environment variable doesn't appear in the container:
- Make sure you used `--force-recreate` when running `docker compose up`
- Verify the changes are in both `docker-compose.yml` and `docker-compose.prod.yml`
- Check that you're using the correct compose file combination for production

## Security Notes

1. **Read-Only Mount**: The file is mounted as read-only (`:ro`) to prevent containers from modifying the credentials
2. **File Permissions**: Keep the service account JSON file permissions restrictive (e.g., `640` or `644`)
3. **No Commit**: Never commit the actual service account JSON file to version control
4. **Backup**: Keep a secure backup of the service account JSON file

## Services Affected

The following services now have access to Google STT:

| Service | Development | Production | Purpose |
|---------|------------|------------|---------|
| `backend` | ✅ | ❌ (legacy) | Legacy service (dev only) |
| `worker` | ✅ | ✅ | Background jobs, may process audio |
| `prosaas-api` | ✅ | ✅ | REST API, may handle STT requests |
| `prosaas-calls` | ✅ | ✅ | WebSocket/Twilio streaming, handles calls |

## Related Files

- `docker-compose.yml` - Development configuration
- `docker-compose.prod.yml` - Production configuration overrides

## Support

If you encounter issues:
1. Check the container logs: `docker compose logs -f [service-name]`
2. Verify the Google Cloud service account has STT API enabled
3. Ensure the service account JSON is valid and not expired
