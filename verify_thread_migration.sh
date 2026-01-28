#!/bin/bash
# Thread Migration Verification Script
# Verifies that all non-realtime threads have been migrated to RQ

echo "🔍 Thread Migration Verification"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for issues
ISSUES=0

echo "1️⃣ Checking for non-realtime thread usage..."
echo "   (Excluding: media_ws_ai.py, gcp_stt_stream, worker.py, safe_thread.py, logging_async.py)"
echo ""

# Find threads that shouldn't be there
NON_REALTIME_THREADS=$(grep -r "threading.Thread\|Thread(target" server --include="*.py" \
    | grep -v "media_ws_ai.py" \
    | grep -v "gcp_stt_stream" \
    | grep -v "worker.py" \
    | grep -v "safe_thread.py" \
    | grep -v "logging_async.py" \
    | grep -v "# " \
    | grep -v "Replaces threading.Thread" \
    | grep -v "_scheduler_thread: Optional\[threading.Thread\]")

if [ -z "$NON_REALTIME_THREADS" ]; then
    echo -e "${GREEN}✅ PASS: No non-realtime threads found${NC}"
else
    echo -e "${RED}❌ FAIL: Non-realtime threads detected:${NC}"
    echo "$NON_REALTIME_THREADS"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "2️⃣ Checking required RQ jobs exist..."
echo ""

REQUIRED_JOBS=(
    "server/jobs/webhook_process_job.py"
    "server/jobs/push_send_job.py"
    "server/jobs/reminders_tick_job.py"
    "server/jobs/whatsapp_sessions_cleanup_job.py"
)

for job in "${REQUIRED_JOBS[@]}"; do
    if [ -f "$job" ]; then
        echo -e "${GREEN}✅ $job${NC}"
    else
        echo -e "${RED}❌ $job - MISSING${NC}"
        ISSUES=$((ISSUES + 1))
    fi
done

echo ""
echo "3️⃣ Checking scheduler service exists..."
echo ""

if [ -f "server/scheduler/run_scheduler.py" ]; then
    echo -e "${GREEN}✅ server/scheduler/run_scheduler.py${NC}"
else
    echo -e "${RED}❌ server/scheduler/run_scheduler.py - MISSING${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "4️⃣ Checking docker-compose has scheduler service..."
echo ""

if grep -q "scheduler:" docker-compose.yml; then
    echo -e "${GREEN}✅ Scheduler service defined in docker-compose.yml${NC}"
    
    # Check SERVICE_ROLE
    if grep -A 10 "scheduler:" docker-compose.yml | grep -q "SERVICE_ROLE: scheduler"; then
        echo -e "${GREEN}✅ SERVICE_ROLE=scheduler configured${NC}"
    else
        echo -e "${RED}❌ SERVICE_ROLE not set for scheduler${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "${RED}❌ Scheduler service NOT found in docker-compose.yml${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "5️⃣ Checking API service has correct SERVICE_ROLE..."
echo ""

if sed -n '372,410p' docker-compose.yml | grep -q "SERVICE_ROLE.*api"; then
    echo -e "${GREEN}✅ API service: SERVICE_ROLE=api${NC}"
else
    echo -e "${YELLOW}⚠️  API service: SERVICE_ROLE not explicitly set${NC}"
fi

if sed -n '372,410p' docker-compose.yml | grep -q "ENABLE_SCHEDULERS.*false"; then
    echo -e "${GREEN}✅ API service: ENABLE_SCHEDULERS=false${NC}"
else
    echo -e "${RED}❌ API service: ENABLE_SCHEDULERS not set to false${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "6️⃣ Checking calls service has correct SERVICE_ROLE..."
echo ""

if sed -n '439,480p' docker-compose.yml | grep -q "SERVICE_ROLE.*calls"; then
    echo -e "${GREEN}✅ Calls service: SERVICE_ROLE=calls${NC}"
else
    echo -e "${YELLOW}⚠️  Calls service: SERVICE_ROLE not explicitly set${NC}"
fi

if sed -n '439,480p' docker-compose.yml | grep -q "ENABLE_SCHEDULERS.*false"; then
    echo -e "${GREEN}✅ Calls service: ENABLE_SCHEDULERS=false${NC}"
else
    echo -e "${RED}❌ Calls service: ENABLE_SCHEDULERS not set to false${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "7️⃣ Checking worker service configuration..."
echo ""

if sed -n '176,235p' docker-compose.yml | grep -q "SERVICE_ROLE.*worker"; then
    echo -e "${GREEN}✅ Worker service: SERVICE_ROLE=worker${NC}"
else
    echo -e "${YELLOW}⚠️  Worker service: SERVICE_ROLE not explicitly set${NC}"
fi

if sed -n '176,235p' docker-compose.yml | grep -q "python.*server.worker"; then
    echo -e "${GREEN}✅ Worker service: Runs RQ worker${NC}"
else
    echo -e "${RED}❌ Worker service: Not configured to run RQ worker${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "8️⃣ Checking deprecated functions are marked..."
echo ""

# Check reminder_scheduler.py
if grep -q "DEPRECATED" server/services/notifications/reminder_scheduler.py; then
    echo -e "${GREEN}✅ reminder_scheduler.py marked as deprecated${NC}"
else
    echo -e "${RED}❌ reminder_scheduler.py not marked as deprecated${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check whatsapp_session_service.py
if grep -q "DEPRECATED" server/services/whatsapp_session_service.py; then
    echo -e "${GREEN}✅ whatsapp_session_service.py marked as deprecated${NC}"
else
    echo -e "${RED}❌ whatsapp_session_service.py not marked as deprecated${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "9️⃣ Checking Python syntax of new files..."
echo ""

python3 -m py_compile \
    server/jobs/webhook_process_job.py \
    server/jobs/push_send_job.py \
    server/jobs/reminders_tick_job.py \
    server/jobs/whatsapp_sessions_cleanup_job.py \
    server/scheduler/run_scheduler.py \
    2>&1 > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All Python files have valid syntax${NC}"
else
    echo -e "${RED}❌ Python syntax errors detected${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "🔟 Checking documentation exists..."
echo ""

if [ -f "THREADING_MIGRATION_COMPLETE.md" ]; then
    echo -e "${GREEN}✅ THREADING_MIGRATION_COMPLETE.md${NC}"
else
    echo -e "${RED}❌ THREADING_MIGRATION_COMPLETE.md - MISSING${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [ -f "THREADING_MIGRATION_VISUAL_HE.md" ]; then
    echo -e "${GREEN}✅ THREADING_MIGRATION_VISUAL_HE.md${NC}"
else
    echo -e "${YELLOW}⚠️  THREADING_MIGRATION_VISUAL_HE.md - MISSING${NC}"
fi

echo ""
echo "================================"
echo "Summary"
echo "================================"
echo ""

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "🎉 Thread-to-RQ migration is complete and verified!"
    echo ""
    echo "Next steps:"
    echo "1. Deploy services: docker-compose up -d"
    echo "2. Check scheduler logs: docker-compose logs -f scheduler"
    echo "3. Check worker logs: docker-compose logs -f worker"
    echo "4. Verify no threads in API logs"
    echo "5. Monitor Redis queues: redis-cli LLEN rq:queue:default"
    exit 0
else
    echo -e "${RED}❌ VERIFICATION FAILED${NC}"
    echo ""
    echo "Found $ISSUES issue(s) that need to be addressed."
    echo ""
    echo "Please review the output above and fix the issues."
    exit 1
fi
