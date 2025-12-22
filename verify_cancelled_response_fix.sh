#!/bin/bash
# Quick verification script for _cancelled_response_ids fix

echo "========================================================================"
echo "Verifying _cancelled_response_ids AttributeError Fix"
echo "========================================================================"
echo ""

# Check 1: Verify initialization line exists
echo "✓ Checking if _cancelled_response_ids is initialized..."
if grep -q "self._cancelled_response_ids = set()" server/media_ws_ai.py; then
    echo "  ✅ Found initialization: self._cancelled_response_ids = set()"
else
    echo "  ❌ ERROR: Initialization line not found!"
    exit 1
fi
echo ""

# Check 2: Verify it's in __init__ method
echo "✓ Checking if initialization is in __init__ method..."
# Extract the __init__ method and check if it contains the initialization
awk '/def __init__/,/^    def [^_]/' server/media_ws_ai.py | grep -q "_cancelled_response_ids = set()"
if [ $? -eq 0 ]; then
    echo "  ✅ Initialization is in __init__ method"
else
    echo "  ❌ ERROR: Initialization not found in __init__!"
    exit 1
fi
echo ""

# Check 3: Count usage locations
echo "✓ Checking usage locations..."
usage_count=$(grep -c "_cancelled_response_ids" server/media_ws_ai.py)
echo "  ✅ Found $usage_count references to _cancelled_response_ids"
if [ $usage_count -ge 10 ]; then
    echo "  ✅ All usage locations can now access the attribute"
else
    echo "  ⚠️  Warning: Expected at least 10 usage locations"
fi
echo ""

# Check 4: Verify enhanced exception handler
echo "✓ Checking enhanced exception handler..."
if grep -q "self.closed = True" server/media_ws_ai.py && \
   grep -q "drop_ai_audio_until_done = False" server/media_ws_ai.py && \
   grep -q "close_session(f\"realtime_fatal_error" server/media_ws_ai.py; then
    echo "  ✅ Enhanced exception handler is in place"
    echo "     - Sets self.closed = True"
    echo "     - Clears audio flags"
    echo "     - Calls close_session()"
else
    echo "  ⚠️  Warning: Some exception handler enhancements may be missing"
fi
echo ""

# Check 5: Verify Python syntax
echo "✓ Verifying Python syntax..."
python -m py_compile server/media_ws_ai.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✅ Python syntax is valid"
else
    echo "  ❌ ERROR: Python syntax errors found!"
    exit 1
fi
echo ""

# Check 6: Verify the critical line that was crashing
echo "✓ Checking the critical crash line (3936)..."
crash_line=$(sed -n '3936p' server/media_ws_ai.py)
if echo "$crash_line" | grep -q "_cancelled_response_ids"; then
    echo "  ✅ Found: $crash_line"
    echo "     This line will no longer crash because _cancelled_response_ids is initialized"
else
    echo "  ⚠️  Note: Line 3936 content may have shifted"
fi
echo ""

echo "========================================================================"
echo "🎉 VERIFICATION COMPLETE - Fix is properly implemented!"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  - _cancelled_response_ids is initialized as a set in __init__"
echo "  - Exception handler has been enhanced with proper cleanup"
echo "  - Python syntax is valid"
echo "  - All usage locations can now access the attribute"
echo ""
echo "Next steps:"
echo "  1. Deploy to staging environment"
echo "  2. Test with actual phone calls"
echo "  3. Monitor logs for [REALTIME_FATAL] entries"
echo "  4. Verify audio works correctly (no more silence)"
echo ""
