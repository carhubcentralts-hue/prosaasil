# Twilio Removal Checklist

This document tracks the complete removal/replacement of Twilio dependencies with Asterisk + DID + SIP infrastructure.

## ✅ Completed

### Phase 1: Core Infrastructure (12/12)
- [x] Create telephony provider base interface (`server/telephony/provider_base.py`)
- [x] Implement Asterisk provider (`server/telephony/asterisk_provider.py`)
- [x] Create ARI service (`server/services/asterisk_ari_service.py`)
- [x] Create Media Gateway service (`server/services/media_gateway/`)
- [x] Add Asterisk configuration files (`infra/asterisk/`)
- [x] Create Docker Compose for Asterisk + Media Gateway (`docker-compose.sip.yml`)
- [x] Add deployment documentation (`DEPLOY_SIP_ASTERISK.md`)
- [x] Add verification checklist (`VERIFY_SIP_MIGRATION.md`)
- [x] Update environment variables (`.env.asterisk.example`)
- [x] Add SIP trunk configuration templates
- [x] Add DID/number mapping system (in dialplan)
- [x] Add recording path management (MixMonitor)

## 🔄 In Progress

### Phase 2: Media Streaming (2/8)
- [x] Implement RTP server scaffold (`media_gateway/gateway.py`)
- [ ] Add RTP packet parsing and handling
- [ ] Add g711 ulaw codec handlers
- [ ] Connect Media Gateway to OpenAI Realtime
- [ ] Implement jitter buffer
- [ ] Add audio frame buffering (20ms)
- [ ] Implement reconnect guards
- [ ] Add debug audio dump support

### Phase 3: Call Flow Integration (0/10)
- [ ] Replace Twilio webhook routes with ARI handlers
- [ ] Update inbound call handling
- [ ] Update outbound call handling
- [ ] Implement call status tracking
- [ ] Add call event mapping (ARI → internal)
- [ ] Update call_limiter for Asterisk
- [ ] Implement hangup detection
- [ ] Add voicemail detection (15s)
- [ ] Add silence watchdog (20s)
- [ ] Test concurrent call handling

### Phase 4: Recording & Transcription (0/7)
- [ ] Configure Asterisk MixMonitor (done in extensions.conf, needs integration testing)
- [ ] Implement recording file management
- [ ] Update recording service for local files
- [ ] Integrate with existing Whisper transcription
- [ ] Add S3/MinIO upload support
- [ ] Update recording URL generation
- [ ] Test end-to-end recording flow

### Phase 5: Migration & Cleanup (0/8)
- [ ] Create feature flag for Twilio/Asterisk switch (TELEPHONY_PROVIDER env var ready)
- [ ] Update all call creation endpoints to use provider interface
- [ ] Migrate existing phone number mappings
- [ ] Update frontend calls if needed
- [ ] Create migration scripts
- [ ] Add rollback procedures
- [ ] Mark Twilio code for deprecation
- [ ] Document migration checklist

### Phase 6: Testing & Verification (0/9)
- [ ] Test inbound calls with AI
- [ ] Test outbound calls bulk
- [ ] Test barge-in functionality
- [ ] Test recording capture
- [ ] Test transcription pipeline
- [ ] Test voicemail detection
- [ ] Test silence detection
- [ ] Verify logging completeness
- [ ] Load test concurrent calls

## 📋 Twilio Code Inventory

### Files to Keep (for gradual migration)
These files should be marked as deprecated but kept functional during migration period:

1. **`server/routes_twilio.py`** (1343 lines)
   - Status: Keep for fallback
   - Mark with deprecation warnings
   - Plan: Remove after 100% Asterisk traffic

2. **`server/services/twilio_outbound_service.py`** (257 lines)
   - Status: Keep for fallback
   - Should be replaced by `AsteriskProvider.start_outbound_call()`
   - Plan: Remove after migration

3. **`server/services/twilio_call_control.py`**
   - Status: Keep for fallback
   - Contains Twilio client initialization
   - Plan: Remove after migration

### Files to Modify

1. **`server/routes_calls.py`**
   - Update to use `TelephonyProvider` interface
   - Support both Twilio and Asterisk via provider switch
   
2. **`server/media_ws_ai.py`** (3000+ lines)
   - **CRITICAL**: Do NOT modify AI logic
   - Only update media source (Twilio Media Stream → RTP)
   - Keep all VAD, barge-in, prompt layers unchanged

3. **`server/tasks_recording.py`**
   - Update to handle both Twilio recordings and local files
   - Add support for `/var/spool/asterisk/recordings/` path

4. **`server/services/recording_service.py`** (if exists)
   - Update to support local file downloads
   - Add S3/MinIO upload logic

### Files to Remove (after full migration)

1. **`server/twilio_security.py`**
   - Twilio signature verification
   - Remove when no longer using Twilio webhooks

2. **`server/routes_webhook.py`** (Twilio-specific parts)
   - Keep generic webhook handling
   - Remove Twilio-specific endpoints

### Dependencies to Update

**`pyproject.toml`**:
```toml
# Current
dependencies = [
    "twilio>=9.8.3",  # Can be removed after migration
]

# Add for Asterisk
dependencies = [
    "aiohttp>=3.9.0",  # For ARI HTTP client
    "websockets>=13.0",  # Already present for OpenAI
]
```

## 🎯 Key Implementation Tasks

### 1. Media Gateway RTP Server
**File**: `server/services/media_gateway/rtp_server.py`

Must implement:
- UDP socket server for RTP
- RTP packet parsing (header + payload)
- g711 ulaw decoding
- Jitter buffer (20-50ms)
- Session management (multiple concurrent calls)
- Audio frame streaming to OpenAI Realtime

**Pseudo-code**:
```python
class RTPServer:
    def __init__(self, host, port_range):
        self.sessions = {}  # {call_id: RTPSession}
    
    async def start(self):
        # Bind UDP sockets for RTP
        pass
    
    async def handle_packet(self, packet, addr):
        # Parse RTP header
        # Extract audio payload
        # Decode g711 ulaw
        # Buffer and forward to OpenAI
        pass
```

### 2. Call Session Bridge
**File**: `server/services/media_gateway/call_session.py`

Must implement:
- OpenAI Realtime WebSocket connection
- Audio frame forwarding (RTP → OpenAI)
- AI response forwarding (OpenAI → RTP)
- VAD state synchronization
- Barge-in coordination

### 3. Provider Adapter Integration
**File**: `server/routes_calls.py` (update existing)

Current code:
```python
from server.services.twilio_outbound_service import create_outbound_call
```

New code:
```python
from server.telephony.provider_factory import get_telephony_provider

provider = get_telephony_provider()  # Returns Twilio or Asterisk based on env
call_id = provider.start_outbound_call(tenant_id, to, from, metadata)
```

### 4. Recording Service Update
**File**: `server/tasks_recording.py` (update existing)

Add support for local recording files:
```python
def get_recording_file(call_id):
    # Check if provider is Asterisk
    if provider == "asterisk":
        # Path: /var/spool/asterisk/recordings/{tenant}/{call_id}.wav
        return local_recording_path(call_id)
    else:
        # Download from Twilio
        return download_twilio_recording(call_id)
```

## 🔒 Critical Rules (SSOT)

### DO NOT TOUCH (AI Logic)
- `server/media_ws_ai.py` - Core AI logic
- VAD implementation
- Barge-in state machine
- Prompt layer system
- Turn-taking logic

### MUST REPLACE
- All direct Twilio SDK calls
- Twilio webhook endpoints
- Twilio Media Stream handling
- Twilio recording downloads

### ADAPTER PATTERN
All telephony operations MUST go through `TelephonyProvider` interface:
```
Application Code
    ↓
TelephonyProvider (interface)
    ↓
TwilioProvider | AsteriskProvider
```

## 📊 Migration Strategy

### Phase A: Parallel Deployment (Week 1)
- Deploy Asterisk stack alongside Twilio
- Test with `TELEPHONY_PROVIDER=asterisk` in dev
- Keep Twilio as fallback

### Phase B: Shadow Traffic (Week 2)
- Route 10% of traffic to Asterisk
- Monitor metrics, errors, recordings
- Compare quality with Twilio

### Phase C: Gradual Rollout (Week 3-4)
- 25% → 50% → 75% → 100%
- Monitor at each step
- Ready to rollback at any point

### Phase D: Cleanup (Week 5)
- Remove Twilio dependencies
- Delete deprecated code
- Final documentation

## 🧪 Testing Requirements

Before marking any phase complete:

1. **Unit Tests**: All new components
2. **Integration Tests**: End-to-end call flow
3. **Load Tests**: 50 concurrent calls
4. **Quality Tests**: Audio quality metrics
5. **Regression Tests**: Existing features work

## 📈 Success Metrics

Must meet or exceed Twilio baseline:

- **Call Success Rate**: > 99%
- **Audio Quality**: MOS > 4.0
- **Latency**: Time to greeting < 2s
- **Barge-in Latency**: < 500ms
- **Recording Capture**: 100%
- **Transcription Accuracy**: > 90%
- **Cost per Minute**: < $0.02 (vs $0.074 Twilio)

## 🚨 Rollback Procedure

If any critical issue occurs:

```bash
# 1. Immediate: Switch to Twilio
export TELEPHONY_PROVIDER=twilio
docker-compose restart backend

# 2. Stop Asterisk services
docker-compose -f docker-compose.sip.yml down

# 3. Analyze logs
docker-compose -f docker-compose.sip.yml logs > rollback_logs.txt

# 4. Report issue with logs
# 5. Fix and retry
```

## 📝 Sign-Off Required

Each phase requires sign-off from:

- [ ] Technical Lead
- [ ] QA Engineer
- [ ] DevOps Engineer
- [ ] Product Manager

---

**Last Updated**: 2025-12-29
**Status**: Phase 1 Complete, Phase 2 In Progress
