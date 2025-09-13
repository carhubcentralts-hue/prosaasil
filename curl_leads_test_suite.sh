#!/bin/bash

##############################################################################
# COMPREHENSIVE LEADS SYSTEM CURL TEST SUITE
# Tests authentication, CSRF, all CRUD operations, and error handling
##############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
BASE_URL="${BASE_URL:-http://localhost:5000}"
COOKIE_JAR="/tmp/curl_test_cookies.txt"
TEST_LOG="/tmp/curl_test_results.log"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@shai-realestate.co.il}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
    rm -f "$COOKIE_JAR" 2>/dev/null || true
    echo "Cleaned up test files"
}

# Set cleanup trap
trap cleanup EXIT

# Initialize test environment
init_test_env() {
    echo -e "${BLUE}🔧 Initializing test environment${NC}"
    rm -f "$COOKIE_JAR" "$TEST_LOG" 2>/dev/null || true
    
    echo "========================================" > "$TEST_LOG"
    echo "LEADS SYSTEM CURL TEST SUITE RESULTS" >> "$TEST_LOG"
    echo "$(date)" >> "$TEST_LOG"
    echo "Base URL: $BASE_URL" >> "$TEST_LOG"
    echo "========================================" >> "$TEST_LOG"
    echo "" >> "$TEST_LOG"
}

# Helper functions
log_test() {
    local test_name="$1"
    local status="$2" 
    local details="$3"
    
    echo -e "${BLUE}▶ $test_name${NC}" | tee -a "$TEST_LOG"
    if [[ "$status" == "PASS" ]]; then
        echo -e "${GREEN}✅ PASS: $details${NC}" | tee -a "$TEST_LOG"
    elif [[ "$status" == "FAIL" ]]; then
        echo -e "${RED}❌ FAIL: $details${NC}" | tee -a "$TEST_LOG"
    elif [[ "$status" == "INFO" ]]; then
        echo -e "${YELLOW}ℹ️ INFO: $details${NC}" | tee -a "$TEST_LOG"
    fi
    echo "" >> "$TEST_LOG"
}

# Check response status and content
check_response() {
    local expected_status="$1"
    local actual_status="$2"
    local response_body="$3"
    local test_name="$4"
    
    if [[ "$actual_status" == "$expected_status" ]]; then
        log_test "$test_name" "PASS" "HTTP $actual_status (expected $expected_status)"
        return 0
    else
        log_test "$test_name" "FAIL" "HTTP $actual_status (expected $expected_status). Response: $response_body"
        return 1
    fi
}

# Extract JSON field from response
extract_json_field() {
    local json="$1"
    local field="$2"
    echo "$json" | python3 -c "import json, sys; print(json.load(sys.stdin).get('$field', ''))" 2>/dev/null || echo ""
}

# Test 1: Health check
test_health_check() {
    echo -e "${BLUE}🔍 Testing health check${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$BASE_URL/healthz")
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    check_response "200" "$http_status" "$body" "Health Check"
}

# Test 2: Get CSRF token
get_csrf_token() {
    echo -e "${BLUE}🔒 Getting CSRF token${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -c "$COOKIE_JAR" \
        "$BASE_URL/api/auth/csrf")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "CSRF Token Request"; then
        CSRF_TOKEN=$(extract_json_field "$body" "csrfToken")
        if [[ -n "$CSRF_TOKEN" ]]; then
            log_test "CSRF Token Extraction" "PASS" "Token: ${CSRF_TOKEN:0:10}..."
            echo "CSRF_TOKEN=$CSRF_TOKEN" >> "$TEST_LOG"
        else
            log_test "CSRF Token Extraction" "FAIL" "No csrfToken in response: $body"
            return 1
        fi
    else
        return 1
    fi
}

# Test 3: Login
login_user() {
    echo -e "${BLUE}🔐 Logging in as admin${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -c "$COOKIE_JAR" \
        -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
        "$BASE_URL/api/auth/login")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "Admin Login"; then
        # Extract user info
        USER_ID=$(extract_json_field "$body" "user" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('id', ''))" 2>/dev/null || echo "")
        TENANT_ID=$(extract_json_field "$body" "tenant" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('id', ''))" 2>/dev/null || echo "")
        
        log_test "Login Success" "INFO" "User ID: $USER_ID, Tenant ID: $TENANT_ID"
        echo "USER_ID=$USER_ID" >> "$TEST_LOG"
        echo "TENANT_ID=$TENANT_ID" >> "$TEST_LOG"
    else
        return 1
    fi
}

# Test 4: List leads (empty state)
test_list_leads_empty() {
    echo -e "${BLUE}📋 Testing list leads (empty state)${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        "$BASE_URL/api/leads")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "List Leads (Empty)"; then
        total=$(extract_json_field "$body" "total")
        log_test "Empty Lead List" "INFO" "Total leads: $total"
    fi
}

# Test 5: Create new lead
create_test_lead() {
    echo -e "${BLUE}✨ Creating test lead${NC}"
    
    local lead_data='{
        "first_name": "Test",
        "last_name": "Lead",
        "phone_e164": "+972501234567",
        "email": "test.lead@example.com",
        "source": "test_automation",
        "status": "New",
        "tags": ["test", "automation"],
        "notes": "Created by curl test suite"
    }'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$lead_data" \
        "$BASE_URL/api/leads")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "201" "$http_status" "$body" "Create Lead"; then
        LEAD_ID=$(extract_json_field "$body" "id")
        if [[ -n "$LEAD_ID" ]]; then
            log_test "Lead Creation" "PASS" "Created lead ID: $LEAD_ID"
            echo "LEAD_ID=$LEAD_ID" >> "$TEST_LOG"
        else
            log_test "Lead Creation" "FAIL" "No lead ID in response: $body"
            return 1
        fi
    else
        return 1
    fi
}

# Test 6: Get lead details
test_get_lead_details() {
    echo -e "${BLUE}📖 Getting lead details${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "Get Lead Details" "FAIL" "No lead ID available (create lead first)"
        return 1
    fi
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        "$BASE_URL/api/leads/$LEAD_ID")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "Get Lead Details"; then
        full_name=$(extract_json_field "$body" "full_name")
        status=$(extract_json_field "$body" "status") 
        log_test "Lead Details" "INFO" "Name: $full_name, Status: $status"
    fi
}

# Test 7: Update lead
test_update_lead() {
    echo -e "${BLUE}✏️ Updating lead${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "Update Lead" "FAIL" "No lead ID available"
        return 1
    fi
    
    local update_data='{
        "notes": "Updated by curl test suite at $(date)"
    }'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X PATCH \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$update_data" \
        "$BASE_URL/api/leads/$LEAD_ID")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    check_response "200" "$http_status" "$body" "Update Lead"
}

# Test 8: Update lead status (check for method mismatch)
test_update_lead_status() {
    echo -e "${BLUE}🎯 Testing lead status update${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "Update Lead Status" "FAIL" "No lead ID available"
        return 1
    fi
    
    # Test POST method (as per routes_leads.py)
    local status_data='{"status": "Contacted"}'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$status_data" \
        "$BASE_URL/api/leads/$LEAD_ID/status")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "Update Lead Status (POST)"; then
        log_test "Status Update Method" "INFO" "POST method works correctly"
    else
        # Try PUT method to check for mismatch
        echo -e "${YELLOW}🔄 Trying PUT method for status update${NC}"
        
        response_put=$(curl -s -w "HTTPSTATUS:%{http_code}" \
            -X PUT \
            -H "Content-Type: application/json" \
            -H "X-CSRFToken: $CSRF_TOKEN" \
            -b "$COOKIE_JAR" \
            -d "$status_data" \
            "$BASE_URL/api/leads/$LEAD_ID/status")
        
        http_status_put=$(echo "$response_put" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
        body_put=$(echo "$response_put" | sed -E 's/HTTPSTATUS:[0-9]*$//')
        
        if check_response "200" "$http_status_put" "$body_put" "Update Lead Status (PUT)"; then
            log_test "Method Mismatch" "INFO" "PUT method also works"
        else
            log_test "Method Mismatch" "INFO" "POST: $http_status, PUT: $http_status_put"
        fi
    fi
}

# Test 9: Create reminder
test_create_reminder() {
    echo -e "${BLUE}⏰ Creating reminder${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "Create Reminder" "FAIL" "No lead ID available"
        return 1
    fi
    
    # Create reminder for 1 hour from now
    local due_date=$(date -d "+1 hour" -Iseconds)
    local reminder_data='{
        "due_at": "'$due_date'",
        "note": "Follow up call - created by test suite",
        "channel": "ui"
    }'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$reminder_data" \
        "$BASE_URL/api/leads/$LEAD_ID/reminders")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "201" "$http_status" "$body" "Create Reminder"; then
        REMINDER_ID=$(extract_json_field "$body" "id")
        log_test "Reminder Creation" "INFO" "Created reminder ID: $REMINDER_ID"
        echo "REMINDER_ID=$REMINDER_ID" >> "$TEST_LOG"
    fi
}

# Test 10: List leads with filters
test_list_leads_with_filters() {
    echo -e "${BLUE}🔍 Testing lead filters${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        "$BASE_URL/api/leads?status=New&source=test_automation&q=Test")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "200" "$http_status" "$body" "List Leads with Filters"; then
        total=$(extract_json_field "$body" "total")
        log_test "Lead Filtering" "INFO" "Filtered results: $total"
    fi
}

# Test 11: Test WhatsApp placeholder
test_whatsapp_placeholder() {
    echo -e "${BLUE}📱 Testing WhatsApp placeholder${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "WhatsApp Test" "FAIL" "No lead ID available"
        return 1
    fi
    
    local whatsapp_data='{"message": "Hello from test suite"}'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$whatsapp_data" \
        "$BASE_URL/api/leads/$LEAD_ID/message/whatsapp")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    # Expecting 501 (Not Implemented) for placeholder
    if check_response "501" "$http_status" "$body" "WhatsApp Placeholder"; then
        log_test "WhatsApp Integration" "INFO" "Placeholder working correctly (501)"
    fi
}

# Test 12: Error handling tests
test_error_handling() {
    echo -e "${BLUE}⚠️ Testing error handling${NC}"
    
    # Test unauthorized access (without cookies)
    echo "Testing unauthorized access..."
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        "$BASE_URL/api/leads")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "401" "$http_status" "$body" "Unauthorized Access"; then
        log_test "Auth Protection" "PASS" "Endpoints properly protected"
    fi
    
    # Test invalid lead ID
    echo "Testing invalid lead ID..."
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        "$BASE_URL/api/leads/99999")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if check_response "404" "$http_status" "$body" "Invalid Lead ID"; then
        log_test "Not Found Handling" "PASS" "Proper 404 for invalid lead"
    fi
    
    # Test invalid JSON
    echo "Testing invalid JSON..."
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "{invalid json}" \
        "$BASE_URL/api/leads")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_status" == "400" ]]; then
        log_test "Invalid JSON Handling" "PASS" "Proper 400 for invalid JSON"
    else
        log_test "Invalid JSON Handling" "INFO" "Got HTTP $http_status for invalid JSON"
    fi
}

# Test 13: CSRF validation 
test_csrf_validation() {
    echo -e "${BLUE}🛡️ Testing CSRF validation${NC}"
    
    # Try POST without CSRF token
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -b "$COOKIE_JAR" \
        -d '{"first_name": "No CSRF", "phone_e164": "+972501111111"}' \
        "$BASE_URL/api/leads")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    # Should get 400 or 403 for missing CSRF
    if [[ "$http_status" == "400" || "$http_status" == "403" ]]; then
        log_test "CSRF Protection" "PASS" "Blocked request without CSRF token ($http_status)"
    else
        log_test "CSRF Protection" "FAIL" "Expected 400/403, got $http_status. Response: $body"
    fi
}

# Test 14: Bulk operations
test_bulk_operations() {
    echo -e "${BLUE}🔄 Testing bulk operations${NC}"
    
    if [[ -z "${LEAD_ID:-}" ]]; then
        log_test "Bulk Operations" "FAIL" "No lead ID available"
        return 1
    fi
    
    local bulk_data='{
        "lead_ids": ['$LEAD_ID'],
        "updates": {
            "status": "Qualified",
            "tags": ["bulk_updated", "qualified"]
        }
    }'
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X PATCH \
        -H "Content-Type: application/json" \
        -H "X-CSRFToken: $CSRF_TOKEN" \
        -b "$COOKIE_JAR" \
        -d "$bulk_data" \
        "$BASE_URL/api/leads/bulk")
    
    http_status=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    check_response "200" "$http_status" "$body" "Bulk Update"
}

# Generate test summary
generate_summary() {
    echo -e "\n${BLUE}📊 Generating test summary${NC}"
    
    echo "" >> "$TEST_LOG"
    echo "========================================" >> "$TEST_LOG"
    echo "TEST SUMMARY" >> "$TEST_LOG"
    echo "========================================" >> "$TEST_LOG"
    
    local total_tests=$(grep -c "▶" "$TEST_LOG" || echo "0")
    local passed_tests=$(grep -c "✅ PASS" "$TEST_LOG" || echo "0")
    local failed_tests=$(grep -c "❌ FAIL" "$TEST_LOG" || echo "0")
    local info_tests=$(grep -c "ℹ️ INFO" "$TEST_LOG" || echo "0")
    
    echo "Total Tests: $total_tests" >> "$TEST_LOG"
    echo "Passed: $passed_tests" >> "$TEST_LOG" 
    echo "Failed: $failed_tests" >> "$TEST_LOG"
    echo "Info: $info_tests" >> "$TEST_LOG"
    echo "" >> "$TEST_LOG"
    
    if [[ "$failed_tests" -gt 0 ]]; then
        echo "❌ SOME TESTS FAILED" >> "$TEST_LOG"
        echo -e "${RED}❌ Test suite completed with $failed_tests failures${NC}"
    else
        echo "✅ ALL TESTS PASSED" >> "$TEST_LOG"
        echo -e "${GREEN}✅ All tests passed successfully!${NC}"
    fi
    
    echo -e "\n${BLUE}📄 Full test results saved to: $TEST_LOG${NC}"
    
    # Show summary on console
    echo -e "\n${YELLOW}SUMMARY:${NC}"
    echo -e "  Total: $total_tests"
    echo -e "  Passed: $passed_tests"
    echo -e "  Failed: $failed_tests"
    echo -e "  Info: $info_tests"
}

##############################################################################
# MAIN TEST EXECUTION
##############################################################################

main() {
    echo -e "${GREEN}🧪 Starting Comprehensive Leads System Test Suite${NC}"
    echo -e "${BLUE}Base URL: $BASE_URL${NC}"
    
    init_test_env
    
    # Run all tests in sequence
    echo -e "\n${YELLOW}=== PHASE 1: SETUP & AUTH ===${NC}"
    test_health_check
    get_csrf_token
    login_user
    
    echo -e "\n${YELLOW}=== PHASE 2: LEAD MANAGEMENT ===${NC}"
    test_list_leads_empty
    create_test_lead
    test_get_lead_details
    test_update_lead
    test_update_lead_status
    
    echo -e "\n${YELLOW}=== PHASE 3: ADVANCED FEATURES ===${NC}"
    test_create_reminder
    test_list_leads_with_filters
    test_bulk_operations
    test_whatsapp_placeholder
    
    echo -e "\n${YELLOW}=== PHASE 4: ERROR & SECURITY TESTING ===${NC}"
    test_error_handling
    test_csrf_validation
    
    generate_summary
}

# Allow running individual tests
case "${1:-all}" in
    "health") test_health_check ;;
    "auth") get_csrf_token && login_user ;;
    "create") create_test_lead ;;
    "list") test_list_leads_empty ;;
    "update") test_update_lead ;;
    "status") test_update_lead_status ;;
    "reminder") test_create_reminder ;;
    "bulk") test_bulk_operations ;;
    "errors") test_error_handling ;;
    "csrf") test_csrf_validation ;;
    "all"|*) main ;;
esac