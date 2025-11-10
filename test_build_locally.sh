#!/usr/bin/env bash
# Test build locally to find bottlenecks

echo "🧪 Testing build script locally..."
echo ""
echo "This will help identify which phase is slow/failing"
echo ""

time bash build_production.sh 2>&1 | tee /tmp/build_test.log

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Build test complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Full log: /tmp/build_test.log"
echo ""
echo "If build failed, check the log for errors"
