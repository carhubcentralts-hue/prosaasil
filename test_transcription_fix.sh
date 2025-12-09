#!/bin/bash
# Test script to verify transcription fix is working

echo "🧪 Testing Transcription Fix"
echo "=============================="
echo ""

echo "1️⃣ Checking if backend is running..."
if docker ps | grep -q phonecrm-backend; then
    echo "✅ Backend container is running"
else
    echo "❌ Backend container is not running"
    echo "   Run: docker-compose -f docker-compose.prod.yml up -d"
    exit 1
fi

echo ""
echo "2️⃣ Checking for OFFLINE_STT logs in the last 100 lines..."
docker logs --tail 100 phonecrm-backend-1 2>&1 | grep "\[OFFLINE_STT\]" | tail -20

echo ""
echo "3️⃣ Checking for errors..."
ERROR_COUNT=$(docker logs --tail 100 phonecrm-backend-1 2>&1 | grep -c "❌.*OFFLINE_STT")
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "⚠️ Found $ERROR_COUNT OFFLINE_STT errors in recent logs"
    docker logs --tail 100 phonecrm-backend-1 2>&1 | grep "❌.*OFFLINE_STT"
else
    echo "✅ No OFFLINE_STT errors found"
fi

echo ""
echo "4️⃣ Watch live logs (Ctrl+C to stop):"
echo "   docker logs -f phonecrm-backend-1 2>&1 | grep --color=always 'OFFLINE_STT\|OFFLINE_EXTRACT\|❌\|⚠️'"
echo ""
echo "5️⃣ To test with a real call:"
echo "   - Make a test call to your Twilio number"
echo "   - Watch logs with the command above"
echo "   - Look for:"
echo "     • 'Downloaded recording bytes: XXXX' (should be > 1000)"
echo "     • 'Transcript obtained: XXX chars' (should be > 0)"
echo "     • 'Saved final_transcript (XXX chars)' (should be > 0)"
echo ""
echo "=============================="
echo "✅ Fix verification complete!"
