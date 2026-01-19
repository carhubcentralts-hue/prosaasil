# Testing Guide: WhatsApp Templates & Contract Fixes

## Overview
This guide covers testing for three main fixes:
1. WhatsApp Templates Loading (404 Error Fix)
2. Contract File Upload from Lead Page
3. Contract Signing Page UI Improvements

## Prerequisites
- Access to the application with admin/agent role
- Test lead with phone number and email
- Sample PDF/DOC files for contract testing

---

## Test 1: WhatsApp Templates Loading

### Issue Fixed
- Frontend was calling wrong endpoint `/api/whatsapp/templates/manual`
- Backend endpoint is actually `/api/whatsapp/manual-templates`

### Testing Steps
1. Navigate to Lead Detail page
2. Click on "WhatsApp" tab
3. Find and click "שליחה מתבנית" (Send from Template) tab
4. **Expected Result**: Templates load successfully without 404 error
5. **Expected Result**: List of WhatsApp manual templates is displayed
6. **Failure Signs**: 
   - 404 error in console
   - "שגיאה בטעינת התבניות" error message
   - Empty template list with error

### Code Changes
- **File**: `client/src/pages/Leads/LeadDetailPage.tsx`
- **Line**: 3943
- **Change**: `/api/whatsapp/templates/manual` → `/api/whatsapp/manual-templates`

---

## Test 2: Contract File Upload from Lead Page

### Issue Fixed
- Backend only accepted JSON for contract creation
- Lead page sends FormData with multiple files
- Backend now handles both JSON and FormData with multiple file uploads

### Testing Steps

#### Test 2A: Create Contract WITHOUT Files
1. Navigate to Lead Detail page
2. Click on "חוזים" (Contracts) tab
3. Click "חוזה חדש" (New Contract) button
4. Fill in:
   - Contract title: "חוזה בדיקה 1"
   - Contract type: "מכר" (Sale)
   - **DO NOT** upload any files
5. Click "צור חוזה" (Create Contract)
6. **Expected Result**: Contract created successfully
7. **Expected Result**: Success message with contract number displayed
8. **Expected Result**: Contract appears in the list

#### Test 2B: Create Contract WITH Single File
1. Navigate to Lead Detail page
2. Click on "חוזים" (Contracts) tab
3. Click "חוזה חדש" (New Contract) button
4. Fill in:
   - Contract title: "חוזה בדיקה 2"
   - Contract type: "שכירות" (Rent)
5. Click on file upload area
6. Select a PDF file
7. **Expected Result**: File appears in the list below upload area
8. Click "צור חוזה" (Create Contract)
9. **Expected Result**: Contract created successfully with file attached
10. **Expected Result**: Success message displayed
11. **Expected Result**: Contract appears in list with file count

#### Test 2C: Create Contract WITH Multiple Files
1. Navigate to Lead Detail page
2. Click on "חוזים" (Contracts) tab
3. Click "חוזה חדש" (New Contract) button
4. Fill in:
   - Contract title: "חוזה בדיקה 3"
   - Contract type: "תיווך" (Mediation)
5. Click on file upload area
6. Select multiple PDF/DOC files (2-3 files)
7. **Expected Result**: All files appear in the list
8. Click "צור חוזה" (Create Contract)
9. **Expected Result**: Contract created successfully with all files attached
10. **Expected Result**: Success message displayed
11. **Expected Result**: Contract appears in list with correct file count

#### Test 2D: Compare with Contracts Page Creation
1. Navigate to Contracts page (not from lead)
2. Create a new contract with files
3. **Expected Result**: Should work the same way as lead page
4. **Expected Result**: Both methods should produce identical results

### Code Changes
- **File**: `server/routes_contracts.py`
- **Function**: `create_contract()`
- **Changes**: 
  - Added FormData support alongside JSON
  - Added multiple file upload support
  - Files are attached using 'files' field name
  - Returns success status with file information

---

## Test 3: Contract Signing Page UI Improvements

### Issue Fixed
- Enhanced UI with better preview
- Added digital signature canvas
- Improved overall user experience

### Testing Steps

#### Test 3A: Access Signing Page
1. Create a contract with files (from Test 2)
2. Get the signing token/link
3. Open the signing page in browser
4. **Expected Result**: Page loads with modern, clean UI
5. **Expected Result**: Contract title and signer info displayed
6. **Expected Result**: Gradient background (blue-to-indigo)

#### Test 3B: Preview Contract Files
1. On signing page, locate the "מסמכים לעיון" (Documents) section
2. For each PDF file, click "תצוגה מקדימה" (Preview) button
3. **Expected Result**: PDF displays in embedded iframe (600px height)
4. **Expected Result**: Can scroll through PDF pages
5. Click "סגור תצוגה" (Close Preview) to close
6. Click "הורד" (Download) button
7. **Expected Result**: File downloads successfully

#### Test 3C: Digital Signature
1. On signing page, click "חתימה דיגיטלית" (Digital Signature) tab
2. **Expected Result**: Canvas displays with white background
3. **Expected Result**: "שם מלא" (Full Name) input field is visible
4. Enter name in the text field
5. Draw signature on canvas using mouse/touch
6. **Expected Result**: Black lines appear as you draw
7. Click "נקה" (Clear) button
8. **Expected Result**: Canvas clears completely
9. Draw signature again
10. Click "אשר וחתום דיגיטלית" (Confirm and Sign Digitally)
11. **Expected Result**: Signature submits successfully
12. **Expected Result**: Success page displays with:
    - Green checkmark icon
    - Success message with signer name
    - Signed contract preview (if available)
    - Download button for signed document
    - Print button

#### Test 3D: Upload Signed Document
1. On signing page, click "העלאת מסמך חתום" (Upload Signed Document) tab
2. Click "בחר קובץ" (Choose File) button
3. Select a PDF file
4. **Expected Result**: File name and size display
5. Click "אשר וחתום" (Confirm and Sign)
6. **Expected Result**: File uploads successfully
7. **Expected Result**: Success page displays

#### Test 3E: Canvas Initialization
1. Open signing page
2. Click on "חתימה דיגיטלית" (Digital Signature) tab
3. **Expected Result**: Canvas has white background (not transparent)
4. Switch to "העלאת מסמך חתום" tab
5. Switch back to "חתימה דיגיטלית" tab
6. **Expected Result**: Canvas reinitializes with white background

### Code Changes
- **File**: `client/src/pages/contracts/PublicSigningPage.tsx`
- **Changes**:
  - Added canvas initialization useEffect
  - Canvas fills with white background when tab opens
  - Better visual consistency

---

## Verification Checklist

### WhatsApp Templates
- [ ] Templates load without 404 error
- [ ] Template list displays correctly
- [ ] Can select and use templates

### Contract Creation (Lead Page)
- [ ] Can create contract without files
- [ ] Can create contract with single file
- [ ] Can create contract with multiple files
- [ ] Files display in contract details after creation
- [ ] Works identically to contracts page creation

### Contract Signing Page
- [ ] Page loads with good UI
- [ ] PDF preview works for all files
- [ ] Digital signature canvas works
- [ ] Canvas has white background
- [ ] Clear signature works
- [ ] Can draw smooth signatures
- [ ] Digital signing submits successfully
- [ ] Upload signed document works
- [ ] Success page displays correctly
- [ ] Can download signed contract
- [ ] Can print signed contract

---

## Browser Testing
Test in multiple browsers:
- [ ] Chrome/Edge (Desktop)
- [ ] Firefox (Desktop)
- [ ] Safari (Desktop)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

---

## Rollback Instructions
If any issues are found:

```bash
git checkout <previous-commit-hash>
```

The previous commit hashes:
- Before all fixes: `78aef8c`
- Before canvas init: `1c41c67`
- Current: `0a99ea7`

---

## Contact
For issues or questions about these fixes, refer to the problem statement in PR.
