#!/bin/bash
# Check for logger.* calls with flush=True or file= parameters
# These parameters are not supported by Python's logging module
# 
# NOTE: This script only checks logger.* calls (not print statements)
# print() with flush=True is valid and will not be flagged

set -euo pipefail

echo "🔍 Checking for invalid logger parameters (logger.* calls only)..."

# Search for logger.* with flush=True in Python files
# Using more specific pattern to avoid false positives
FOUND_FLUSH=$(grep -rn 'logger\.\(debug\|info\|warning\|error\|critical\).*flush=True' . --include="*.py" || true)

# Search for logger.* with file= in Python files  
FOUND_FILE=$(grep -rn 'logger\.\(debug\|info\|warning\|error\|critical\).*file=' . --include="*.py" || true)

ERRORS=0

if [ -n "$FOUND_FLUSH" ]; then
    echo "❌ ERROR: Found logger calls with flush=True parameter!"
    echo ""
    echo "Python's logging module does not support the 'flush' parameter."
    echo "Please remove 'flush=True' from the following logger calls:"
    echo ""
    echo "$FOUND_FLUSH"
    echo ""
    ERRORS=1
fi

if [ -n "$FOUND_FILE" ]; then
    echo "❌ ERROR: Found logger calls with file= parameter!"
    echo ""
    echo "Python's logging module does not support the 'file' parameter."
    echo "Please remove 'file=' from the following logger calls:"
    echo ""
    echo "$FOUND_FILE"
    echo ""
    ERRORS=1
fi

if [ $ERRORS -eq 1 ]; then
    exit 1
fi

echo "✅ No invalid logger parameters found. Good!"
exit 0
