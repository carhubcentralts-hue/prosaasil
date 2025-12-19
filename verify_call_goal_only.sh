#!/bin/bash
# בדיקת תלות רק ב-call_goal (ללא enable_calendar_scheduling)

echo "🔍 בדיקה: הכלים תלויים רק ב-call_goal"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

# Test 1: Realtime - בודק רק call_goal
echo "Test 1: Realtime API - בדיקה רק של call_goal..."
if grep -q "if call_goal == 'appointment':" server/media_ws_ai.py && \
   ! grep "enable_calendar_scheduling" server/media_ws_ai.py | grep -q "if call_goal.*and.*enable"; then
    echo -e "${GREEN}✅${NC} Realtime: בודק רק call_goal (לא enable_calendar_scheduling)"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Realtime: עדיין בודק enable_calendar_scheduling"
    ((FAIL++))
fi

# Test 2: AgentKit - בדיקת בניית כלים
echo "Test 2: AgentKit - בניית כלים תלויה רק ב-call_goal..."
if grep -q "calendar_tools_enabled = (call_goal == 'appointment')" server/agent_tools/agent_factory.py; then
    echo -e "${GREEN}✅${NC} AgentKit: כלים נבנים רק לפי call_goal"
    ((PASS++))
else
    echo -e "${RED}❌${NC} AgentKit: בעיה בבדיקת call_goal"
    ((FAIL++))
fi

# Test 3: וידוא שלא נשארו בדיקות של enable_calendar_scheduling
echo "Test 3: בדיקה שלא נשארו בדיקות ישנות..."
OLD_CHECKS=$(grep -r "enable_calendar_scheduling" server/media_ws_ai.py server/agent_tools/agent_factory.py 2>/dev/null | grep -v "^Binary" | grep -v "getattr" | grep -c "if.*enable_calendar")
if [ "$OLD_CHECKS" -eq "0" ]; then
    echo -e "${GREEN}✅${NC} אין בדיקות ישנות של enable_calendar_scheduling בתנאי if"
    ((PASS++))
else
    echo -e "${YELLOW}⚠️${NC}  נמצאו $OLD_CHECKS בדיקות ישנות (ייתכן ובסדר)"
    grep -r "enable_calendar_scheduling" server/media_ws_ai.py server/agent_tools/agent_factory.py 2>/dev/null | grep -v "^Binary" | grep "if.*enable_calendar" | head -3
fi

# Test 4: וידוא שהכלים קוראים ל-policy
echo "Test 4: וידוא שהimplementation משתמשת ב-business_policy..."
if grep -q "get_business_policy" server/agent_tools/tools_calendar.py; then
    echo -e "${GREEN}✅${NC} tools_calendar משתמש ב-business_policy"
    ((PASS++))
else
    echo -e "${RED}❌${NC} tools_calendar לא משתמש ב-business_policy"
    ((FAIL++))
fi

# Test 5: וידוא שה-policy מכיל opening_hours ו-slot_size_min
echo "Test 5: בדיקה ש-policy מכיל opening_hours ו-slot_size_min..."
if grep -q "policy.opening_hours" server/agent_tools/tools_calendar.py && \
   grep -q "policy.slot_size_min" server/agent_tools/tools_calendar.py; then
    echo -e "${GREEN}✅${NC} Implementation משתמש ב-opening_hours ו-slot_size_min מה-policy"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Implementation לא משתמש ב-policy כראוי"
    ((FAIL++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "תוצאות: ${GREEN}${PASS} עברו${NC}, ${RED}${FAIL} נכשלו${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 כל הבדיקות עברו! הכלים תלויים רק ב-call_goal${NC}"
    exit 0
else
    echo -e "${RED}⚠️  יש בדיקות שנכשלו. בדוק את ההטמעה.${NC}"
    exit 1
fi
