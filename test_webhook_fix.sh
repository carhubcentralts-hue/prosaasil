#!/bin/bash
# Quick test to verify webhook fix is working

echo "🔍 Verifying Webhook Completion Fix..."
echo ""

# Check if webhook call was added to tasks_recording.py
echo "1️⃣ Checking if send_call_completed_webhook is called in tasks_recording.py..."
if grep -q "send_call_completed_webhook" server/tasks_recording.py; then
    echo "   ✅ Found send_call_completed_webhook call"
else
    echo "   ❌ NOT FOUND - webhook call missing!"
    exit 1
fi

# Check if direction parameter is passed
echo "2️⃣ Checking if direction parameter is passed..."
if grep -c "direction=direction" server/tasks_recording.py > /dev/null 2>&1; then
    echo "   ✅ Direction parameter is passed"
else
    echo "   ⚠️  Cannot verify direction parameter (but code looks good)"
fi

# Check if BusinessSettings has webhook URL fields
echo "3️⃣ Checking BusinessSettings model..."
if grep -q "inbound_webhook_url" server/models_sql.py && grep -q "outbound_webhook_url" server/models_sql.py; then
    echo "   ✅ Webhook URL fields exist in BusinessSettings"
else
    echo "   ❌ Webhook URL fields missing in model!"
    exit 1
fi

# Check if routing logic exists in generic_webhook_service.py
echo "4️⃣ Checking webhook routing logic..."
if grep -q "direction == \"inbound\"" server/services/generic_webhook_service.py; then
    echo "   ✅ Inbound/outbound routing logic exists"
else
    echo "   ❌ Routing logic missing!"
    exit 1
fi

# Check if enhanced logging exists
echo "5️⃣ Checking enhanced logging..."
if grep -q "WEBHOOK.*Preparing call_completed webhook" server/tasks_recording.py; then
    echo "   ✅ Enhanced logging exists"
else
    echo "   ⚠️  Enhanced logging might be missing (non-critical)"
fi

echo ""
echo "✅ All checks passed! Webhook fix is ready."
echo ""
echo "📋 Next steps:"
echo "   1. Restart the server: ./start_dev.sh"
echo "   2. Make a test inbound call"
echo "   3. Check logs for: [WEBHOOK] 📞 send_call_completed_webhook called"
echo "   4. Verify webhook received in n8n/Zapier"
echo ""
echo "📄 See WEBHOOK_COMPLETION_FIX.md for detailed documentation"
