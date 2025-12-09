#!/bin/bash
# ✅ OFFLINE RECORDING TRANSCRIPTION FIX - VERIFICATION SCRIPT

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🔍 VERIFYING OFFLINE RECORDING TRANSCRIPTION FIX"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Function to check if a pattern exists in a file
check_pattern() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        ((PASS_COUNT++))
    else
        echo -e "${RED}❌ FAIL${NC} - $description"
        echo -e "   ${YELLOW}Pattern not found:${NC} $pattern"
        ((FAIL_COUNT++))
    fi
}

# Function to check if a pattern does NOT exist in a file
check_pattern_not_exists() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if ! grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✅ PASS${NC} - $description"
        ((PASS_COUNT++))
    else
        echo -e "${RED}❌ FAIL${NC} - $description"
        echo -e "   ${YELLOW}Pattern should not exist:${NC} $pattern"
        ((FAIL_COUNT++))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 1. Code Structure Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if files exist
if [ -f "server/tasks_recording.py" ]; then
    echo -e "${GREEN}✅ PASS${NC} - server/tasks_recording.py exists"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC} - server/tasks_recording.py not found"
    ((FAIL_COUNT++))
fi

if [ -f "server/media_ws_ai.py" ]; then
    echo -e "${GREEN}✅ PASS${NC} - server/media_ws_ai.py exists"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC} - server/media_ws_ai.py not found"
    ((FAIL_COUNT++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 2. URL Normalization Logic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pattern "server/tasks_recording.py" 'if download_url.startswith("/")' \
    "Relative URL handling - checks for leading /"

check_pattern "server/tasks_recording.py" 'https://api.twilio.com' \
    "Base URL prepending - adds api.twilio.com"

check_pattern "server/tasks_recording.py" 'if download_url.endswith(".json")' \
    "JSON to MP3 conversion - handles .json extension"

check_pattern "server/tasks_recording.py" 'original={original_url}, final={download_url}' \
    "Enhanced logging - logs both original and final URL"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 3. Error Handling & Safety Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pattern "server/tasks_recording.py" 'if resp.status_code != 200:' \
    "HTTP status check - validates 200 OK response"

check_pattern "server/tasks_recording.py" 'if not data:' \
    "Empty data check - handles empty responses"

check_pattern "server/tasks_recording.py" 'if not audio_file:' \
    "Audio file validation - checks download success"

check_pattern "server/tasks_recording.py" 'from typing import Optional' \
    "Type hints - Optional import for better type safety"

check_pattern "server/tasks_recording.py" 'def download_recording(recording_url: str, call_sid: str) -> Optional\[str\]' \
    "Function signature - proper type annotations"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 4. Webhook Transcript Selection Logic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_pattern "server/media_ws_ai.py" 'OFFLINE TRANSCRIPT = PRIMARY SOURCE' \
    "Offline transcript priority - no thresholds"

check_pattern "server/media_ws_ai.py" 'if call_log and call_log.final_transcript:' \
    "Offline transcript check - simple existence check (no length threshold)"

check_pattern "server/media_ws_ai.py" 'Using OFFLINE transcript' \
    "Success logging - logs when using offline transcript"

check_pattern "server/media_ws_ai.py" 'Offline transcript missing.*using realtime' \
    "Fallback logging - logs when falling back to realtime"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 5. Running Unit Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 test_url_normalization.py; then
    echo -e "${GREEN}✅ PASS${NC} - URL normalization tests passed"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC} - URL normalization tests failed"
    ((FAIL_COUNT++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 6. Python Syntax Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 -m py_compile server/tasks_recording.py 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC} - tasks_recording.py has valid Python syntax"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC} - tasks_recording.py has syntax errors"
    ((FAIL_COUNT++))
fi

if python3 -c "import ast; ast.parse(open('server/media_ws_ai.py').read())" 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC} - media_ws_ai.py has valid Python syntax"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC} - media_ws_ai.py has syntax errors"
    ((FAIL_COUNT++))
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "📊 VERIFICATION SUMMARY"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo -e "Tests Passed: ${GREEN}${PASS_COUNT}${NC}"
echo -e "Tests Failed: ${RED}${FAIL_COUNT}${NC}"
echo -e "Total Tests:  $((PASS_COUNT + FAIL_COUNT))"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED!${NC}"
    echo ""
    echo "The offline recording transcription fix has been successfully implemented."
    echo ""
    echo "Next steps:"
    echo "  1. Deploy the changes to production"
    echo "  2. Monitor logs for successful recording downloads:"
    echo "     - Look for: '[OFFLINE_STT] Download status: 200'"
    echo "     - Look for: '✅ [WEBHOOK] Using offline final_transcript'"
    echo "  3. Verify no more 404 errors in logs"
    echo "  4. Check database for populated final_transcript fields"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME CHECKS FAILED!${NC}"
    echo ""
    echo "Please review the failed checks above and fix any issues."
    echo ""
    exit 1
fi
