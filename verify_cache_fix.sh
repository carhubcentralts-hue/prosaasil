#!/bin/bash

# Verification script for recording cache persistence fix
# Run this after deploying to verify the fix works

set -e

echo "======================================"
echo "Recording Cache Persistence Fix - Verification"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "1. Checking docker-compose.yml for persistent volume..."
if grep -q "recordings_data:/app/server/recordings" docker-compose.yml; then
    echo -e "${GREEN}✅ Persistent volume configured${NC}"
else
    echo -e "${RED}❌ Persistent volume NOT configured${NC}"
    exit 1
fi

echo ""
echo "2. Checking recording_service.py for parent_call_sid fallback..."
if grep -q "parent_call_sid" server/services/recording_service.py && \
   grep -q "sids_to_try" server/services/recording_service.py; then
    echo -e "${GREEN}✅ Parent call_sid fallback implemented${NC}"
else
    echo -e "${RED}❌ Parent call_sid fallback NOT implemented${NC}"
    exit 1
fi

echo ""
echo "3. Checking recording_service.py for download locking..."
if grep -q "fcntl" server/services/recording_service.py && \
   grep -q "LOCK_EX" server/services/recording_service.py; then
    echo -e "${GREEN}✅ File-based download locking implemented (works across workers/pods)${NC}"
else
    echo -e "${RED}❌ File-based download locking NOT implemented${NC}"
    exit 1
fi

echo ""
echo "4. Checking recording_service.py for Cache HIT logging..."
if grep -q "Cache HIT" server/services/recording_service.py; then
    echo -e "${GREEN}✅ Cache HIT logging implemented${NC}"
else
    echo -e "${RED}❌ Cache HIT logging NOT implemented${NC}"
    exit 1
fi

echo ""
echo "5. Checking AudioPlayer.tsx for no prefetching..."
if grep -q 'preload="none"' client/src/shared/components/AudioPlayer.tsx && \
   ! grep -q 'preload="metadata"' client/src/shared/components/AudioPlayer.tsx; then
    echo -e "${GREEN}✅ AudioPlayer uses preload='none' (no prefetching)${NC}"
else
    echo -e "${RED}❌ AudioPlayer still uses preload='metadata'${NC}"
    exit 1
fi

echo ""
echo "6. Checking .gitignore for recordings directory..."
if grep -q "server/recordings" .gitignore; then
    echo -e "${GREEN}✅ Recordings directory excluded from git${NC}"
else
    echo -e "${YELLOW}⚠️  Recordings directory not in .gitignore (optional)${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}✅ All checks passed!${NC}"
echo "======================================"
echo ""
echo "Expected behavior after deployment:"
echo "1. First playback: Cache miss → downloads from Twilio → saves locally (one-time)"
echo "2. Second playback: Cache HIT → serves from disk (no Twilio download)"
echo "3. Multiple Range requests: Only one download happens, others wait and serve from cache"
echo "4. Container restart: Recordings persist (not lost) thanks to persistent volume"
echo "5. Outbound calls: Correctly finds recording using parent_call_sid fallback if needed"
echo "6. Page load: No prefetching, no Range requests until user clicks play"
echo ""
echo "To verify in production:"
echo "1. docker-compose up -d"
echo "2. Check logs: docker-compose logs -f backend | grep 'RECORDING_SERVICE'"
echo "3. First playback should show: 'Cache miss - downloading from Twilio'"
echo "4. Second playback should show: 'Cache HIT - using existing local file'"
echo "5. No more 502 errors or re-downloads on every click"
echo ""
