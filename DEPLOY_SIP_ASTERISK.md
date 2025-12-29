# Twilio to Asterisk Migration - Deployment Guide

## Overview

This guide covers the complete deployment of the Asterisk + DID + SIP system to replace Twilio for AI call handling.

## Architecture

```
Internet (SIP/DID Provider)
    ↓
Asterisk (PJSIP + ARI + MixMonitor)
    ↓ RTP (g711 ulaw)
Media Gateway (Python)
    ↓ WebSocket
OpenAI Realtime API
```

## Prerequisites

### 1. DID/SIP Provider Account
- **Provider**: DIDWW (IP-based authentication)
- **No SIP registration required** - authentication via source IP whitelist
- Requirements:
  - At least one DID (phone number) assigned to your account
  - Your server's public IP whitelisted in DIDWW portal
  - g711 ulaw codec support (standard)
  - Stable internet connection with public IP

**DIDWW Configuration**:
1. Log into DIDWW portal
2. Add your server's public IP to "Allowed IPs" under SIP Trunk settings
3. Assign DIDs to your SIP trunk
4. Note the DIDWW SIP server IPs for pjsip.conf configuration

### 2. Server Requirements
- **Minimum**: 4 CPU cores, 8GB RAM, 100GB storage
- **Recommended**: 8 CPU cores, 16GB RAM, 200GB storage
- **OS**: Ubuntu 20.04/22.04 LTS or Debian 11/12
- **Network**: Public IP with UDP ports accessible

### 3. Required Ports

**External (must be publicly accessible):**
- `5060/UDP`: SIP signaling
- `10000-10100/UDP`: RTP media (adjust range based on concurrent calls)

**Internal (Docker network only):**
- `8088/TCP`: Asterisk ARI HTTP/WebSocket
- `5000/TCP`: Backend API
- `10000-10100/UDP`: Media Gateway RTP

## Installation Steps

### Step 1: Environment Configuration

Create `.env.sip` file with SIP trunk credentials:

```bash
# Asterisk/ARI Configuration
ASTERISK_ARI_PASSWORD=your_secure_password_here
ASTERISK_ARI_USER=prosaas

# DIDWW SIP Trunk Configuration (IP-based authentication)
DIDWW_SIP_HOST=sip.didww.com
DIDWW_SIP_PORT=5060
# DIDWW source IPs for ACL (from DIDWW documentation)
DIDWW_IP_1=89.105.196.76
DIDWW_IP_2=80.93.48.76
DIDWW_IP_3=89.105.205.76

# External IP (your server's public IP - must be whitelisted in DIDWW)
EXTERNAL_IP=your.server.public.ip

# OpenAI API Key
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://user:pass@localhost/prosaas

# Public URLs
PUBLIC_BASE_URL=https://yourdomain.com
PUBLIC_HOST=yourdomain.com

# Telephony Provider Selection
TELEPHONY_PROVIDER=asterisk

# Default Tenant (for single-tenant setup)
DEFAULT_TENANT_ID=1
```

### Step 2: Deploy with Docker Compose

```bash
# Build and start all services
docker-compose -f docker-compose.sip.yml up -d

# Check service status
docker-compose -f docker-compose.sip.yml ps

# View logs
docker-compose -f docker-compose.sip.yml logs -f
```

### Step 3: Verify Asterisk Configuration

```bash
# Connect to Asterisk CLI
docker exec -it prosaas-asterisk asterisk -rvvv

# Check PJSIP endpoints
pjsip show endpoints

# Check PJSIP registration (if using registration)
pjsip show registrations

# Test ARI
curl -u prosaas:your_password http://localhost:8088/ari/asterisk/info
```

### Step 4: Configure DID Routing (DIDWW)

Configure DIDWW to route incoming calls to your server:

1. **Whitelist Your IP**: In DIDWW portal → SIP Trunks → Add your server's public IP
2. **Assign DIDs**: Assign your phone number(s) to the SIP trunk
3. **Verify Configuration**: 
   - Destination: Your server IP:5060
   - Codec: g711 ulaw
   - Authentication: IP-based (no credentials needed)

**Important**: DIDWW uses IP-based authentication. Your server's public IP MUST be whitelisted, or all calls will be rejected.

### Step 5: Test Inbound Calls

```bash
# Monitor ARI events
docker-compose -f docker-compose.sip.yml logs -f media-gateway

# Watch backend logs
docker-compose -f docker-compose.sip.yml logs -f backend

# Make a test call to your DID
# Expected flow:
# 1. Call arrives at Asterisk
# 2. Dialplan answers and starts recording
# 3. Stasis enters call
# 4. ARI creates bridge
# 5. ExternalMedia connects to Media Gateway
# 6. AI greeting plays
```

### Step 6: Test Outbound Calls

```bash
# Use existing API endpoint
curl -X POST http://localhost:5000/api/outbound/call \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": 1,
    "lead_id": 123,
    "to_number": "+1234567890"
  }'

# Check logs for call progression
docker-compose -f docker-compose.sip.yml logs -f asterisk
```

## Monitoring & Debugging

### Health Checks

```bash
# Check all services
docker-compose -f docker-compose.sip.yml ps

# Individual health checks
curl http://localhost:5000/health  # Backend
curl http://localhost:8088/ari/asterisk/info -u prosaas:password  # Asterisk
```

### Common Issues

#### 1. No Audio / One-Way Audio
**Cause**: NAT/firewall blocking RTP
**Solution**:
- Verify `EXTERNAL_IP` is correct
- Open UDP port range 10000-10100
- Check `rtp.conf` settings

#### 2. SIP Registration Failed
**Cause**: Incorrect SIP trunk credentials
**Solution**:
- Verify credentials in `.env.sip`
- Check provider's IP whitelist
- Review `pjsip show registrations`

#### 3. ARI Connection Failed
**Cause**: ARI not accessible or wrong credentials
**Solution**:
- Check `ari.conf` password
- Verify port 8088 is accessible
- Review `http.conf` settings

#### 4. Recording Not Found
**Cause**: MixMonitor path incorrect or permissions
**Solution**:
- Check `/var/spool/asterisk/recordings/` exists
- Verify Docker volume mount
- Check recording service logs

### Log Files

```bash
# Asterisk logs
docker exec prosaas-asterisk tail -f /var/log/asterisk/full

# ARI debug
docker exec prosaas-asterisk tail -f /var/log/asterisk/ari.log

# Media Gateway logs
docker-compose -f docker-compose.sip.yml logs -f media-gateway

# Backend logs
docker-compose -f docker-compose.sip.yml logs -f backend
```

## DID/Number Mapping

### Single Tenant Setup
All calls route to `DEFAULT_TENANT_ID` (configured in `.env.sip`).

### Multi-Tenant Setup
Enhance dialplan to map DIDs to tenants:

```asterisk
; extensions.conf
exten => 1234567890,1,Set(__TENANT_ID=1)
exten => 0987654321,1,Set(__TENANT_ID=2)
exten => _X.,n,Goto(from-trunk,${EXTEN},1)
```

Or use database lookup:
```asterisk
exten => _X.,1,Set(__TENANT_ID=${ODBC_GET_TENANT(${EXTEN})})
```

## Recording Configuration

### Storage Options

#### Option 1: Local Storage (Default)
Recordings stored in Docker volume `asterisk_recordings`.

```bash
# Access recordings
docker exec prosaas-asterisk ls /var/spool/asterisk/recordings/
```

#### Option 2: S3/MinIO Upload
Backend automatically uploads recordings after transcription.
Configure in backend `.env`:

```bash
# S3 Configuration
S3_BUCKET=prosaas-recordings
S3_REGION=us-east-1
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
```

### Recording Format
- **Codec**: WAV (PCM 8kHz mono)
- **Location**: `/var/spool/asterisk/recordings/{tenant_id}/{call_id}.wav`
- **Processing**: Async transcription via Whisper (existing pipeline)

## Scaling & Production

### Concurrent Call Limits

Adjust RTP port range based on expected concurrent calls:
- **10 calls**: 10000-10200 (20 ports per call)
- **50 calls**: 10000-11000 (20 ports per call)
- **100 calls**: 10000-12000 (20 ports per call)

Update `rtp.conf` and Docker port mappings accordingly.

### High Availability

For production HA setup:
1. **Load Balancer**: SIP-aware LB (OpenSIPS, Kamailio)
2. **Multiple Asterisk Instances**: Scale horizontally
3. **Shared Storage**: NFS/GlusterFS for recordings
4. **Database**: PostgreSQL with replication

### Monitoring Metrics

Track these metrics for production:
- **Call Success Rate**: Percentage of successful calls
- **Audio Quality**: MOS score, packet loss
- **Latency**: Time to first audio frame
- **Concurrent Calls**: Peak and average
- **Recording Success**: Percentage captured and transcribed

## Migration from Twilio

### Gradual Migration Strategy

1. **Phase 1**: Deploy Asterisk in parallel (test mode)
2. **Phase 2**: Route 10% of traffic to Asterisk
3. **Phase 3**: Gradually increase to 100%
4. **Phase 4**: Deprecate Twilio

### Feature Flag

Backend supports both providers simultaneously:

```python
# .env
TELEPHONY_PROVIDER=asterisk  # or "twilio" for fallback
```

### Testing Checklist

Before full migration, verify:
- [x] Inbound calls work
- [x] Outbound calls work
- [x] Barge-in functions correctly
- [x] Recordings captured
- [x] Transcription completes
- [x] Voicemail detection (15s)
- [x] Silence timeout (20s)
- [x] Concurrent call limits respected
- [x] Call quality acceptable
- [x] Logging complete

## Cost Comparison

### Twilio Costs (approximate)
- **Inbound call**: $0.0085/min
- **Outbound call**: $0.013/min
- **Recording**: $0.0025/min
- **Transcription**: $0.05/min
- **Total per min**: ~$0.074/min

### Asterisk Costs (approximate)
- **DID rental**: $1-3/month per number
- **Inbound call**: $0.004/min (DID provider)
- **Outbound call**: $0.006/min (SIP trunk)
- **Recording**: $0 (self-hosted)
- **Transcription**: $0.006/min (Whisper API)
- **Total per min**: ~$0.016/min

**Savings**: ~78% cost reduction!

## Support & Troubleshooting

### Documentation
- [Asterisk ARI Documentation](https://docs.asterisk.org/Asterisk_18_Documentation/API_Documentation/Asterisk_REST_Interface/)
- [PJSIP Configuration](https://wiki.asterisk.org/wiki/display/AST/Configuring+res_pjsip)
- [Dialplan Functions](https://wiki.asterisk.org/wiki/display/AST/Dialplan)

### Getting Help
- Check logs first (see "Log Files" section)
- Review `VERIFY_SIP_MIGRATION.md` for test scenarios
- Contact support with logs and error messages

## Security Considerations

### SIP Security
- Use strong passwords for ARI and SIP trunk
- Whitelist provider IPs in `pjsip.conf`
- Enable TLS for SIP signaling (production)
- Use SRTP for media encryption (if supported)

### Network Security
- Restrict ARI port 8088 to internal network only
- Use firewall rules for SIP/RTP ports
- Enable fail2ban for brute force protection
- Regular security audits

## Next Steps

1. Complete deployment following this guide
2. Run verification tests (see `VERIFY_SIP_MIGRATION.md`)
3. Monitor metrics for 24-48 hours
4. Gradually migrate production traffic
5. Deprecate Twilio once stable

---

**Questions or Issues?**
Refer to the troubleshooting section or contact support with detailed logs.
