#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 REALTIME STABILITY VERIFICATION SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════
# 
# This script verifies the Realtime/Greeting/Cold-start stability improvements.
# Run it after deployment to check if the changes are working correctly.
#
# Usage:
#   ./verify_realtime_stability.sh [logfile]
#
# If no logfile is provided, it will try to read from /var/log/app.log or stdin.
# ═══════════════════════════════════════════════════════════════════════════════

set -e

LOGFILE="${1:-/var/log/app.log}"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🔥 REALTIME STABILITY VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Check if logfile exists
if [ ! -f "$LOGFILE" ]; then
    echo "⚠️  Logfile not found: $LOGFILE"
    echo "    Provide a logfile as argument or pipe logs via stdin."
    echo ""
    echo "Usage:"
    echo "    $0 /path/to/logfile"
    echo "    journalctl -u myapp | $0 /dev/stdin"
    echo ""
    exit 1
fi

echo "📂 Analyzing: $LOGFILE"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Check for REALTIME_FATAL errors (no silent failures)
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 1: Check for REALTIME_FATAL errors"
echo "═══════════════════════════════════════════════════════════════════════════════"

FATAL_COUNT=$(grep -c "REALTIME_FATAL" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$FATAL_COUNT" -gt 0 ]; then
    echo "⚠️  Found $FATAL_COUNT REALTIME_FATAL errors:"
    grep "REALTIME_FATAL" "$LOGFILE" | head -10
    echo ""
    echo "   (Showing first 10 - check logs for full details)"
else
    echo "✅ No REALTIME_FATAL errors found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Check for NO_START_EVENT_FROM_TWILIO errors
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 2: Check for START event timeouts"
echo "═══════════════════════════════════════════════════════════════════════════════"

NO_START_COUNT=$(grep -c "NO_START_EVENT_FROM_TWILIO" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$NO_START_COUNT" -gt 0 ]; then
    echo "⚠️  Found $NO_START_COUNT NO_START_EVENT_FROM_TWILIO errors:"
    grep "NO_START_EVENT_FROM_TWILIO" "$LOGFILE" | head -5
else
    echo "✅ No START event timeouts found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Check for OPENAI_CONNECT_TIMEOUT errors
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 3: Check for OpenAI connection timeouts"
echo "═══════════════════════════════════════════════════════════════════════════════"

OPENAI_TIMEOUT_COUNT=$(grep -c "OPENAI_CONNECT_TIMEOUT" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$OPENAI_TIMEOUT_COUNT" -gt 0 ]; then
    echo "⚠️  Found $OPENAI_TIMEOUT_COUNT OpenAI connection timeouts:"
    grep "OPENAI_CONNECT_TIMEOUT" "$LOGFILE" | head -5
else
    echo "✅ No OpenAI connection timeouts found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Check for NO_AUDIO_FROM_OPENAI greeting timeouts
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 4: Check for greeting audio timeouts"
echo "═══════════════════════════════════════════════════════════════════════════════"

NO_AUDIO_COUNT=$(grep -c "NO_AUDIO_FROM_OPENAI" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$NO_AUDIO_COUNT" -gt 0 ]; then
    echo "⚠️  Found $NO_AUDIO_COUNT greeting audio timeouts:"
    grep "NO_AUDIO_FROM_OPENAI" "$LOGFILE" | head -5
else
    echo "✅ No greeting audio timeouts found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: Check for SILENT_FAILURE_DETECTED (tx=0 without marked failure)
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 5: Check for silent failures (tx=0 without marked failure)"
echo "═══════════════════════════════════════════════════════════════════════════════"

SILENT_FAILURE_COUNT=$(grep -c "SILENT_FAILURE_DETECTED" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$SILENT_FAILURE_COUNT" -gt 0 ]; then
    echo "⚠️  Found $SILENT_FAILURE_COUNT silent failures (tx=0 without marked realtime failure):"
    grep "SILENT_FAILURE_DETECTED" "$LOGFILE" | head -5
else
    echo "✅ No silent failures found"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Analyze REALTIME_TIMINGS metrics
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 6: Analyze greeting timing metrics"
echo "═══════════════════════════════════════════════════════════════════════════════"

METRICS_COUNT=$(grep -c "REALTIME_TIMINGS" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$METRICS_COUNT" -gt 0 ]; then
    echo "📊 Found $METRICS_COUNT calls with timing metrics"
    echo ""
    
    # Extract and analyze openai_connect_ms values
    echo "OpenAI Connection Times:"
    grep "REALTIME_TIMINGS" "$LOGFILE" | \
        sed -n 's/.*openai_connect_ms=\([0-9]*\).*/\1/p' | \
        awk '{
            sum += $1;
            count++;
            if ($1 > max) max = $1;
            if (min == "" || $1 < min) min = $1;
            if ($1 > 1500) slow++;
        }
        END {
            if (count > 0) {
                printf "  - Count: %d\n", count;
                printf "  - Average: %.0f ms\n", sum/count;
                printf "  - Min: %d ms\n", min;
                printf "  - Max: %d ms\n", max;
                printf "  - Slow (>1500ms): %d (%.1f%%)\n", slow, slow*100/count;
                if (sum/count <= 1500) {
                    print "  ✅ Average is within target (≤1500ms)";
                } else {
                    print "  ⚠️  Average exceeds target (>1500ms)";
                }
            }
        }'
    echo ""
    
    # Extract and analyze first_greeting_audio_ms values
    echo "First Greeting Audio Times:"
    grep "REALTIME_TIMINGS" "$LOGFILE" | \
        sed -n 's/.*first_greeting_audio_ms=\([0-9]*\).*/\1/p' | \
        awk '{
            if ($1 > 0) {
                sum += $1;
                count++;
                if ($1 > max) max = $1;
                if (min == "" || $1 < min) min = $1;
                if ($1 > 2000) slow++;
            }
        }
        END {
            if (count > 0) {
                printf "  - Count: %d (calls with greeting audio)\n", count;
                printf "  - Average: %.0f ms\n", sum/count;
                printf "  - Min: %d ms\n", min;
                printf "  - Max: %d ms\n", max;
                printf "  - Slow (>2000ms): %d (%.1f%%)\n", slow, slow*100/count;
                if (sum/count <= 2000) {
                    print "  ✅ Average is within target (≤2000ms)";
                } else {
                    print "  ⚠️  Average exceeds target (>2000ms)";
                }
            } else {
                print "  - No greeting audio data found";
            }
        }'
    echo ""
    
    # Check realtime_failed count
    echo "Realtime Failure Rate:"
    FAILED_COUNT=$(grep "REALTIME_TIMINGS" "$LOGFILE" | grep -c "realtime_failed=True" 2>/dev/null || echo "0")
    SUCCESS_COUNT=$(grep "REALTIME_TIMINGS" "$LOGFILE" | grep -c "realtime_failed=False" 2>/dev/null || echo "0")
    TOTAL=$((FAILED_COUNT + SUCCESS_COUNT))
    if [ "$TOTAL" -gt 0 ]; then
        FAIL_RATE=$(echo "scale=1; $FAILED_COUNT * 100 / $TOTAL" | bc)
        echo "  - Total calls: $TOTAL"
        echo "  - Successful: $SUCCESS_COUNT"
        echo "  - Failed: $FAILED_COUNT ($FAIL_RATE%)"
        if [ "$FAILED_COUNT" -gt 0 ]; then
            echo ""
            echo "  Failure reasons:"
            grep "REALTIME_TIMINGS.*realtime_failed=True" "$LOGFILE" | \
                sed -n 's/.*reason=\([^,]*\).*/\1/p' | sort | uniq -c | sort -rn
        fi
    fi
else
    echo "⚠️  No REALTIME_TIMINGS metrics found in logs"
    echo "   Make sure the new code is deployed and calls have been made."
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Check for REALTIME_FALLBACK entries
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 7: Check fallback handling"
echo "═══════════════════════════════════════════════════════════════════════════════"

FALLBACK_COUNT=$(grep -c "REALTIME_FALLBACK" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$FALLBACK_COUNT" -gt 0 ]; then
    echo "⚠️  Found $FALLBACK_COUNT calls that triggered fallback:"
    grep "REALTIME_FALLBACK" "$LOGFILE" | head -5
    echo ""
    echo "   Fallback reasons:"
    grep "REALTIME_FALLBACK" "$LOGFILE" | sed -n 's/.*reason=\([^)]*\).*/\1/p' | sort | uniq -c | sort -rn
else
    echo "✅ No fallback triggers found (good - realtime is working)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Check T0 WS_START logs (WebSocket open tracking)
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "TEST 8: Check T0 WS_START tracking"
echo "═══════════════════════════════════════════════════════════════════════════════"

T0_COUNT=$(grep -c "\[T0\] WS_START" "$LOGFILE" 2>/dev/null || echo "0")
if [ "$T0_COUNT" -gt 0 ]; then
    echo "✅ Found $T0_COUNT calls with T0 tracking (WebSocket open timestamp)"
else
    echo "⚠️  No T0 WS_START logs found - new code may not be deployed"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "SUMMARY"
echo "═══════════════════════════════════════════════════════════════════════════════"

ISSUES=0

if [ "$FATAL_COUNT" -gt 0 ]; then
    echo "❌ REALTIME_FATAL errors: $FATAL_COUNT"
    ISSUES=$((ISSUES + 1))
fi

if [ "$SILENT_FAILURE_COUNT" -gt 0 ]; then
    echo "❌ Silent failures: $SILENT_FAILURE_COUNT"
    ISSUES=$((ISSUES + 1))
fi

if [ "$NO_START_COUNT" -gt 0 ]; then
    echo "⚠️  START timeouts: $NO_START_COUNT"
fi

if [ "$OPENAI_TIMEOUT_COUNT" -gt 0 ]; then
    echo "⚠️  OpenAI timeouts: $OPENAI_TIMEOUT_COUNT"
fi

if [ "$NO_AUDIO_COUNT" -gt 0 ]; then
    echo "⚠️  Greeting audio timeouts: $NO_AUDIO_COUNT"
fi

if [ "$FALLBACK_COUNT" -gt 0 ]; then
    echo "⚠️  Fallback triggers: $FALLBACK_COUNT"
fi

if [ "$ISSUES" -eq 0 ]; then
    echo ""
    echo "✅ All critical checks passed!"
    echo "   The realtime stability improvements appear to be working correctly."
else
    echo ""
    echo "⚠️  Found $ISSUES critical issues that need attention."
    echo "   Review the logs for details."
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
