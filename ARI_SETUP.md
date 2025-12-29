# ARI Setup and Validation Guide

## Quick Setup

### 1. ARI Configuration Files

All ARI configuration is pre-configured in `infra/asterisk/`:

✅ **`ari.conf`**:
```conf
[general]
enabled = yes
pretty = yes

[prosaas]
type = user
read_only = no
password = ${ASTERISK_ARI_PASSWORD:-prosaas_default_change_me}
```

✅ **`http.conf`**:
```conf
[general]
enabled = yes
bindaddr = 0.0.0.0
bindport = 8088
```

These files are mounted into the Asterisk container via `docker-compose.sip.yml`.

### 2. Environment Variables

Set in your `.env` file:

```bash
ASTERISK_ARI_URL=http://asterisk:8088/ari
ASTERISK_ARI_USER=prosaas
ASTERISK_ARI_PASSWORD=your_secure_password_here
```

**Important**: Replace `your_secure_password_here` with a strong password.

### 3. Validation

After starting services, validate ARI connection:

```bash
# Method 1: Using validation script
docker-compose -f docker-compose.sip.yml exec backend \
  python scripts/validate_ari_connection.py

# Method 2: Direct curl test
curl -u prosaas:your_password http://localhost:8088/ari/api-docs/resources.json
```

Expected output:
```
✅ [ARI] Connected successfully to Asterisk ARI
   Asterisk Version: 18.x.x
   ARI URL: http://asterisk:8088/ari
   Username: prosaas
```

### 4. Test Outbound Call (ARI Originate)

Test that backend can control calls through ARI:

```bash
# Set test phone number
export TEST_PHONE_NUMBER=+1234567890

# Run originate test
docker-compose -f docker-compose.sip.yml exec backend \
  python scripts/test_ari_originate.py
```

Expected flow:
1. ARI creates channel to `PJSIP/+1234567890@didww`
2. Call enters Stasis application `prosaas_ai`
3. Channel waits 5 seconds
4. Channel is hung up
5. ✅ Test passes

## Troubleshooting

### Issue: "Cannot connect to ARI"

**Solution**: Check Asterisk is running and ARI is enabled
```bash
# Check Asterisk status
docker-compose -f docker-compose.sip.yml ps asterisk

# Check Asterisk logs
docker-compose -f docker-compose.sip.yml logs asterisk | grep ARI

# Connect to Asterisk CLI
docker exec -it prosaas-asterisk asterisk -rvvv
# Then: ari show status
```

### Issue: "Authentication failed"

**Solution**: Check password matches in both places
```bash
# Check environment variable
echo $ASTERISK_ARI_PASSWORD

# Check Asterisk config (inside container)
docker exec prosaas-asterisk cat /etc/asterisk/ari.conf
```

### Issue: "Connection refused on port 8088"

**Solution**: Verify HTTP server is enabled
```bash
# Check http.conf
docker exec prosaas-asterisk cat /etc/asterisk/http.conf

# Restart Asterisk
docker-compose -f docker-compose.sip.yml restart asterisk
```

## Integration with Backend

The backend automatically validates ARI connection on startup:

**File**: `server/telephony/asterisk_provider.py`

```python
def _validate_connection(self) -> None:
    """Validate ARI connection is available."""
    response = requests.get(
        f"{self.ari_url}/asterisk/info",
        auth=(self.ari_username, self.ari_password),
        timeout=5
    )
    response.raise_for_status()
    logger.info("[ARI] Connected successfully to Asterisk ARI")
```

This runs when `AsteriskProvider` is initialized.

## No Manual Server Access Needed

✅ All configuration is in code/Docker
✅ No need to SSH into server
✅ No manual Asterisk commands required
✅ Everything provisioned via docker-compose

## Next Steps

After ARI validation passes:

1. ✅ **ARI Connection** - Validated
2. ⏭️ **Media Gateway** - Wire RTP to OpenAI
3. ⏭️ **Call Integration** - Wire ARI events to backend
4. ⏭️ **End-to-End Test** - Full call flow

---

**Status**: ARI credentials configured and ready for validation
**Phase**: 1 (Infrastructure) - Complete
**Next**: Phase 3 (Integration)
