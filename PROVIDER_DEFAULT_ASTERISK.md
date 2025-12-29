# Provider Default Configuration - Asterisk Only

## ✅ Current State: ASTERISK IS DEFAULT

The system is configured to use **Asterisk as the default provider**. Twilio is completely disconnected from the production flow.

### Provider Selection

**Default**: `TELEPHONY_PROVIDER=asterisk`

The provider factory (`server/telephony/provider_factory.py`) automatically defaults to Asterisk:

```python
provider_type = os.getenv("TELEPHONY_PROVIDER", "asterisk").lower()
```

### Code Changes

#### 1. Provider Factory (`server/telephony/provider_factory.py`)
- ✅ Created with `asterisk` as default
- ✅ Twilio only loaded if explicitly set to `"twilio"` (emergency fallback)
- ✅ Logs warning if Twilio is used
- ✅ Singleton pattern ensures one provider instance

#### 2. Telephony __init__ (`server/telephony/__init__.py`)
- ✅ Exports `get_telephony_provider()` function
- ✅ Exports `is_using_asterisk()` helper
- ✅ Exports `is_using_twilio()` helper

#### 3. Environment Files
- ✅ `.env.asterisk.example`: `TELEPHONY_PROVIDER=asterisk` (default)
- ✅ Twilio variables commented out with deprecation warning
- ✅ Clear comments: "DO NOT USE unless rollback required"

#### 4. Docker Compose (`docker-compose.sip.yml`)
- ✅ Backend service: `TELEPHONY_PROVIDER=${TELEPHONY_PROVIDER:-asterisk}`
- ✅ Falls back to `asterisk` if not set
- ✅ Twilio credentials marked as deprecated

#### 5. Initialization (`server/telephony/init_provider.py`)
- ✅ Logs provider on startup
- ✅ Validates Asterisk configuration
- ✅ Warns if Twilio is being used

### Usage in Code

Any code that needs to use the telephony provider should:

```python
from server.telephony import get_telephony_provider

# Get provider (defaults to Asterisk)
provider = get_telephony_provider()

# Use provider methods
call_id = provider.start_outbound_call(
    tenant_id=1,
    to_number="+1234567890",
    from_number="+0987654321"
)
```

### Verification

To verify the provider is Asterisk:

```python
from server.telephony import is_using_asterisk, is_using_twilio

assert is_using_asterisk() == True
assert is_using_twilio() == False
```

### Startup Logs

When the application starts with Asterisk (default):

```
============================================================
TELEPHONY PROVIDER INITIALIZATION
============================================================
[TELEPHONY] Initializing provider: asterisk
[ASTERISK] Initialized provider: ari_url=http://asterisk:8088/ari, app=prosaas_ai
✅ [TELEPHONY] ASTERISK PROVIDER ACTIVE (PRODUCTION)
   ARI URL: http://asterisk:8088/ari
   ARI User: prosaas
   SIP Trunk: didww
============================================================
```

If someone accidentally sets `TELEPHONY_PROVIDER=twilio`:

```
============================================================
TELEPHONY PROVIDER INITIALIZATION
============================================================
⚠️ [TELEPHONY] Using Twilio provider (LEGACY - should migrate to Asterisk)
⚠️ [TELEPHONY] TWILIO PROVIDER ACTIVE (LEGACY FALLBACK)
   This should only be used for emergency rollback
   Please migrate to Asterisk as soon as possible
   Environment: TELEPHONY_PROVIDER=twilio
============================================================
```

## No Way to Accidentally Use Twilio

### Safeguards in Place:

1. **Default is Asterisk**: `os.getenv("TELEPHONY_PROVIDER", "asterisk")`
2. **Docker Compose default**: `${TELEPHONY_PROVIDER:-asterisk}`
3. **Environment file default**: `TELEPHONY_PROVIDER=asterisk`
4. **Twilio credentials commented out**: No values in `.env.asterisk.example`
5. **Loud warnings**: Logs warn if Twilio is used
6. **Documentation**: All docs say Asterisk is default

### To Use Twilio (Emergency Only)

You would need to **explicitly**:
1. Set `TELEPHONY_PROVIDER=twilio` in `.env`
2. Uncomment and fill Twilio credentials
3. Restart services
4. Ignore the warnings in logs

This makes it nearly impossible to accidentally use Twilio.

## Migration Complete

✅ Asterisk is the default provider  
✅ Twilio is completely disconnected from normal flow  
✅ Twilio only available as explicit emergency fallback  
✅ Clear warnings if Twilio is used  
✅ No way to accidentally use Twilio  

**הכל מנותק מTwilio! רק Asterisk! 🎯**
