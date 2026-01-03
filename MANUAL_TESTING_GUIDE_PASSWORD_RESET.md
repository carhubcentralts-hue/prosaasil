# Password Reset Flow - Manual Testing Guide

## Prerequisites
1. Ensure SendGrid is configured with valid API key
2. Ensure `PUBLIC_BASE_URL` environment variable is set correctly
3. Have access to email account for testing

## Test Scenario 1: Happy Path (Full Flow)

### Steps
1. **Request Password Reset**
   - Navigate to login page
   - Click "Forgot Password" link
   - Enter a valid email address
   - Click "Send Reset Link"
   - ✅ **Expected:** Success message appears (even if email doesn't exist - security feature)

2. **Check Email**
   - Open email inbox for the test user
   - ✅ **Expected:** Email with subject "Password Reset Request" received
   - ✅ **Expected:** Email contains a reset link like: `https://app.prosaas.co/reset-password?token=XXXXXXX`

3. **Open Reset Link**
   - Click the reset link in email
   - ✅ **Expected:** Password reset page loads successfully
   - ✅ **Expected:** No error messages appear
   - ✅ **Expected:** Form shows two password fields

4. **Submit New Password**
   - Enter a new password (must meet requirements: 8+ chars, uppercase, lowercase, number)
   - Enter the same password in "Confirm Password" field
   - Click "Reset Password" button
   - ✅ **Expected:** Success message appears
   - ✅ **Expected:** Automatic redirect to login page after 3 seconds

5. **Login with New Password**
   - Enter email and new password
   - Click "Login"
   - ✅ **Expected:** Successfully logged in

## Test Scenario 2: Page Refresh Doesn't Invalidate Token

### Steps
1. Request password reset as above
2. Open reset link from email
3. **Refresh the page 3 times** (Press F5 or Ctrl+R)
   - ✅ **Expected:** Page reloads without error each time
   - ✅ **Expected:** No "invalid token" message
4. Enter new password and submit
   - ✅ **Expected:** Password reset succeeds

## Test Scenario 3: Token Can't Be Reused

### Steps
1. Request password reset as above
2. Open reset link from email
3. Successfully reset password
4. Try to use the same reset link again (copy-paste URL)
   - ✅ **Expected:** Error message: "טוקן איפוס לא תקין או פג תוקף" (Invalid or expired token)

## Test Scenario 4: Token Expires After 60 Minutes

### Steps
1. Request password reset
2. Wait 61 minutes (or manipulate database for testing)
3. Try to use reset link
   - ✅ **Expected:** Error message: "טוקן איפוס לא תקין או פג תוקף" (Invalid or expired token)

## Test Scenario 5: Copy Link to Different Browser

### Steps
1. Request password reset
2. Open reset link in Browser A (e.g., Chrome)
3. Copy the URL
4. Open the same URL in Browser B (e.g., Firefox)
   - ✅ **Expected:** Page loads successfully in both browsers
5. Reset password in Browser B
   - ✅ **Expected:** Password reset succeeds
6. Try to reset again in Browser A
   - ✅ **Expected:** Token is already used, error message appears

## Test Scenario 6: Invalid Token in URL

### Steps
1. Navigate to: `https://app.prosaas.co/reset-password?token=invalid_token_123`
   - ✅ **Expected:** Page loads but shows no error yet
2. Enter new password and submit
   - ✅ **Expected:** Error message: "טוקן איפוס לא תקין או פג תוקף" (Invalid or expired token)

## Test Scenario 7: No Token in URL

### Steps
1. Navigate to: `https://app.prosaas.co/reset-password` (no token parameter)
   - ✅ **Expected:** Error message appears immediately: "טוקן איפוס לא תקין או חסר" (Token invalid or missing)

## Test Scenario 8: Password Validation

### Steps
1. Request password reset and open link
2. Try to submit with password that doesn't meet requirements:
   - Password too short (< 8 chars)
     - ✅ **Expected:** Error: "סיסמה חייבת להכיל לפחות 8 תווים"
   - No uppercase letter
     - ✅ **Expected:** Error: "סיסמה חייבת להכיל לפחות אות גדולה אחת באנגלית"
   - No lowercase letter
     - ✅ **Expected:** Error: "סיסמה חייבת להכיל לפחות אות קטנה אחת באנגלית"
   - No number
     - ✅ **Expected:** Error: "סיסמה חייבת להכיל לפחות ספרה אחת"
   - Passwords don't match
     - ✅ **Expected:** Error: "סיסמאות לא תואמות"

## Test Scenario 9: Email Not Found (Security Test)

### Steps
1. Navigate to forgot password page
2. Enter a non-existent email address
3. Click "Send Reset Link"
   - ✅ **Expected:** Same success message as if email existed (security feature)
   - ✅ **Expected:** No email is actually sent
   - ✅ **Expected:** No indication to user whether email exists or not

## Test Scenario 10: All Sessions Logout After Reset

### Steps
1. Login to account on 2 different browsers/devices
2. Request password reset
3. Complete password reset
4. Check the other browser/device sessions
   - ✅ **Expected:** All other sessions are logged out (security feature)
5. Try to make an API call from old session
   - ✅ **Expected:** 401 Unauthorized response

## API Testing (Advanced)

### Test 1: Backend accepts 'password' field
```bash
curl -X POST https://app.prosaas.co/api/auth/reset \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"token":"<valid_token>","password":"NewPass123"}'
```
✅ **Expected:** `{"success": true, "message": "Password updated successfully"}`

### Test 2: Backend accepts 'newPassword' field (backward compatibility)
```bash
curl -X POST https://app.prosaas.co/api/auth/reset \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"token":"<valid_token>","newPassword":"NewPass123"}'
```
✅ **Expected:** `{"success": true, "message": "Password updated successfully"}`

### Test 3: Missing password field
```bash
curl -X POST https://app.prosaas.co/api/auth/reset \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"token":"<valid_token>"}'
```
✅ **Expected:** `{"success": false, "error": "Missing token or password"}`

## Regression Testing

After deploying the fix, verify that:
1. ✅ Login still works normally
2. ✅ User creation still works
3. ✅ Session management still works
4. ✅ Other authentication flows are unaffected

## Success Criteria

✅ All 10 test scenarios pass
✅ No console errors in browser
✅ No server errors in logs
✅ Email delivery works consistently
✅ Password complexity requirements enforced
✅ Security features (no email enumeration, session invalidation) work correctly

## Troubleshooting

### Issue: Email not received
- Check SendGrid API key is configured
- Check SendGrid account status
- Check spam/junk folder
- Check server logs for email sending errors

### Issue: "Invalid token" error immediately
- **Step 1: Check Debug Logs** (NEW)
  - Look for `[AUTH][RESET_DEBUG]` logs in server output
  - **Token Generation Log** (when requesting reset):
    ```
    [AUTH][RESET_DEBUG] token_generated user_id=X token_len=43 token_first8=abc12345 token_last8=xyz98765 hash8=a1b2c3d4
    ```
  - **Token Receipt Log** (when submitting reset form):
    ```
    [AUTH][RESET_DEBUG] got_token=True len=43 first8=abc12345 last8=xyz98765 keys=['token', 'password'] args={}
    ```
  - **Token Validation Log**:
    ```
    [AUTH][RESET_DEBUG] stored_hash8=a1b2c3d4 computed_hash8=a1b2c3d4 used=False exp=2026-01-03 20:16:00
    ```

- **Diagnose Based on Logs**:
  - If `got_token=False`: Frontend not sending token (check browser console, network tab)
  - If `len != 43`: Token is being corrupted/truncated in transit
  - If `first8`/`last8` don't match email link: Token was modified
  - If `stored_hash8 != computed_hash8`: Token encoding issue (should never happen)
  - If `used=True`: Token was already used
  - If `exp` is in the past: Token expired (60 min limit)

- **Other Checks**:
  - Verify token is present in URL
  - Check that token hasn't been used already
  - Verify token hasn't expired (60 min limit)
  - Check database for token status

### Issue: CSRF token error
- Clear browser cookies
- Try in incognito/private mode
- Check CSRF token is being sent in headers

## Notes for QA Team

- Test on multiple browsers (Chrome, Firefox, Safari, Edge)
- Test on mobile devices (iOS Safari, Android Chrome)
- Test with slow network conditions
- Test with browser back/forward buttons
- Verify accessibility (keyboard navigation, screen readers)
