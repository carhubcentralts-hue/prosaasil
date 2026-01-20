# Contract Page Navigation Test Plan

## Manual Testing Steps

### Setup
1. Create a test contract with a multi-page PDF (at least 4 pages)
2. Send the contract for signature
3. Open the public signing link

### Test 1: Page Navigation
1. ✅ Verify you start on page 1 (עמוד 1 מתוך X)
2. ✅ Click the left arrow (←) to go to page 2
3. ✅ Verify the page indicator shows "עמוד 2 מתוך X"
4. ✅ Verify the PDF content actually changes to page 2
5. ✅ Check browser console - should see log: `[PDF_NAV] Navigating from page 1 to page 2`
6. ✅ Navigate to page 3 and verify
7. ✅ Navigate to page 4 and verify
8. ✅ Navigate back to page 2 and verify

### Test 2: Signature Placement on Different Pages
1. ✅ Navigate to page 1
2. ✅ Click "הוסף חתימה" button
3. ✅ Double-click on the PDF to place a signature
4. ✅ Draw a signature and confirm
5. ✅ Verify signature list shows "עמוד 1"
6. ✅ Check console - should see: `[PDF_SIGN] Adding signature on page 1 (0-indexed: 0)`

7. ✅ Navigate to page 2 using arrows
8. ✅ Verify PDF actually changes to page 2
9. ✅ Double-click to place another signature
10. ✅ Draw and confirm
11. ✅ Verify signature list shows "עמוד 2"
12. ✅ Check console - should see: `[PDF_SIGN] Adding signature on page 2 (0-indexed: 1)`

13. ✅ Navigate to page 4
14. ✅ Verify PDF shows page 4
15. ✅ Place another signature
16. ✅ Verify signature list shows "עמוד 4"
17. ✅ Check console - should see: `[PDF_SIGN] Adding signature on page 4 (0-indexed: 3)`

### Test 3: Submit and Verify
1. ✅ Click "אשר X חתימות וחתום על המסמך"
2. ✅ Check console - should see submission log with all signatures and their page numbers
3. ✅ Wait for success message
4. ✅ Download the signed PDF
5. ✅ Open the PDF and verify:
   - Signature appears on page 1
   - Signature appears on page 2
   - Signature appears on page 4
   - NO signatures appear on wrong pages

### Test 4: Mobile/Touch Navigation
1. ✅ Open signing page on mobile device or use browser dev tools (device mode)
2. ✅ Test touch navigation with arrows
3. ✅ Verify page changes work correctly
4. ✅ Test double-tap signature placement
5. ✅ Verify signatures are placed on correct pages

## Expected Results
- ✅ Page navigation arrows work smoothly and reliably
- ✅ PDF content actually changes when navigating between pages
- ✅ Current page indicator accurately reflects the displayed page
- ✅ Signatures are placed on the correct pages (as seen by the user)
- ✅ Final signed PDF has signatures on the correct pages
- ✅ Console logs show correct page numbers (both display and 0-indexed)

## Bug Fix Verification
**Before Fix:**
- Page navigation didn't work - arrows clicked but PDF stayed on page 1
- All signatures ended up on page 1 because user thought they were navigating but PDF wasn't actually changing

**After Fix:**
- Iframe is forced to reload with `key={pdf-page-${currentPage}}` prop
- PDF actually navigates to selected page
- Signatures are correctly associated with the page the user sees
- Enhanced visual feedback makes it clear which page is active
