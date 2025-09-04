# WhatsApp System Manual Testing Checklist
## רשימת בדיקות ידניות למערכת WhatsApp - 15 דקות

### Phase 1: Basic Connectivity (5 דקות)

#### ✅ 1.1 Environment Setup
- [ ] All required environment variables set in Replit Secrets
- [ ] PUBLIC_BASE_URL points to correct domain
- [ ] WHATSAPP_PROVIDER set to "auto" or specific provider
- [ ] BAILEYS_WEBHOOK_SECRET configured and secure

#### ✅ 1.2 Service Health
- [ ] Python Flask server running without errors
- [ ] Visit `/status` endpoint shows provider status
- [ ] Database connection working (PostgreSQL)
- [ ] No critical errors in console logs

#### ✅ 1.3 Baileys Service (if used)
- [ ] Node.js Baileys service accessible at port 3001
- [ ] `/health` endpoint returns connection status
- [ ] QR code generation working (if first time)
- [ ] WhatsApp Web session authenticated

### Phase 2: Core Functionality (5 דקות)

#### ✅ 2.1 Provider Routing
- [ ] Test `/api/whatsapp/window-check` with test number
- [ ] Verify smart routing between Baileys/Twilio
- [ ] Check 24-hour window detection
- [ ] Confirm template requirement logic

#### ✅ 2.2 Message Sending
- [ ] Send test message via `/api/whatsapp/send`
- [ ] Verify message appears in database
- [ ] Check provider selection logic
- [ ] Test both Hebrew and English text

#### ✅ 2.3 Template System
- [ ] Fetch templates via `/api/whatsapp/templates`
- [ ] Verify Hebrew real estate templates exist
- [ ] Test template parameter substitution
- [ ] Check Twilio template sending (if outside 24h window)

### Phase 3: Integration Testing (5 דקות)

#### ✅ 3.1 Webhook Processing
- [ ] Test Baileys webhook with signature validation
- [ ] Test Twilio webhook with signature validation
- [ ] Verify Hebrew message processing
- [ ] Check automatic response generation

#### ✅ 3.2 Database Operations
- [ ] Verify message logging to `messages` table
- [ ] Check thread creation in `threads` table
- [ ] Test conversation history retrieval
- [ ] Confirm provider tracking

#### ✅ 3.3 Advanced Features
- [ ] Test idempotency with duplicate messages
- [ ] Verify deduplication logic
- [ ] Check failover between providers
- [ ] Test media message handling (if supported)

### Critical Success Criteria

**🟢 PASS Criteria:**
- All 12 automated tests pass
- No errors in server logs
- Messages send and receive correctly
- Database operations work
- Hebrew text handled properly

**🔴 FAIL Criteria:**
- Provider connection failures
- Database connection errors
- Message sending failures
- Template system not working
- Webhook security issues

### Quick Manual Tests

#### Test 1: Send Message
```bash
curl -X POST http://localhost:5000/api/whatsapp/send \
  -H "Content-Type: application/json" \
  -d '{"to":"972501234567","message":"שלום בדיקה","business_id":1}'
```

#### Test 2: Check Window Status
```bash
curl -X POST http://localhost:5000/api/whatsapp/window-check \
  -H "Content-Type: application/json" \
  -d '{"to":"972501234567","business_id":1}'
```

#### Test 3: Get Templates
```bash
curl http://localhost:5000/api/whatsapp/templates
```

#### Test 4: Check Provider Status
```bash
curl http://localhost:5000/status
```

### Expected Response Times
- API calls: < 2 seconds
- Message sending: < 5 seconds
- Database operations: < 1 second
- Webhook processing: < 3 seconds

### Common Issues & Solutions

**Issue:** Baileys not connecting
**Solution:** Check QR code scan, verify WhatsApp Web session

**Issue:** Twilio authentication failed
**Solution:** Verify TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN

**Issue:** Database connection error
**Solution:** Check PostgreSQL service and connection string

**Issue:** Hebrew text garbled
**Solution:** Verify UTF-8 encoding in database and API

**Issue:** Templates not sending
**Solution:** Check Twilio WhatsApp Business API configuration

### Final Validation

After all tests pass:
1. ✅ System handles both Hebrew and English
2. ✅ Smart routing works between providers
3. ✅ 24-hour window rules enforced
4. ✅ Security measures active
5. ✅ Database logging complete
6. ✅ No memory leaks or performance issues

**Total Testing Time: ~15 minutes**
**Acceptance Criteria: 90%+ tests passing**