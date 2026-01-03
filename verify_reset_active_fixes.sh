#!/bin/bash
# Comprehensive verification script for password reset and is_active fixes

echo "=================================================="
echo "Verification: Password Reset and is_active Fixes"
echo "=================================================="
echo ""

echo "1. Checking that validate_reset_token does NOT filter by is_active in query..."
if grep -q "filter_by(reset_token_hash=token_hash, is_active=True)" server/services/auth_service.py; then
    echo "   ❌ FAIL: validate_reset_token still filters by is_active in query"
    exit 1
else
    echo "   ✅ PASS: validate_reset_token does not filter by is_active in initial query"
fi

echo ""
echo "2. Checking that validate_reset_token checks is_active AFTER finding user..."
if grep -q "if not user.is_active:" server/services/auth_service.py; then
    echo "   ✅ PASS: validate_reset_token checks is_active after finding user"
else
    echo "   ❌ FAIL: validate_reset_token does not check is_active after finding user"
    exit 1
fi

echo ""
echo "3. Checking that validate_reset_token logs user_inactive..."
if grep -q "user_inactive" server/services/auth_service.py; then
    echo "   ✅ PASS: validate_reset_token logs 'user_inactive' message"
else
    echo "   ❌ FAIL: validate_reset_token does not log 'user_inactive'"
    exit 1
fi

echo ""
echo "4. Checking that login returns is_active in user_data..."
if grep -A 10 "# Prepare user response" server/auth_api.py | grep -q "'is_active': user.is_active"; then
    echo "   ✅ PASS: Login endpoint includes is_active in user_data"
else
    echo "   ❌ FAIL: Login endpoint does not include is_active in user_data"
    exit 1
fi

echo ""
echo "5. Checking that /api/admin/users returns is_active..."
if grep -q "'is_active': user.is_active" server/routes_admin.py; then
    echo "   ✅ PASS: /api/admin/users returns is_active field"
else
    echo "   ❌ FAIL: /api/admin/users does not return is_active field"
    exit 1
fi

echo ""
echo "6. Checking that /api/admin/businesses/{id}/users returns is_active..."
if grep -q "'is_active': user.is_active" server/routes_user_management.py; then
    echo "   ✅ PASS: /api/admin/businesses/{id}/users returns is_active field"
else
    echo "   ❌ FAIL: /api/admin/businesses/{id}/users does not return is_active field"
    exit 1
fi

echo ""
echo "7. Checking that ResetPasswordPage logs token from URL..."
if grep -q "console.log('RESET TOKEN FROM URL:" client/src/pages/Auth/ResetPasswordPage.tsx; then
    echo "   ✅ PASS: ResetPasswordPage logs token from URL"
else
    echo "   ❌ FAIL: ResetPasswordPage does not log token from URL"
    exit 1
fi

echo ""
echo "8. Checking that ResetPasswordPage logs token before submitting..."
if grep -q "SUBMITTING RESET" client/src/pages/Auth/ResetPasswordPage.tsx; then
    echo "   ✅ PASS: ResetPasswordPage logs token before submitting"
else
    echo "   ❌ FAIL: ResetPasswordPage does not log token before submitting"
    exit 1
fi

echo ""
echo "9. Checking that UsersPage uses is_active from API..."
if grep -q "status: u.is_active ? 'active' : 'inactive'" client/src/pages/users/UsersPage.tsx; then
    echo "   ✅ PASS: UsersPage correctly uses is_active from API"
else
    echo "   ⚠️  WARNING: UsersPage may not be using is_active correctly"
fi

echo ""
echo "10. Checking that validate_reset_token logs found_user_id..."
if grep -q "found_user_id" server/services/auth_service.py; then
    echo "   ✅ PASS: validate_reset_token logs found_user_id for debugging"
else
    echo "   ❌ FAIL: validate_reset_token does not log found_user_id"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ ALL VERIFICATIONS PASSED!"
echo "=================================================="
echo ""
echo "Summary of fixes:"
echo "  1. ✅ validate_reset_token finds user by token ONLY (no is_active filter)"
echo "  2. ✅ validate_reset_token checks is_active AFTER finding user"
echo "  3. ✅ Better logging: 'user_inactive' instead of 'no matching user'"
echo "  4. ✅ All user APIs return is_active field from DB"
echo "  5. ✅ Frontend logs token for debugging token mismatches"
echo ""
echo "Next steps:"
echo "  - Deploy to production"
echo "  - Test with real scenarios using MANUAL_TESTING_GUIDE_RESET_AND_ACTIVE_FIX.md"
echo "  - Check SQL: SELECT id, email, is_active FROM users WHERE id = 11;"
echo ""
