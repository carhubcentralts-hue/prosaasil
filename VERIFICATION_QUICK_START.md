# Quick Verification Guide

## Auto-Status + Bulk Calling Production Verification

### TL;DR - Run This

```bash
# On production server (SSH into server)
cd /opt/prosaasil
docker exec -it backend python verify_master_final_production.py
```

Or if not using Docker:

```bash
# On production server with DATABASE_URL set
cd /opt/prosaasil
python verify_master_final_production.py
```

### What This Verifies

1. ✅ **Auto-Status** works for both inbound and outbound calls
2. ✅ **Status validation** - all statuses come from `lead_statuses` table
3. ✅ **Bulk calling** respects concurrency limits (default: 3 concurrent)
4. ✅ **No UI dependency** - pure backend operation
5. ✅ **Database updates** - `summary`, `last_contact_at`, `status` all updated

### Expected Output

If everything works:

```
✅✅✅ ALL ACCEPTANCE CRITERIA MET ✅✅✅

The feature is WORKING IN PRODUCTION
Auto-status and bulk calling are operational
Ready for production use
```

### If You See Warnings

**"⚠️  No recent calls found"**
- Make a test call and run again

**"⚠️  NOT VERIFIED"** for inbound/outbound
- Make test calls to verify both flows
- See MASTER_FINAL_VERIFICATION_GUIDE.md for manual test steps

### Manual Test Calls

**Test Inbound:**
1. Call business number
2. Say: "לא מעוניין, תפסיקו להתקשר"
3. Wait 30 seconds
4. Check database:
   ```sql
   SELECT status, summary FROM leads ORDER BY last_contact_at DESC LIMIT 1;
   ```
5. Should show `status = 'not_relevant'` (or equivalent)

**Test Outbound:**
1. Make outbound call to a lead
2. Say: "יכול להיות מעניין"
3. Wait 30 seconds
4. Check database - status should update to `interested` (or equivalent)

### Important Database Queries

**Check for status drift (MUST be empty):**
```sql
SELECT DISTINCT status
FROM leads
WHERE status IS NOT NULL
  AND status NOT IN (
    SELECT name FROM lead_statuses WHERE is_active = true
  );
```

**Check recent auto-status activity:**
```sql
SELECT l.id, l.status, la.payload->>'source' as source, la.at
FROM leads l
JOIN lead_activities la ON la.lead_id = l.id
WHERE la.type = 'status_change'
  AND la.payload->>'source' LIKE 'auto_%'
ORDER BY la.at DESC
LIMIT 10;
```

**Check bulk call concurrency:**
```sql
SELECT run_id,
       COUNT(*) FILTER (WHERE status='calling') AS active,
       concurrency
FROM outbound_call_jobs
JOIN outbound_call_runs ON outbound_call_runs.id = run_id
WHERE status IN ('running', 'calling')
GROUP BY run_id, concurrency;
```

Active must NEVER exceed concurrency.

### What NOT to Do

❌ Don't touch permissions  
❌ Don't touch admin routes  
❌ Don't "fix" console errors  
❌ Don't change status mapping  

### More Details

See [MASTER_FINAL_VERIFICATION_GUIDE.md](./MASTER_FINAL_VERIFICATION_GUIDE.md) for:
- Full architecture diagrams
- Detailed test procedures
- Troubleshooting guide
- Code flow explanations

---

**Quick Check:** Run the script, look for ✅✅✅ at the end.
