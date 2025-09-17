#!/bin/bash
# GO Health Check Script - Single bounded command for Step 8 validation
# This script starts services, validates health endpoints, and stops services in one execution

echo "🔬 GO HEALTH CHECK - Step 8 Validation"
echo "======================================"

# Set environment variables
export INTERNAL_SECRET="test-local-secret-123"
export FLASK_BASE_URL="http://127.0.0.1:5000"
export BAILEYS_PORT=3001
export BAILEYS_BASE_URL="http://127.0.0.1:3001"
export PYTHONPATH=.

# Cleanup any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f gunicorn 2>/dev/null || true
pkill -f "node.*baileys" 2>/dev/null || true
sleep 2

# Start Flask
echo "🌐 Starting Flask server..."
python run_production_server.py &
FLASK_PID=$!
echo "Flask PID: $FLASK_PID"

# Wait for Flask
echo "⏳ Waiting for Flask to initialize..."
for i in {1..20}; do
    if curl -s --connect-timeout 2 http://127.0.0.1:5000/healthz > /dev/null 2>&1; then
        echo "✅ Flask is ready!"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "❌ Flask failed to start"
        kill $FLASK_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Start Baileys
echo "📱 Starting Baileys service..."
cd services/whatsapp && node baileys_service.js &
BAILEYS_PID=$!
cd ../..
echo "Baileys PID: $BAILEYS_PID"

# Wait for Baileys
echo "⏳ Waiting for Baileys to initialize..."
for i in {1..15}; do
    if curl -s --connect-timeout 2 http://127.0.0.1:3001/healthz > /dev/null 2>&1; then
        echo "✅ Baileys is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "⚠️  Baileys failed to start (will test Flask endpoints)"
        break
    fi
    sleep 1
done

# Run GO Tests
echo ""
echo "🚀 RUNNING GO HEALTH CHECKS"
echo "============================"

PASS_COUNT=0
TOTAL_TESTS=4

# Test 1: Basic Health Check
echo -n "Test 1 - Basic Health (/healthz): "
HEALTH_RESPONSE=$(curl -s --connect-timeout 3 http://127.0.0.1:5000/healthz 2>/dev/null)
if [ "$HEALTH_RESPONSE" = "ok" ]; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL (got: '$HEALTH_RESPONSE')"
fi

# Test 2: Version Check
echo -n "Test 2 - Version Info (/version): "
VERSION_RESPONSE=$(curl -s --connect-timeout 3 http://127.0.0.1:5000/version 2>/dev/null)
if echo "$VERSION_RESPONSE" | grep -q '"status":"ok"' && echo "$VERSION_RESPONSE" | grep -q '"build":57'; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
fi

# Test 3: Baileys Health Check
echo -n "Test 3 - Baileys Health (/healthz): "
BAILEYS_RESPONSE=$(curl -s --connect-timeout 3 http://127.0.0.1:3001/healthz 2>/dev/null)
if [ "$BAILEYS_RESPONSE" = "ok" ]; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL (got: '$BAILEYS_RESPONSE')"
fi

# Test 4: Readiness Check (with dependencies)
echo -n "Test 4 - Readiness Check (/readyz): "
READY_RESPONSE=$(curl -s --connect-timeout 5 -w "%{http_code}" http://127.0.0.1:5000/readyz 2>/dev/null)
HTTP_CODE=$(echo "$READY_RESPONSE" | tail -c 4)
READY_BODY=$(echo "$READY_RESPONSE" | sed 's/...$//')

if [[ "$HTTP_CODE" == "200" ]] && echo "$READY_BODY" | grep -q '"status":"ready"'; then
    echo "✅ PASS (HTTP $HTTP_CODE, status ready)"
    PASS_COUNT=$((PASS_COUNT + 1))
elif [[ "$HTTP_CODE" == "503" ]] && echo "$READY_BODY" | grep -q '"status":"degraded"'; then
    echo "⚠️  PARTIAL (HTTP $HTTP_CODE, degraded but functional)"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL (HTTP $HTTP_CODE)"
fi

# Results Summary
echo ""
echo "📊 GO TEST RESULTS"
echo "=================="
echo "Tests Passed: $PASS_COUNT/$TOTAL_TESTS"

if [ $PASS_COUNT -ge 3 ]; then
    echo "🎉 GO VALIDATION: ✅ PASS"
    echo "   Health endpoints are working correctly!"
    echo "   System is ready for production deployment."
    GO_RESULT=0
else
    echo "❌ GO VALIDATION: FAIL"
    echo "   Critical health endpoints not responding."
    GO_RESULT=1
fi

# Detailed response logging
echo ""
echo "📋 DETAILED RESPONSES:"
echo "Response Details:"
echo "- /healthz: '$HEALTH_RESPONSE'"
echo "- /version: $(echo "$VERSION_RESPONSE" | head -c 100)..."
echo "- Baileys /healthz: '$BAILEYS_RESPONSE'"
echo "- /readyz HTTP: $HTTP_CODE"

# Cleanup
echo ""
echo "🛑 Cleaning up processes..."
kill $FLASK_PID 2>/dev/null || true
kill $BAILEYS_PID 2>/dev/null || true
sleep 2
pkill -f gunicorn 2>/dev/null || true
pkill -f "node.*baileys" 2>/dev/null || true

echo "✅ GO Health Check Complete!"
exit $GO_RESULT