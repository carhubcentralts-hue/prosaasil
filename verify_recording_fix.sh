#!/bin/bash

echo "🔍 בדיקת תיקון הורדת הקלטות מ-Twilio"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if string exists in file
check_pattern() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} $description"
        return 0
    else
        echo -e "${RED}❌${NC} $description"
        return 1
    fi
}

echo "1️⃣  בדיקת server/tasks_recording.py"
echo "-----------------------------------"
check_pattern "server/tasks_recording.py" "candidates = \[" "יצירת רשימת קנדידטים (candidates)"
check_pattern "server/tasks_recording.py" "for url in candidates:" "לולאה על קנדידטים"
check_pattern "server/tasks_recording.py" "if resp.status_code == 200 and resp.content:" "בדיקת הצלחה 200"
check_pattern "server/tasks_recording.py" "if resp.status_code == 404:" "טיפול ב-404"
check_pattern "server/tasks_recording.py" 'base_url\[:-5\]' "הסרת .json"
echo ""

echo "2️⃣  בדיקת server/routes_twilio.py"
echo "-----------------------------------"
check_pattern "server/routes_twilio.py" "recording.uri" "שימוש ב-recording.uri המקורי"
check_pattern "server/routes_twilio.py" "'RecordingUrl': recording.uri" "העברת URI כמו שהוא"
echo ""

echo "3️⃣  בדיקת server/routes_calls.py"
echo "-----------------------------------"
check_pattern "server/routes_calls.py" 'if base_url.endswith(".json"):' "בדיקת .json"
check_pattern "server/routes_calls.py" 'base_url = base_url\[:-5\]' "הסרת .json"
check_pattern "server/routes_calls.py" '\.mp3' "קנדידט .mp3"
check_pattern "server/routes_calls.py" '\.wav' "קנדידט .wav"
echo ""

echo "4️⃣  בדיקת עדיפות Offline Transcript"
echo "-----------------------------------"
check_pattern "server/media_ws_ai.py" "call_log.final_transcript" "שימוש ב-final_transcript"
check_pattern "server/media_ws_ai.py" "Using OFFLINE transcript" "הודעת offline"
check_pattern "server/media_ws_ai.py" "using realtime" "fallback לrealtime"
echo ""

echo "5️⃣  בדיקת Python Syntax"
echo "-----------------------------------"
if python3 -m py_compile server/tasks_recording.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} tasks_recording.py - syntax תקין"
else
    echo -e "${RED}❌${NC} tasks_recording.py - שגיאת syntax"
fi

if python3 -m py_compile server/routes_twilio.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} routes_twilio.py - syntax תקין"
else
    echo -e "${RED}❌${NC} routes_twilio.py - שגיאת syntax"
fi

if python3 -m py_compile server/routes_calls.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} routes_calls.py - syntax תקין"
else
    echo -e "${RED}❌${NC} routes_calls.py - שגיאת syntax"
fi
echo ""

echo "6️⃣  בדיקת קבצי תיעוד"
echo "-----------------------------------"
if [ -f "RECORDING_DOWNLOAD_FIX.md" ]; then
    echo -e "${GREEN}✅${NC} RECORDING_DOWNLOAD_FIX.md קיים"
else
    echo -e "${RED}❌${NC} RECORDING_DOWNLOAD_FIX.md חסר"
fi

if [ -f "תיקון_הורדת_הקלטות.md" ]; then
    echo -e "${GREEN}✅${NC} תיקון_הורדת_הקלטות.md קיים"
else
    echo -e "${RED}❌${NC} תיקון_הורדת_הקלטות.md חסר"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}✅ בדיקת תיקון הושלמה!${NC}"
echo ""
echo "📋 מה עכשיו?"
echo "  1. הפעל את השרת: ./start_all.sh"
echo "  2. עשה שיחת טסט"
echo "  3. בדוק בלוגים: docker logs -f prosaas-backend | grep OFFLINE_STT"
echo "  4. ודא שרואה: ✅ Download OK + ✅ Transcript obtained"
echo ""
