#!/bin/bash
# Verification script for DIDWW/PJSIP configuration fix
# Run this after deploying the fixed configuration

set -e

echo "==================================="
echo "DIDWW PJSIP Configuration Validator"
echo "==================================="
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.sip.yml" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

echo "1. Checking pjsip.conf for ENV variables..."
if grep -q '\${DIDWW' infra/asterisk/pjsip.conf; then
    echo "   ❌ FAILED: Found DIDWW ENV variables in pjsip.conf"
    grep '\${DIDWW' infra/asterisk/pjsip.conf
    exit 1
else
    echo "   ✅ PASSED: No DIDWW ENV variables found"
fi

echo ""
echo "2. Checking for hardcoded sip.didww.com..."
if grep -q "sip.didww.com" infra/asterisk/pjsip.conf; then
    echo "   ✅ PASSED: Found hardcoded sip.didww.com"
else
    echo "   ❌ FAILED: sip.didww.com not found"
    exit 1
fi

echo ""
echo "3. Checking for DIDWW IP addresses..."
REQUIRED_IPS=("46.19.210.14" "89.105.196.76" "80.93.48.76" "89.105.205.76")
for ip in "${REQUIRED_IPS[@]}"; do
    if grep -q "$ip" infra/asterisk/pjsip.conf; then
        echo "   ✅ Found IP: $ip"
    else
        echo "   ❌ Missing IP: $ip"
        exit 1
    fi
done

echo ""
echo "4. Checking dialplan configuration..."
if grep -q "context=from-trunk" infra/asterisk/pjsip.conf; then
    echo "   ✅ PASSED: Endpoint context is from-trunk"
else
    echo "   ❌ FAILED: Endpoint context not set correctly"
    exit 1
fi

if grep -q "Stasis(prosaas_ai" infra/asterisk/extensions.conf; then
    echo "   ✅ PASSED: Stasis application prosaas_ai configured"
else
    echo "   ❌ FAILED: Stasis application not configured"
    exit 1
fi

echo ""
echo "5. Checking endpoint settings..."
REQUIRED_SETTINGS=("transport=transport-udp" "rtp_symmetric=yes" "force_rport=yes" "rewrite_contact=yes" "direct_media=no")
for setting in "${REQUIRED_SETTINGS[@]}"; do
    if grep -q "$setting" infra/asterisk/pjsip.conf; then
        echo "   ✅ Found: $setting"
    else
        echo "   ❌ Missing: $setting"
        exit 1
    fi
done

echo ""
echo "==================================="
echo "✅ All configuration checks PASSED!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Restart Asterisk:"
echo "   docker-compose -f docker-compose.sip.yml restart asterisk"
echo "   # OR (newer Docker): docker compose -f docker-compose.sip.yml restart asterisk"
echo ""
echo "2. Verify endpoint registration in Asterisk:"
echo "   docker exec -it prosaas-asterisk asterisk -rx 'pjsip show endpoints'"
echo ""
echo "3. Verify identify mappings:"
echo "   docker exec -it prosaas-asterisk asterisk -rx 'pjsip show identify'"
echo ""
echo "4. Check Asterisk logs during test call:"
echo "   docker logs -f prosaas-asterisk"
echo ""
echo "Expected behavior:"
echo "- INVITE from 46.19.210.14 should match didww-identify"
echo "- Call should route to context=from-trunk"
echo "- Call should enter Stasis(prosaas_ai)"
echo "- No more 'No matching endpoint found' errors"
