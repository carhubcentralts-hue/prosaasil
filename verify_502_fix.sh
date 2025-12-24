#!/bin/bash
# =============================================================================
# Recording Download 502 Fix - Comprehensive Verification Script
# בדיקה מקיפה של 5 דברים קריטיים לתיקון 502
# =============================================================================

set -e

echo "=========================================="
echo "בדיקת תיקון 502 להורדת הקלטות"
echo "5 בדיקות קריטיות"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running inside Docker or on host
if [ -f /.dockerenv ]; then
    BACKEND_URL="http://backend:5000"
    NGINX_URL="http://localhost:80"
else
    BACKEND_URL="http://localhost:5000"
    NGINX_URL="http://localhost"
fi

# Function to check if services are running
check_services() {
    echo "🔍 בדיקה 1: האם השירותים רצים?"
    echo "----------------------------------------"
    
    if command -v docker &> /dev/null; then
        echo "בדיקת Docker containers..."
        if docker compose ps | grep -q "prosaas-backend.*Up"; then
            echo -e "${GREEN}✅ Backend רץ${NC}"
        else
            echo -e "${RED}❌ Backend לא רץ - הרץ: docker compose up -d backend${NC}"
            return 1
        fi
        
        if docker compose ps | grep -q "prosaas-frontend.*Up"; then
            echo -e "${GREEN}✅ Nginx רץ${NC}"
        else
            echo -e "${RED}❌ Nginx לא רץ - הרץ: docker compose up -d frontend${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  Docker לא זמין - דילוג על בדיקת containers${NC}"
    fi
    
    echo ""
}

# Check nginx configuration
check_nginx_config() {
    echo "🔍 בדיקה 2: תצורת Nginx (streaming, Range, timeouts)"
    echo "----------------------------------------"
    
    NGINX_CONF="docker/nginx.conf"
    
    if [ ! -f "$NGINX_CONF" ]; then
        echo -e "${RED}❌ nginx.conf לא נמצא ב-$NGINX_CONF${NC}"
        return 1
    fi
    
    # Required settings
    CHECKS=(
        "proxy_buffering off:Buffering מבוטל"
        "proxy_request_buffering off:Request buffering מבוטל"
        "proxy_read_timeout:Read timeout מוגדר"
        "proxy_send_timeout:Send timeout מוגדר"
        "Range \$http_range:Range header מועבר"
        "proxy_http_version 1.1:HTTP/1.1 מוגדר"
        'Connection "":Connection header מנוקה'
    )
    
    ALL_OK=true
    for check in "${CHECKS[@]}"; do
        IFS=":" read -r pattern desc <<< "$check"
        if grep -q "$pattern" "$NGINX_CONF"; then
            echo -e "${GREEN}✅ $desc${NC}"
        else
            echo -e "${RED}❌ חסר: $desc ($pattern)${NC}"
            ALL_OK=false
        fi
    done
    
    if [ "$ALL_OK" = true ]; then
        echo -e "${GREEN}✅ כל ההגדרות הנדרשות קיימות${NC}"
    else
        echo -e "${RED}❌ חסרות הגדרות ב-nginx.conf${NC}"
        return 1
    fi
    
    echo ""
}

# Check backend timeout configuration
check_backend_timeout() {
    echo "🔍 בדיקה 3: Timeout של Backend (Uvicorn/Gunicorn)"
    echo "----------------------------------------"
    
    DOCKERFILE="Dockerfile.backend"
    
    if [ ! -f "$DOCKERFILE" ]; then
        echo -e "${RED}❌ Dockerfile.backend לא נמצא${NC}"
        return 1
    fi
    
    # Check for uvicorn with good timeout settings
    if grep -q "uvicorn" "$DOCKERFILE"; then
        echo -e "${GREEN}✅ משתמש ב-Uvicorn${NC}"
        
        if grep -q "timeout-keep-alive" "$DOCKERFILE"; then
            # Extract timeout value - look for number after timeout-keep-alive
            TIMEOUT=$(grep "timeout-keep-alive" "$DOCKERFILE" | sed 's/.*timeout-keep-alive[",[:space:]]*\([0-9]\+\).*/\1/')
            if [ -n "$TIMEOUT" ] && [ "$TIMEOUT" -ge 75 ]; then
                echo -e "${GREEN}✅ timeout-keep-alive = $TIMEOUT שניות (מספיק)${NC}"
            elif [ -n "$TIMEOUT" ]; then
                echo -e "${YELLOW}⚠️  timeout-keep-alive = $TIMEOUT שניות (מומלץ 75+)${NC}"
            else
                echo -e "${YELLOW}⚠️  timeout-keep-alive לא ניתן לזיהוי${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  timeout-keep-alive לא מוגדר${NC}"
        fi
    elif grep -q "gunicorn" "$DOCKERFILE"; then
        echo -e "${GREEN}✅ משתמש ב-Gunicorn${NC}"
        
        if grep -q "\--timeout" "$DOCKERFILE"; then
            TIMEOUT=$(grep "\--timeout" "$DOCKERFILE" | grep -o '[0-9]\+' | head -1)
            if [ "$TIMEOUT" -ge 300 ]; then
                echo -e "${GREEN}✅ --timeout = $TIMEOUT שניות (מספיק)${NC}"
            else
                echo -e "${YELLOW}⚠️  --timeout = $TIMEOUT שניות (מומלץ 300+)${NC}"
            fi
        else
            echo -e "${RED}❌ --timeout לא מוגדר (ברירת מחדל 30 שניות - לא מספיק!)${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  לא מזהה Uvicorn או Gunicorn${NC}"
    fi
    
    echo ""
}

# Check that endpoint returns 206 Partial Content
check_206_support() {
    echo "🔍 בדיקה 4: תמיכה ב-206 Partial Content (קריטי ל-iOS)"
    echo "----------------------------------------"
    
    ROUTES_FILE="server/routes_calls.py"
    
    if [ ! -f "$ROUTES_FILE" ]; then
        echo -e "${RED}❌ routes_calls.py לא נמצא${NC}"
        return 1
    fi
    
    # Check for 206 response in code
    if grep -q "206" "$ROUTES_FILE" && grep -q "Content-Range" "$ROUTES_FILE"; then
        echo -e "${GREEN}✅ קוד מחזיר 206 Partial Content עם Content-Range${NC}"
    else
        echo -e "${RED}❌ חסר תמיכה ב-206 Partial Content${NC}"
        return 1
    fi
    
    # Check for Accept-Ranges header
    if grep -q "Accept-Ranges" "$ROUTES_FILE"; then
        echo -e "${GREEN}✅ מחזיר Accept-Ranges: bytes${NC}"
    else
        echo -e "${RED}❌ חסר Accept-Ranges header${NC}"
        return 1
    fi
    
    # Check for Range header handling
    if grep -q "Range" "$ROUTES_FILE" && grep -q "range_header" "$ROUTES_FILE"; then
        echo -e "${GREEN}✅ מטפל ב-Range header${NC}"
    else
        echo -e "${RED}❌ לא מטפל ב-Range header${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Endpoint תומך ב-Range requests (206)${NC}"
    echo ""
}

# Check that recordings are pre-downloaded (not fetched on-demand)
check_predownload_strategy() {
    echo "🔍 בדיקה 5: הורדה מראש של הקלטות (לא on-demand)"
    echo "----------------------------------------"
    
    RECORDING_SERVICE="server/services/recording_service.py"
    
    if [ ! -f "$RECORDING_SERVICE" ]; then
        echo -e "${RED}❌ recording_service.py לא נמצא${NC}"
        return 1
    fi
    
    # Check for local file caching
    if grep -q "os.path.exists(local_path)" "$RECORDING_SERVICE"; then
        echo -e "${GREEN}✅ בודק קבצים מקומיים לפני הורדה${NC}"
    else
        echo -e "${YELLOW}⚠️  לא בודק קבצים מקומיים${NC}"
    fi
    
    # Check for Twilio download fallback
    if grep -q "_download_from_twilio" "$RECORDING_SERVICE"; then
        echo -e "${YELLOW}⚠️  יורד מטוויליו במקרה שאין קובץ מקומי${NC}"
        echo -e "${YELLOW}   מומלץ: להוריד מראש ב-worker/webhook${NC}"
    else
        echo -e "${GREEN}✅ לא יורד מטוויליו on-demand${NC}"
    fi
    
    # Check for timeout handling in Twilio download
    if grep -q "timeout" "$RECORDING_SERVICE"; then
        echo -e "${GREEN}✅ יש timeout להורדה מטוויליו${NC}"
    else
        echo -e "${RED}❌ חסר timeout להורדה מטוויליו${NC}"
        return 1
    fi
    
    echo ""
}

# Live test with curl (if service is available)
live_test() {
    echo "🧪 בדיקה חיה (אופציונלי - דורש שירות רץ)"
    echo "----------------------------------------"
    
    # Skip if services are not running
    if ! curl -s -f "$NGINX_URL/health" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  שירותים לא רצים - דילוג על בדיקה חיה${NC}"
        echo "   להריץ: docker compose up -d"
        echo ""
        return 0
    fi
    
    echo "נסיון בדיקת endpoint..."
    
    # Try to get a real call_sid from database (if possible)
    # This is optional and requires database access
    
    # For now, just test that the endpoint exists
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$NGINX_URL/api/calls/TEST123/download" 2>/dev/null || echo "000")
    
    if [ "$RESPONSE" = "000" ]; then
        echo -e "${RED}❌ לא מצליח להתחבר ל-$NGINX_URL${NC}"
        return 1
    elif [ "$RESPONSE" = "502" ]; then
        echo -e "${RED}❌ מקבל 502 Bad Gateway!${NC}"
        echo "   צריך לבדוק:"
        echo "   1. docker compose logs nginx"
        echo "   2. docker compose logs backend"
        return 1
    elif [ "$RESPONSE" = "404" ] || [ "$RESPONSE" = "401" ]; then
        echo -e "${GREEN}✅ Endpoint עונה (קיבל $RESPONSE - נורמלי לקריאה ללא אימות/call_sid לא קיים)${NC}"
    else
        echo -e "${GREEN}✅ Endpoint עונה (status: $RESPONSE)${NC}"
    fi
    
    echo ""
}

# Main execution
main() {
    FAILED=0
    
    check_services || FAILED=$((FAILED + 1))
    check_nginx_config || FAILED=$((FAILED + 1))
    check_backend_timeout || FAILED=$((FAILED + 1))
    check_206_support || FAILED=$((FAILED + 1))
    check_predownload_strategy || FAILED=$((FAILED + 1))
    live_test || true  # Don't fail on live test
    
    echo "=========================================="
    echo "סיכום"
    echo "=========================================="
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✅ כל הבדיקות עברו בהצלחה!${NC}"
        echo ""
        echo "צעדים הבאים:"
        echo "1. docker compose build"
        echo "2. docker compose restart nginx backend"
        echo "3. בדוק playback בדפדפן"
        echo "4. אם יש 502, הרץ: docker compose logs -f nginx backend"
        return 0
    else
        echo -e "${RED}❌ $FAILED בדיקות נכשלו${NC}"
        echo ""
        echo "תקן את הבעיות ולאחר מכן הרץ שוב את הסקריפט"
        return 1
    fi
}

# Run main
main
