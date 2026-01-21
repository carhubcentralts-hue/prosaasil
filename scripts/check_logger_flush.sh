#!/bin/bash
# Check for logger.* calls with flush=True or file= parameters
# These parameters are not supported by Python's logging module

set -euo pipefail

echo "🔍 Checking for invalid logger parameters..."

# Search for logger.* with flush=True in Python files
FOUND_FLUSH=$(grep -rn "logger\." . --include="*.py" | grep "flush=True" || true)

# Search for logger.* with file= in Python files  
FOUND_FILE=$(grep -rn "logger\." . --include="*.py" | grep "file=" || true)

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
