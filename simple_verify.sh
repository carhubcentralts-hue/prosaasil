#!/bin/bash

echo "=========================================="
echo "  Verification of Outbound Bug Fixes"
echo "=========================================="
echo ""

PASS_COUNT=0
TOTAL_COUNT=0

# Test 1: Check job signature
echo "[TEST 1] Checking create_lead_from_call_job signature..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if grep -q "def create_lead_from_call_job(call_sid: str):" server/jobs/twilio_call_jobs.py; then
    echo "  ✅ PASS: Function signature is correct"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: Function signature is incorrect"
fi

# Test 2: Check job fetches CallLog
echo ""
echo "[TEST 2] Checking job fetches CallLog..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if grep -q "CallLog.query.filter_by(call_sid=call_sid)" server/jobs/twilio_call_jobs.py; then
    echo "  ✅ PASS: Job fetches CallLog by call_sid"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: Job doesn't fetch CallLog"
fi

# Test 3: Check model has error_message
echo ""
echo "[TEST 3] Checking CallLog model has error_message..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if grep -q "error_message = db.Column(db.Text, nullable=True)" server/models_sql.py; then
    echo "  ✅ PASS: error_message field exists"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: error_message field missing"
fi

# Test 4: Check model has error_code
echo ""
echo "[TEST 4] Checking CallLog model has error_code..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if grep -q "error_code = db.Column(db.String(64), nullable=True)" server/models_sql.py; then
    echo "  ✅ PASS: error_code field exists"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: error_code field missing"
fi

# Test 5: Check migration exists
echo ""
echo "[TEST 5] Checking migration file exists..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if [ -f "migration_add_call_log_error_fields.py" ]; then
    echo "  ✅ PASS: Migration file exists"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: Migration file missing"
fi

# Test 6: Check cleanup uses error_message
echo ""
echo "[TEST 6] Checking cleanup sets error_message..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if grep -q "error_message='Stale record - no call_sid received from Twilio'" server/routes_outbound.py; then
    echo "  ✅ PASS: Cleanup sets error_message"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: Cleanup doesn't set error_message"
fi

# Test 7: Check enqueue calls simplified (no from_number/to_number/business_id)
echo ""
echo "[TEST 7] Checking enqueue calls are simplified..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
# Count lines with create_lead_from_call_job and extra params in same context
if ! grep -A5 "create_lead_from_call_job" server/routes_twilio.py | grep -E "(from_number=|to_number=|business_id=)" | grep -v "# "; then
    echo "  ✅ PASS: Enqueue calls simplified (no extra params)"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "  ❌ FAIL: Enqueue calls still have old parameters"
fi

echo ""
echo "=========================================="
echo "  Results: $PASS_COUNT/$TOTAL_COUNT tests passed"
echo "=========================================="

if [ $PASS_COUNT -eq $TOTAL_COUNT ]; then
    echo ""
    echo "🎉 SUCCESS: All fixes are in place!"
    echo ""
    echo "Next steps:"
    echo "1. Deploy to production"
    echo "2. Run: python migration_add_call_log_error_fields.py"
    echo "3. Restart workers"
    echo "4. Test 10 outbound calls"
    exit 0
else
    echo ""
    echo "❌ Some tests failed - review above"
    exit 1
fi
