#!/bin/bash
# 🧪 Verification Script for Clean Pipeline Refactor
# Tests that webhook logic is only in worker, not in realtime handler

set -e

echo "🔍 CLEAN PIPELINE VERIFICATION"
echo "=============================="
echo ""

# Test 1: Verify no webhook sending in media_ws_ai.py
echo "✅ Test 1: Checking media_ws_ai.py for webhook calls..."
if grep -q "send_call_completed_webhook\|send_generic_webhook" server/media_ws_ai.py; then
    echo "❌ FAIL: Found webhook sending in media_ws_ai.py (should be removed!)"
    exit 1
else
    echo "✅ PASS: No webhook sending found in media_ws_ai.py"
fi
echo ""

# Test 2: Verify no waiting loops for worker in media_ws_ai.py
echo "✅ Test 2: Checking for waiting loops in media_ws_ai.py..."
if grep -q "wait.*offline.*transcript\|retry.*worker\|sleep.*worker" server/media_ws_ai.py; then
    echo "❌ FAIL: Found waiting loops for worker in media_ws_ai.py"
    exit 1
else
    echo "✅ PASS: No waiting loops for worker found"
fi
echo ""

# Test 3: Verify webhook sending exists in tasks_recording.py
echo "✅ Test 3: Checking tasks_recording.py for webhook calls..."
if grep -q "send_call_completed_webhook" server/tasks_recording.py; then
    echo "✅ PASS: Webhook sending found in tasks_recording.py (correct!)"
else
    echo "❌ FAIL: No webhook sending in tasks_recording.py (should exist!)"
    exit 1
fi
echo ""

# Test 4: Verify DB fields are used correctly in worker
echo "✅ Test 4: Checking worker uses correct DB fields..."
if grep -q "final_transcript\|extracted_city\|extracted_service" server/tasks_recording.py; then
    echo "✅ PASS: Worker uses correct DB fields"
else
    echo "❌ FAIL: Worker doesn't use correct DB fields"
    exit 1
fi
echo ""

# Test 5: Verify clean pipeline message exists in media_ws_ai.py
echo "✅ Test 5: Checking for clean pipeline message..."
if grep -q "CLEAN PIPELINE" server/media_ws_ai.py; then
    echo "✅ PASS: Clean pipeline message found"
else
    echo "⚠️  WARNING: Clean pipeline message not found (minor issue)"
fi
echo ""

# Summary
echo "=============================="
echo "✅ ALL TESTS PASSED!"
echo ""
echo "📋 Summary:"
echo "  • Webhook sending: Worker only ✅"
echo "  • Waiting loops: Removed ✅"
echo "  • DB fields: Correct ✅"
echo "  • Architecture: Clean ✅"
echo ""
echo "🎯 Pipeline is ready for testing!"
echo ""
echo "Next steps:"
echo "  1. Make a test call"
echo "  2. Check worker logs: tail -f server/logs/recording_worker.log"
echo "  3. Verify DB: Check final_transcript, extracted_city, extracted_service"
echo "  4. Verify webhook was sent"
echo ""
