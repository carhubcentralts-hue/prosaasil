# PDF White Box Fix - Manual Testing Guide

## Overview
This guide provides step-by-step instructions for testing the fixes for the PDF viewer "white box" issue and signature field locking.

## Issues Fixed

### 1. White Box Issue (קוביה לבנה)
**Problem**: PDF viewer showed a white box instead of the PDF content when in signature marking mode.

**Root Cause**: Overlay divs didn't have explicit `background: transparent`, allowing default CSS to potentially add a white background.

**Fix**: Added `background: 'transparent'` to all overlay divs in:
- `PDFCanvas.tsx` (overlay wrapper)
- `SignatureFieldMarker.tsx` (signature field overlay)
- `SimplifiedPDFSigning.tsx` (signature preview overlay)

### 2. Signature Field Locking
**Status**: Already correctly implemented, no changes needed.

**How it works**:
- Fields stored with normalized coordinates (0-1 relative to page dimensions)
- Each field has a page number (1-based)
- Fields filtered by current page when rendering
- Screen ↔ PDF coordinate conversion uses `getBoundingClientRect()`

## Pre-Testing Setup

### Prerequisites
1. Access to the contracts page
2. At least one contract with a PDF file uploaded
3. Browser with PDF.js support (Chrome, Firefox, Safari, Edge)
4. For mobile testing: iOS/Android device or browser DevTools device emulation

### Build and Deploy
```bash
cd client
npm install
npm run build
```

## Test Scenarios

### Test 1: PDF Visibility in Signature Marking Mode ⭐ CRITICAL

**Purpose**: Verify PDF is visible and not covered by white box

**Steps**:
1. Navigate to Contracts page (`/contracts`)
2. Click on any contract to open details
3. Click "סמן אזורי חתימה" (Mark Signature Areas) button
4. Observe the PDF viewer

**Expected Results**:
- ✅ PDF displays correctly and is visible
- ✅ No white box covering the PDF
- ✅ PDF content is clear and readable
- ✅ Page navigation buttons are visible
- ✅ Zoom controls work

**If Test Fails**:
- Check browser console for errors
- Verify `background: transparent` is in the style attribute of overlay divs
- Use DevTools to inspect the overlay element and check computed styles

---

### Test 2: Signature Field Creation

**Purpose**: Verify signature fields can be created on PDF

**Steps**:
1. Open signature marking modal (as in Test 1)
2. Click "הפעל מצב סימון" (Enable Marking Mode) button
3. Button should turn green
4. Click anywhere on the PDF

**Expected Results**:
- ✅ Green signature box appears at click location
- ✅ PDF remains visible behind the signature box
- ✅ Box has label "חתימה #1" at the top
- ✅ Box has delete button (X) in top-left corner
- ✅ Field appears in the sidebar list on the right

**If Test Fails**:
- Check if marking mode is active (green button)
- Verify click is inside the PDF area
- Check browser console for JavaScript errors

---

### Test 3: Page Navigation - Single Page Fields ⭐ CRITICAL

**Purpose**: Verify signature fields stay locked to their page

**Steps**:
1. Open signature marking modal with multi-page PDF
2. Enable marking mode
3. Add signature field to page 1
4. Navigate to page 2 (click "עמוד הבא" / Next Page)
5. Observe: Field from page 1 should NOT be visible
6. Add a different signature field to page 2
7. Navigate back to page 1 (click "עמוד קודם" / Previous Page)
8. Observe: Only page 1 field should be visible

**Expected Results**:
- ✅ Page 1 field only visible on page 1
- ✅ Page 2 field only visible on page 2
- ✅ Fields do not "drift" to other pages
- ✅ Fields return to exact same position when returning to their page
- ✅ Sidebar shows all fields (from all pages)

**If Test Fails**:
- This indicates a regression in page filtering logic
- Check `getCurrentPageFields()` function
- Verify `field.page === currentPage` filter is working

---

### Test 4: Zoom Behavior

**Purpose**: Verify signature fields scale correctly with zoom

**Steps**:
1. Open signature marking modal
2. Add signature field to page 1
3. Click zoom in button (+) multiple times
4. Observe field scaling
5. Click zoom out button (-) multiple times
6. Observe field scaling

**Expected Results**:
- ✅ Signature field scales proportionally with PDF
- ✅ Field maintains relative position on page
- ✅ Field maintains aspect ratio
- ✅ PDF and overlay stay synchronized

---

### Test 5: Drag and Resize

**Purpose**: Verify signature fields can be moved and resized

**Steps**:
1. Open signature marking modal
2. Add signature field
3. Click on the field to select it (turns blue)
4. Drag the field to a new position
5. Drag one of the corner handles to resize

**Expected Results**:
- ✅ Field follows cursor smoothly during drag
- ✅ Field stays within page bounds
- ✅ Resize handles appear when field is selected (blue)
- ✅ Field resizes from correct corner
- ✅ Field maintains minimum size (5% width/height)

---

### Test 6: Save and Persistence

**Purpose**: Verify fields are saved correctly

**Steps**:
1. Open signature marking modal
2. Add 2-3 signature fields across different pages
3. Click "שמור" (Save) button
4. Close modal
5. Reopen signature marking modal

**Expected Results**:
- ✅ All fields are restored in exact positions
- ✅ Field count is correct
- ✅ Fields are on correct pages
- ✅ Field numbering is consistent

---

### Test 7: Public Signing View

**Purpose**: Verify signature placement preview in public signing

**Steps**:
1. Create a contract with signature fields (as Business user)
2. Generate public signing link
3. Open public signing link (can use incognito/private browsing)
4. Draw a signature in the signature canvas
5. Observe signature field previews on PDF

**Expected Results**:
- ✅ Purple dashed boxes show where signatures will be placed
- ✅ Boxes are in correct positions
- ✅ Boxes display on correct pages
- ✅ Boxes have correct labels ("חתימה #1", etc.)
- ✅ PDF is visible (not white box)

---

### Test 8: Mobile Touch Interactions

**Purpose**: Verify functionality works on mobile/touch devices

**Steps**:
1. Open signature marking modal on mobile device (or use DevTools device emulation)
2. Enable marking mode
3. Tap on PDF to create signature field
4. Drag field with finger
5. Try to resize using corner handles

**Expected Results**:
- ✅ Tap creates signature field
- ✅ Touch drag moves field smoothly
- ✅ Corner handles are large enough to tap (min 44x44px)
- ✅ PDF remains visible and scrollable
- ✅ Layout is responsive and usable

---

### Test 9: Multiple Fields on Same Page

**Purpose**: Verify multiple fields can coexist on one page

**Steps**:
1. Open signature marking modal
2. Enable marking mode
3. Add 3-4 signature fields to same page
4. Click on different fields to select them

**Expected Results**:
- ✅ All fields are visible simultaneously
- ✅ Fields don't overlap controls
- ✅ Can select individual fields
- ✅ Selected field has blue border, others have green
- ✅ Z-index layering works (selected field on top)

---

### Test 10: Browser Console Verification

**Purpose**: Ensure no JavaScript errors

**Steps**:
1. Open browser DevTools (F12)
2. Go to Console tab
3. Perform all the above tests
4. Monitor console for errors

**Expected Results**:
- ✅ No JavaScript errors
- ✅ No React warnings
- ✅ May see debug logs starting with `[PDF_CANVAS]` or `[SignatureFieldMarker]`
- ✅ No "Failed to load PDF" errors
- ✅ No z-index warnings

---

## Browser Compatibility Testing

Test all scenarios on:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Chrome Mobile (Android)

## Known Acceptable Behaviors

These are expected and not bugs:
1. ResizeObserver warning in console (browser implementation issue, safe to ignore)
2. Debug logs starting with `[PDF_CANVAS]` or `[SignatureFieldMarker]`
3. Slight delay when loading large PDFs
4. Rendering overlay shown briefly when changing pages (intentional)

## Troubleshooting

### Issue: PDF Still Shows White Box

**Debug Steps**:
1. Open DevTools → Elements
2. Find the overlay div (should have `background: transparent` in style)
3. Check computed styles in DevTools
4. Verify no other CSS is overriding the background

**Look for**:
```html
<div class="absolute top-0 left-0" style="... background: transparent; ...">
```

### Issue: Signature Field Appears on Wrong Page

**Debug Steps**:
1. Open DevTools → Console
2. Add a field and check what page number is saved
3. Verify `getCurrentPageFields()` is filtering correctly
4. Check if `field.page === currentPage`

### Issue: Overlay Not Sized Correctly

**Debug Steps**:
1. Check if `canvasRef.current.style.width` has a value
2. Verify canvas is rendered before overlay
3. Ensure overlay div has correct width/height from canvas

## Deployment Verification

After deploying to production:

1. **Smoke Test** (5 minutes):
   - Open contracts page
   - Open signature marking modal
   - Verify PDF is visible
   - Create one signature field
   - Save and verify

2. **Full Regression Test** (30 minutes):
   - Run all 10 test scenarios above
   - Test on at least 2 different browsers

3. **Monitor for 24 hours**:
   - Check error logs for PDF-related errors
   - Monitor user feedback
   - Check analytics for signature field creation success rate

## Success Criteria

✅ All tests pass
✅ No JavaScript errors in console
✅ Works across all major browsers
✅ Mobile interactions are smooth
✅ No user reports of white box or drifting fields

## Rollback Plan

If critical issues are found:

```bash
# Revert the commit
git revert beb3a02

# Rebuild frontend
cd client
npm run build

# Redeploy
```

Note: Rollback is safe - no database changes, no API changes, purely frontend CSS/style fix.

## Support Information

- **Implementation Date**: 2026-01-25
- **Commit**: beb3a02
- **Files Changed**: 
  - `client/src/components/PDFCanvas.tsx`
  - `client/src/components/SignatureFieldMarker.tsx`
  - `client/src/components/SimplifiedPDFSigning.tsx`
- **Changes**: Added `background: 'transparent'` to overlay divs

## Related Documentation

- Implementation Summary: `SIGNATURE_FIELD_LOCKING_IMPLEMENTATION_COMPLETE.md`
- Contract Preview Fix: `CONTRACT_SIGNATURE_PDF_PREVIEW_FIX.md`
- Signature UX Guide: `SIGNATURE_UX_HE.md`
