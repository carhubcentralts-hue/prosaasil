#!/bin/bash
# Quick verification of the 3 critical DIDWW/PJSIP fix points
# Run this to ensure the fix is complete and correct

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  DIDWW/PJSIP Fix - 3 Critical Points Verification         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

FAILED=0

# Point 1: identify uses 'match=' not 'ip='
echo "Point 1: Verify identify section uses 'match=' syntax"
echo "────────────────────────────────────────────────────────────"

if grep -q "type=identify" infra/asterisk/pjsip.conf && \
   grep -A5 "didww-identify" infra/asterisk/pjsip.conf | grep -q "match=46.19.210.14"; then
    echo "✅ PASS: identify section uses 'match=' (CORRECT)"
    echo ""
    grep -A10 "didww-identify" infra/asterisk/pjsip.conf
else
    echo "❌ FAIL: identify section not configured correctly"
    FAILED=1
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Point 2: from-trunk context catches all numbers with _X. pattern
echo "Point 2: Verify from-trunk context has _X. pattern"
echo "────────────────────────────────────────────────────────────"

if grep -A15 "\[from-trunk\]" infra/asterisk/extensions.conf | grep -q "exten => _X"; then
    echo "✅ PASS: Pattern '_X.' present (CORRECT)"
    echo ""
    echo "Dialplan flow:"
    grep -A15 "\[from-trunk\]" infra/asterisk/extensions.conf | grep -E "(exten|Answer|Stasis)" | head -5
else
    echo "❌ FAIL: No _X. pattern found in from-trunk context"
    FAILED=1
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Point 3: External IP configuration guidance
echo "Point 3: External IP configuration check"
echo "────────────────────────────────────────────────────────────"

if grep -q "external_media_address" infra/asterisk/pjsip.conf; then
    if grep "external_media_address" infra/asterisk/pjsip.conf | grep -q "^;"; then
        echo "⚠️  INFO: external_media_address is commented out (default)"
        echo ""
        echo "This is CORRECT for VPS with public IP (e.g., 213.199.43.223)"
        echo ""
        echo "If you have NAT issues or no audio, uncomment and set:"
        grep "external_media_address" infra/asterisk/pjsip.conf
        grep "external_signaling_address" infra/asterisk/pjsip.conf
    else
        echo "✅ INFO: external_media_address is configured"
        grep "external_media_address" infra/asterisk/pjsip.conf
    fi
else
    echo "⚠️  WARNING: No external_media_address configuration found"
    echo "If server is behind NAT, you may need to add it"
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ✅ ALL 3 CRITICAL POINTS VERIFIED                         ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Configuration is READY for deployment!"
    echo ""
    echo "Next: Deploy and verify on the server:"
    echo ""
    echo "1. Restart Asterisk:"
    echo "   docker-compose -f docker-compose.sip.yml restart asterisk"
    echo ""
    echo "2. Check endpoints:"
    echo "   docker exec -it prosaas-asterisk asterisk -rx 'pjsip show endpoints'"
    echo ""
    echo "3. Check identify (THIS IS CRITICAL):"
    echo "   docker exec -it prosaas-asterisk asterisk -rx 'pjsip show identify'"
    echo ""
    echo "   Expected output:"
    echo "   Identify:  didww-identify/didww"
    echo "              Match: 46.19.210.14"
    echo "              Match: 89.105.196.76"
    echo "              Match: 80.93.48.76"
    echo "              Match: 89.105.205.76"
    echo ""
    echo "4. Test call and check logs:"
    echo "   docker logs -f prosaas-asterisk"
    echo ""
    echo "   ✅ Should see: Matched endpoint 'didww'"
    echo "   ✅ Should see: Executing from-trunk"
    echo "   ✅ Should see: Stasis(prosaas_ai"
    echo "   ❌ Should NOT see: No matching endpoint found"
    echo ""
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  ❌ VERIFICATION FAILED                                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Please fix the issues above before deploying"
    exit 1
fi
