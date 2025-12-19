#!/bin/bash
# בדיקת תיאום פגישות בשני הערוצים

echo "🔍 בדיקת תיאום פגישות - שני ערוצים"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

echo -e "${BLUE}📞 בדיקת ערוץ שיחות קוליות (Realtime API)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 1: Realtime tools registration
if grep -q '"name": "check_availability"' server/media_ws_ai.py && \
   grep -q '"name": "schedule_appointment"' server/media_ws_ai.py; then
    echo -e "${GREEN}✅${NC} כלי check_availability ו-schedule_appointment רשומים"
    ((PASS++))
else
    echo -e "${RED}❌${NC} כלים חסרים ב-Realtime API"
    ((FAIL++))
fi

# Test 2: Realtime handlers
if grep -q 'elif function_name == "check_availability":' server/media_ws_ai.py && \
   grep -q 'elif function_name == "schedule_appointment":' server/media_ws_ai.py; then
    echo -e "${GREEN}✅${NC} Handlers רשומים ב-_handle_function_call"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Handlers חסרים"
    ((FAIL++))
fi

# Test 3: Realtime calls implementation
if grep -q '_calendar_find_slots_impl' server/media_ws_ai.py && \
   grep -q '_calendar_create_appointment_impl' server/media_ws_ai.py; then
    echo -e "${GREEN}✅${NC} קריאות ישירות ל-implementation functions"
    ((PASS++))
else
    echo -e "${RED}❌${NC} חסרות קריאות ל-implementation"
    ((FAIL++))
fi

# Test 4: Realtime logging
if grep -q 'CAL_AVAIL_OK' server/media_ws_ai.py && \
   grep -q 'CAL_CREATE_OK' server/media_ws_ai.py; then
    echo -e "${GREEN}✅${NC} לוגים: CAL_AVAIL_OK, CAL_CREATE_OK"
    ((PASS++))
else
    echo -e "${RED}❌${NC} לוגים חסרים"
    ((FAIL++))
fi

echo ""
echo -e "${BLUE}📱 בדיקת ערוץ WhatsApp (AgentKit)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 5: AgentKit imports
if grep -q 'from server.agent_tools.tools_calendar import calendar_find_slots, calendar_create_appointment' server/agent_tools/agent_factory.py; then
    echo -e "${GREEN}✅${NC} calendar_find_slots ו-calendar_create_appointment מיובאים"
    ((PASS++))
else
    echo -e "${RED}❌${NC} imports חסרים ב-agent_factory"
    ((FAIL++))
fi

# Test 6: AgentKit tools registration
if grep -q 'calendar_find_slots,' server/agent_tools/agent_factory.py && \
   grep -q 'calendar_create_appointment,' server/agent_tools/agent_factory.py; then
    echo -e "${GREEN}✅${NC} כלים נוספים לרשימת כלי AgentKit"
    ((PASS++))
else
    echo -e "${RED}❌${NC} כלים לא נוספו לרשימה"
    ((FAIL++))
fi

# Test 7: AgentKit wrappers
if grep -q '@function_tool' server/agent_tools/tools_calendar.py && \
   grep -q 'def calendar_find_slots' server/agent_tools/tools_calendar.py && \
   grep -q 'def calendar_create_appointment' server/agent_tools/tools_calendar.py; then
    echo -e "${GREEN}✅${NC} FunctionTool decorators עם wrappers"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Wrappers חסרים"
    ((FAIL++))
fi

echo ""
echo -e "${BLUE}🔄 בדיקת Implementation משותפת${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 8: Shared implementation
if grep -q 'def _calendar_find_slots_impl' server/agent_tools/tools_calendar.py && \
   grep -q 'def _calendar_create_appointment_impl' server/agent_tools/tools_calendar.py; then
    echo -e "${GREEN}✅${NC} _calendar_find_slots_impl ו-_calendar_create_appointment_impl קיימים"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Implementation functions חסרים"
    ((FAIL++))
fi

# Test 9: Database operations
if grep -q 'Appointment.query' server/agent_tools/tools_calendar.py && \
   grep -q 'db.session.add' server/agent_tools/tools_calendar.py && \
   grep -q 'db.session.commit' server/agent_tools/tools_calendar.py; then
    echo -e "${GREEN}✅${NC} פעולות database: query, add, commit"
    ((PASS++))
else
    echo -e "${RED}❌${NC} פעולות database חסרות"
    ((FAIL++))
fi

# Test 10: WhatsApp channel detection
if grep -q 'channel == "whatsapp"' server/services/ai_service.py && \
   grep -q 'WhatsApp message - skipping FAQ, using AgentKit' server/services/ai_service.py; then
    echo -e "${GREEN}✅${NC} WhatsApp routing ל-AgentKit"
    ((PASS++))
else
    echo -e "${RED}❌${NC} WhatsApp routing חסר"
    ((FAIL++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "תוצאות: ${GREEN}${PASS} עברו${NC}, ${RED}${FAIL} נכשלו${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 כל הבדיקות עברו! שני הערוצים תקינים.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  יש בדיקות שנכשלו. בדוק את ההטמעה.${NC}"
    exit 1
fi
