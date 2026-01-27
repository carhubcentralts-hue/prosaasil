#!/bin/bash
# Manual verification script for HEAD request fix
# This script helps verify that the fix works correctly

echo "=========================================="
echo "HEAD Request Fix Verification"
echo "=========================================="
echo ""

# Check if the route now supports HEAD method
echo "1. Checking if HEAD method is added to the route..."
if grep -q "methods=\['GET', 'HEAD', 'OPTIONS'\]" server/routes_recordings.py; then
    echo "   ✅ HEAD method found in route definition"
else
    echo "   ❌ HEAD method NOT found in route definition"
    exit 1
fi

# Check if HEAD request handling is implemented
echo ""
echo "2. Checking if HEAD request handling is implemented..."
if grep -q "is_head_request = request.method == 'HEAD'" server/routes_recordings.py; then
    echo "   ✅ HEAD request detection implemented"
else
    echo "   ❌ HEAD request detection NOT implemented"
    exit 1
fi

# Check if HEAD requests return proper responses without body
echo ""
echo "3. Checking if HEAD requests return empty responses..."
if grep -q "if is_head_request:" server/routes_recordings.py; then
    echo "   ✅ HEAD request handling found"
    
    # Count occurrences to ensure all error paths are handled
    count=$(grep -c "if is_head_request:" server/routes_recordings.py)
    if [ "$count" -ge 3 ]; then
        echo "   ✅ HEAD handling in multiple paths (found $count occurrences)"
    else
        echo "   ⚠️  HEAD handling might be missing in some paths (found $count occurrences)"
    fi
else
    echo "   ❌ HEAD request handling NOT found"
    exit 1
fi

# Check if the docstring is updated
echo ""
echo "4. Checking if documentation is updated..."
if grep -E "(HEAD|headers only)" server/routes_recordings.py | grep -qE "(Returns|docstring|🔥)"; then
    echo "   ✅ Documentation mentions HEAD requests"
else
    echo "   ⚠️  Documentation might need updates (non-critical)"
fi

# Check Python syntax
echo ""
echo "5. Checking Python syntax..."
if python3 -m py_compile server/routes_recordings.py 2>/dev/null; then
    echo "   ✅ Python syntax is valid"
else
    echo "   ❌ Python syntax error detected"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ All checks passed!"
echo "=========================================="
echo ""
echo "The fix is ready. To test manually:"
echo ""
echo "1. Start the server"
echo "2. Use curl to test HEAD request:"
echo "   curl -I -X HEAD 'http://localhost:5000/api/recordings/file/CA...' \\"
echo "        -H 'Cookie: session=...'"
echo ""
echo "Expected behavior:"
echo "- If file exists: HTTP 200 with headers but no body"
echo "- If file not found: HTTP 404 with no body"
echo ""
echo "Before the fix:"
echo "- HEAD requests returned 404 (method not allowed)"
echo ""
echo "After the fix:"
echo "- HEAD requests return proper status codes"
echo ""
