#!/bin/bash
# Appointment Booking Verification Script
# Checks that all critical components are in place

echo "🔍 Verifying Appointment Booking Implementation..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter
PASS=0
FAIL=0

# Test 1: Check prompt builder has appointment instructions
echo "Test 1: Checking appointment instructions in prompt builder..."
if grep -q "Goal = Book Appointment" server/services/realtime_prompt_builder.py; then
    echo -e "${GREEN}✅ PASS${NC}: Appointment instructions found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: Appointment instructions missing"
    ((FAIL++))
fi

# Test 2: Check tools registration (check_availability)
echo "Test 2: Checking check_availability tool registration..."
if grep -q '"name": "check_availability"' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: check_availability tool registered"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: check_availability tool NOT registered"
    ((FAIL++))
fi

# Test 3: Check tools registration (schedule_appointment)
echo "Test 3: Checking schedule_appointment tool registration..."
if grep -q '"name": "schedule_appointment"' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: schedule_appointment tool registered"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: schedule_appointment tool NOT registered"
    ((FAIL++))
fi

# Test 4: Check check_availability handler
echo "Test 4: Checking check_availability handler implementation..."
if grep -q 'elif function_name == "check_availability":' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: check_availability handler found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: check_availability handler missing"
    ((FAIL++))
fi

# Test 5: Check CAL_AVAIL_OK logging
echo "Test 5: Checking CAL_AVAIL_OK logging..."
if grep -q 'CAL_AVAIL_OK' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: CAL_AVAIL_OK logging found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: CAL_AVAIL_OK logging missing"
    ((FAIL++))
fi

# Test 6: Check CAL_CREATE_OK logging
echo "Test 6: Checking CAL_CREATE_OK logging..."
if grep -q 'CAL_CREATE_OK' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: CAL_CREATE_OK logging found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: CAL_CREATE_OK logging missing"
    ((FAIL++))
fi

# Test 7: Check CAL_ACCESS_DENIED fallback
echo "Test 7: Checking CAL_ACCESS_DENIED fallback..."
if grep -q 'CAL_ACCESS_DENIED' server/media_ws_ai.py; then
    echo -e "${GREEN}✅ PASS${NC}: CAL_ACCESS_DENIED fallback found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: CAL_ACCESS_DENIED fallback missing"
    ((FAIL++))
fi

# Test 8: Check anti-hallucination rules
echo "Test 8: Checking anti-hallucination enforcement..."
if grep -q 'ANTI-HALLUCINATION' server/services/realtime_prompt_builder.py; then
    echo -e "${GREEN}✅ PASS${NC}: Anti-hallucination rules found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: Anti-hallucination rules missing"
    ((FAIL++))
fi

# Test 9: Check calendar implementation exists
echo "Test 9: Checking calendar implementation..."
if [ -f "server/agent_tools/tools_calendar.py" ]; then
    if grep -q '_calendar_create_appointment_impl' server/agent_tools/tools_calendar.py; then
        echo -e "${GREEN}✅ PASS${NC}: Calendar implementation found"
        ((PASS++))
    else
        echo -e "${RED}❌ FAIL${NC}: Calendar implementation incomplete"
        ((FAIL++))
    fi
else
    echo -e "${RED}❌ FAIL${NC}: Calendar tools file missing"
    ((FAIL++))
fi

# Test 10: Check database model
echo "Test 10: Checking Appointment model..."
if grep -q 'class Appointment' server/models_sql.py; then
    echo -e "${GREEN}✅ PASS${NC}: Appointment model found"
    ((PASS++))
else
    echo -e "${RED}❌ FAIL${NC}: Appointment model missing"
    ((FAIL++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! Implementation is complete.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Please review the implementation.${NC}"
    exit 1
fi
