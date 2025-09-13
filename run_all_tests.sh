#!/bin/bash

##############################################################################
# UNIFIED TEST RUNNER - BACKEND + FRONTEND TESTS
# Runs both curl API tests and Playwright UI tests
##############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
BASE_URL="${BASE_URL:-http://localhost:5000}"
RESULTS_DIR="test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$RESULTS_DIR/unified_test_report_$TIMESTAMP.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Test results tracking
BACKEND_TESTS_PASSED=0
BACKEND_TESTS_FAILED=0
FRONTEND_TESTS_PASSED=0
FRONTEND_TESTS_FAILED=0
START_TIME=$(date +%s)

# Cleanup function
cleanup() {
    echo -e "\n${BLUE}🧹 Cleaning up test environment${NC}"
    # Kill any remaining processes if needed
    pkill -f "node.*server" 2>/dev/null || true
    echo "Cleanup completed"
}

# Set cleanup trap
trap cleanup EXIT

# Create results directory
setup_test_environment() {
    echo -e "${BLUE}🔧 Setting up test environment${NC}"
    mkdir -p "$RESULTS_DIR"
    
    # Initialize report file
    cat > "$REPORT_FILE" << EOF
========================================
UNIFIED TEST SUITE REPORT
========================================
Started: $(date)
Base URL: $BASE_URL
Test Results Directory: $RESULTS_DIR
========================================

EOF
}

# Check if app is running
check_app_health() {
    echo -e "${BLUE}🔍 Checking application health${NC}"
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$BASE_URL/healthz" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Application is healthy${NC}"
            echo "✅ App health check passed" >> "$REPORT_FILE"
            return 0
        fi
        
        echo -e "${YELLOW}⏳ Attempt $attempt/$max_attempts: Waiting for app...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ Application health check failed after $max_attempts attempts${NC}"
    echo "❌ App health check failed" >> "$REPORT_FILE"
    return 1
}

# Run backend API tests
run_backend_tests() {
    echo -e "\n${PURPLE}🔧 PHASE 1: BACKEND API TESTS${NC}"
    echo "" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    echo "BACKEND API TESTS" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    
    if [ -f "curl_leads_test_suite.sh" ]; then
        echo -e "${BLUE}🚀 Running curl API tests...${NC}"
        
        # Run the curl test suite
        if bash curl_leads_test_suite.sh > "$RESULTS_DIR/backend_tests_$TIMESTAMP.log" 2>&1; then
            echo -e "${GREEN}✅ Backend API tests completed${NC}"
            
            # Parse results from curl test log
            local curl_log="/tmp/curl_test_results.log"
            if [ -f "$curl_log" ]; then
                local passed=$(grep -c "✅ PASS" "$curl_log" 2>/dev/null || echo "0")
                local failed=$(grep -c "❌ FAIL" "$curl_log" 2>/dev/null || echo "0")
                
                BACKEND_TESTS_PASSED=$passed
                BACKEND_TESTS_FAILED=$failed
                
                echo "Backend Tests - Passed: $passed, Failed: $failed" >> "$REPORT_FILE"
                
                # Copy curl results to our report
                echo "" >> "$REPORT_FILE"
                cat "$curl_log" >> "$REPORT_FILE" 2>/dev/null || echo "Could not read curl test results" >> "$REPORT_FILE"
            else
                echo "❌ Could not find curl test results" >> "$REPORT_FILE"
                BACKEND_TESTS_FAILED=1
            fi
        else
            echo -e "${RED}❌ Backend API tests failed${NC}"
            echo "❌ Backend API tests failed to run" >> "$REPORT_FILE"
            BACKEND_TESTS_FAILED=1
        fi
    else
        echo -e "${YELLOW}⚠️ curl_leads_test_suite.sh not found, skipping backend tests${NC}"
        echo "⚠️ Backend test suite not found" >> "$REPORT_FILE"
    fi
}

# Run frontend UI tests
run_frontend_tests() {
    echo -e "\n${PURPLE}🎭 PHASE 2: FRONTEND UI TESTS${NC}"
    echo "" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    echo "FRONTEND UI TESTS" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    
    if command -v npx >/dev/null 2>&1 && [ -f "playwright.config.ts" ]; then
        echo -e "${BLUE}🚀 Running Playwright UI tests...${NC}"
        
        # Set environment variables for Playwright
        export BASE_URL="$BASE_URL"
        export CI=false
        
        # Run Playwright tests
        if npx playwright test --reporter=list,json,html > "$RESULTS_DIR/frontend_tests_$TIMESTAMP.log" 2>&1; then
            echo -e "${GREEN}✅ Frontend UI tests completed${NC}"
            
            # Parse Playwright results
            if [ -f "$RESULTS_DIR/results.json" ]; then
                # Simple parsing of Playwright JSON results
                local total_tests=$(grep -o '"title"' "$RESULTS_DIR/results.json" | wc -l)
                local failed_tests=$(grep -o '"status":"failed"' "$RESULTS_DIR/results.json" | wc -l)
                local passed_tests=$((total_tests - failed_tests))
                
                FRONTEND_TESTS_PASSED=$passed_tests
                FRONTEND_TESTS_FAILED=$failed_tests
                
                echo "Frontend Tests - Passed: $passed_tests, Failed: $failed_tests" >> "$REPORT_FILE"
            else
                echo "⚠️ Could not parse Playwright results" >> "$REPORT_FILE"
            fi
            
            # Copy frontend test output
            echo "" >> "$REPORT_FILE"
            cat "$RESULTS_DIR/frontend_tests_$TIMESTAMP.log" >> "$REPORT_FILE" 2>/dev/null || echo "Could not read frontend test results" >> "$REPORT_FILE"
            
        else
            echo -e "${RED}❌ Frontend UI tests failed${NC}"
            echo "❌ Frontend UI tests failed to run" >> "$REPORT_FILE"
            FRONTEND_TESTS_FAILED=1
            
            # Still try to get some output
            cat "$RESULTS_DIR/frontend_tests_$TIMESTAMP.log" >> "$REPORT_FILE" 2>/dev/null || true
        fi
    else
        echo -e "${YELLOW}⚠️ Playwright not installed or configured, skipping frontend tests${NC}"
        echo "⚠️ Playwright not available" >> "$REPORT_FILE"
    fi
}

# Generate final report
generate_final_report() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local total_passed=$((BACKEND_TESTS_PASSED + FRONTEND_TESTS_PASSED))
    local total_failed=$((BACKEND_TESTS_FAILED + FRONTEND_TESTS_FAILED))
    local total_tests=$((total_passed + total_failed))
    
    echo -e "\n${BLUE}📊 GENERATING FINAL REPORT${NC}"
    
    # Append final summary to report file
    cat >> "$REPORT_FILE" << EOF

========================================
FINAL SUMMARY
========================================
Completed: $(date)
Duration: ${duration}s

BACKEND TESTS:
  Passed: $BACKEND_TESTS_PASSED
  Failed: $BACKEND_TESTS_FAILED

FRONTEND TESTS:
  Passed: $FRONTEND_TESTS_PASSED
  Failed: $FRONTEND_TESTS_FAILED

TOTAL:
  Passed: $total_passed
  Failed: $total_failed
  Total:  $total_tests

EOF

    # Console summary
    echo -e "\n${YELLOW}========================================${NC}"
    echo -e "${YELLOW}UNIFIED TEST SUITE SUMMARY${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo -e "Duration: ${duration}s"
    echo -e "\n${BLUE}Backend Tests:${NC}"
    echo -e "  ${GREEN}Passed: $BACKEND_TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $BACKEND_TESTS_FAILED${NC}"
    echo -e "\n${BLUE}Frontend Tests:${NC}"
    echo -e "  ${GREEN}Passed: $FRONTEND_TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $FRONTEND_TESTS_FAILED${NC}"
    echo -e "\n${BLUE}Total:${NC}"
    echo -e "  ${GREEN}Passed: $total_passed${NC}"
    echo -e "  ${RED}Failed: $total_failed${NC}"
    echo -e "  Total:  $total_tests"
    
    # Final status
    if [ $total_failed -eq 0 ] && [ $total_tests -gt 0 ]; then
        echo -e "\n${GREEN}🎉 ALL TESTS PASSED!${NC}"
        echo "🎉 ALL TESTS PASSED!" >> "$REPORT_FILE"
        echo -e "${GREEN}✅ Test suite completed successfully${NC}"
    elif [ $total_tests -eq 0 ]; then
        echo -e "\n${YELLOW}⚠️ NO TESTS EXECUTED${NC}"
        echo "⚠️ NO TESTS EXECUTED" >> "$REPORT_FILE"
        echo -e "${YELLOW}⚠️ Check test configuration${NC}"
    else
        echo -e "\n${RED}❌ SOME TESTS FAILED${NC}"
        echo "❌ SOME TESTS FAILED" >> "$REPORT_FILE"
        echo -e "${RED}❌ Test suite completed with failures${NC}"
    fi
    
    echo -e "\n${BLUE}📄 Full report saved to: $REPORT_FILE${NC}"
    echo -e "${BLUE}📁 Test artifacts in: $RESULTS_DIR/${NC}"
    
    # List generated files
    echo -e "\n${BLUE}Generated files:${NC}"
    ls -la "$RESULTS_DIR" | grep "$TIMESTAMP" || true
    
    # Return appropriate exit code
    if [ $total_failed -gt 0 ]; then
        return 1
    else
        return 0
    fi
}

# Install dependencies if needed
check_dependencies() {
    echo -e "${BLUE}📦 Checking dependencies${NC}"
    
    # Check if Playwright is installed
    if [ -f "playwright.config.ts" ] && ! command -v npx >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ npx not found, trying to install dependencies${NC}"
        if command -v npm >/dev/null 2>&1; then
            npm install
        fi
    fi
    
    # Install Playwright browsers if needed
    if [ -f "playwright.config.ts" ] && command -v npx >/dev/null 2>&1; then
        echo -e "${BLUE}🎭 Installing Playwright browsers...${NC}"
        npx playwright install chromium > /dev/null 2>&1 || echo "⚠️ Could not install Playwright browsers"
    fi
}

##############################################################################
# MAIN EXECUTION
##############################################################################

main() {
    echo -e "${GREEN}🚀 UNIFIED TEST SUITE STARTING${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo -e "${BLUE}Base URL: $BASE_URL${NC}"
    echo -e "${BLUE}Timestamp: $TIMESTAMP${NC}"
    
    setup_test_environment
    check_dependencies
    check_app_health
    
    # Run both test suites
    run_backend_tests
    run_frontend_tests
    
    # Generate final report
    generate_final_report
}

# Allow running specific test types
case "${1:-all}" in
    "backend"|"api")
        echo -e "${BLUE}🔧 Running only backend tests${NC}"
        setup_test_environment
        check_app_health
        run_backend_tests
        generate_final_report
        ;;
    "frontend"|"ui")
        echo -e "${BLUE}🎭 Running only frontend tests${NC}"
        setup_test_environment
        check_dependencies
        check_app_health
        run_frontend_tests
        generate_final_report
        ;;
    "all"|*)
        main
        ;;
esac