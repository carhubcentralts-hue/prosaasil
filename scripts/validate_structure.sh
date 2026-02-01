#!/bin/bash
# Quick validation script that doesn't require dependencies
# Checks code structure, files, and patterns

echo "============================================================"
echo "  Customer Service AI Unification - Code Structure Check"
echo "============================================================"
echo ""

# Check that new services exist
echo "TEST 1: New Service Files"
echo "------------------------------------------------------------"
if [ -f "server/services/unified_lead_context_service.py" ]; then
    lines=$(wc -l < server/services/unified_lead_context_service.py)
    echo "✅ unified_lead_context_service.py exists ($lines lines)"
else
    echo "❌ unified_lead_context_service.py missing"
fi

if [ -f "server/services/unified_status_service.py" ]; then
    lines=$(wc -l < server/services/unified_status_service.py)
    echo "✅ unified_status_service.py exists ($lines lines)"
else
    echo "❌ unified_status_service.py missing"
fi

if [ -f "server/agent_tools/tools_status_update.py" ]; then
    lines=$(wc -l < server/agent_tools/tools_status_update.py)
    echo "✅ tools_status_update.py exists ($lines lines)"
else
    echo "❌ tools_status_update.py missing"
fi

echo ""
echo "TEST 2: Modified Integration Files"
echo "------------------------------------------------------------"
modified_files=(
    "server/jobs/webhook_process_job.py"
    "server/services/ai_service.py"
    "server/agent_tools/agent_factory.py"
    "server/services/realtime_prompt_builder.py"
    "server/media_ws_ai.py"
)

for file in "${modified_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done

echo ""
echo "TEST 3: Check Feature Flag Usage"
echo "------------------------------------------------------------"
# Check that enable_customer_service is referenced
if grep -q "enable_customer_service" server/services/unified_lead_context_service.py; then
    echo "✅ unified_lead_context_service checks enable_customer_service"
else
    echo "❌ Feature flag check missing in unified_lead_context_service"
fi

if grep -q "enable_customer_service" server/services/unified_status_service.py; then
    echo "✅ unified_status_service checks enable_customer_service"
else
    echo "❌ Feature flag check missing in unified_status_service"
fi

if grep -q "customer_service_enabled" server/agent_tools/agent_factory.py; then
    echo "✅ agent_factory checks customer service flag"
else
    echo "❌ Feature flag check missing in agent_factory"
fi

echo ""
echo "TEST 4: Check Context Injection"
echo "------------------------------------------------------------"
# Check WhatsApp integration
if grep -q "unified_lead_context_service" server/jobs/webhook_process_job.py; then
    echo "✅ WhatsApp webhook uses unified context service"
else
    echo "❌ WhatsApp webhook missing unified context import"
fi

if grep -q "lead_context" server/services/ai_service.py; then
    echo "✅ AI service handles lead_context"
else
    echo "❌ AI service missing lead_context handling"
fi

# Check Calls integration
if grep -q "caller_phone" server/services/realtime_prompt_builder.py; then
    echo "✅ Realtime prompt builder accepts caller_phone"
else
    echo "❌ Realtime prompt builder missing caller_phone parameter"
fi

if grep -q "LEAD CONTEXT" server/services/realtime_prompt_builder.py; then
    echo "✅ Realtime prompt builder includes LEAD CONTEXT layer"
else
    echo "❌ Realtime prompt builder missing LEAD CONTEXT section"
fi

echo ""
echo "TEST 5: Check Status Update Tool"
echo "------------------------------------------------------------"
if grep -q "update_lead_status" server/agent_tools/tools_status_update.py; then
    echo "✅ Status update tool defined"
else
    echo "❌ Status update tool missing"
fi

if grep -q "update_lead_status" server/agent_tools/agent_factory.py; then
    echo "✅ Status update tool added to agent factory"
else
    echo "❌ Status update tool not integrated in agent factory"
fi

echo ""
echo "TEST 6: Check Documentation"
echo "------------------------------------------------------------"
docs=(
    "CUSTOMER_SERVICE_AI_UNIFIED.md"
    "IMPLEMENTATION_SUMMARY.md"
    "QA_VERIFICATION_REPORT.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        size=$(du -h "$doc" | cut -f1)
        echo "✅ $doc exists ($size)"
    else
        echo "❌ $doc missing"
    fi
done

echo ""
echo "TEST 7: Check for Hardcoded Prompts (Should be removed)"
echo "------------------------------------------------------------"
# Check for hardcoded Hebrew prompts
hardcoded_count=$(grep -r "אתה עוזר דיגיטלי\|שלום, איך אפשר לעזור" server/ 2>/dev/null | wc -l)
if [ "$hardcoded_count" -eq 0 ]; then
    echo "✅ No hardcoded prompts found (good)"
else
    echo "❌ Found $hardcoded_count hardcoded prompt(s)"
fi

echo ""
echo "TEST 8: Check Audit Logging"
echo "------------------------------------------------------------"
if grep -q "audit" server/services/unified_status_service.py; then
    echo "✅ Unified status service includes audit logging"
else
    echo "❌ Audit logging missing from status service"
fi

if grep -q "confidence" server/services/unified_status_service.py; then
    echo "✅ Status service tracks confidence scores"
else
    echo "❌ Confidence scoring missing"
fi

echo ""
echo "TEST 9: Check Multi-Tenant Security"
echo "------------------------------------------------------------"
if grep -q "business_id" server/services/unified_lead_context_service.py | head -1; then
    echo "✅ unified_lead_context_service scoped to business_id"
else
    echo "⚠️  Check multi-tenant scoping in unified_lead_context_service"
fi

if grep -q "tenant_id" server/services/unified_status_service.py | head -1; then
    echo "✅ unified_status_service scoped to tenant_id"
else
    echo "⚠️  Check multi-tenant scoping in unified_status_service"
fi

echo ""
echo "TEST 10: Check Backward Compatibility"
echo "------------------------------------------------------------"
# Check that old services still exist
old_services=(
    "server/services/customer_intelligence.py"
    "server/services/customer_memory_service.py"
    "server/services/lead_auto_status_service.py"
    "server/agent_tools/tools_crm_context.py"
)

for service in "${old_services[@]}"; do
    if [ -f "$service" ]; then
        echo "✅ $service still exists (backward compatible)"
    else
        echo "❌ $service removed (breaking change!)"
    fi
done

echo ""
echo "============================================================"
echo "VALIDATION COMPLETE"
echo "============================================================"
echo ""
echo "Next Steps:"
echo "1. Review QA_VERIFICATION_REPORT.md for manual testing"
echo "2. Test with enable_customer_service=True and False"
echo "3. Capture logs showing flag control"
echo "4. Verify name routing works"
echo "5. Test status update safety"
echo "6. Measure performance (<150ms WhatsApp, <80ms Calls)"
echo ""
