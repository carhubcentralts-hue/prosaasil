# Signature Field Anchoring - Testing Guide

This document describes how to test the signature field anchoring fix to ensure signature fields are properly anchored to PDF pages with normalized coordinates.

## Background

**Problem Fixed:**
Previously, signature fields were positioned relative to the viewport/container, causing:
- Fields to move when scrolling
- Always saved as page 1 regardless of placement
- Incorrect positioning with zoom changes
- Signatures appearing on wrong pages in final PDF

**Solution:**
Signature fields now use:
- Actual PDF page dimensions from backend
- Normalized coordinates (0-1) relative to page dimensions
- Proper coordinate transformation for display

## Manual Testing Steps

### Test 1: Multi-Page Placement
**Objective:** Verify signature stays anchored to correct page when scrolling

1. Log into the system
2. Navigate to Contracts page
3. Create or open a multi-page PDF contract (at least 2-3 pages)
4. Click "Mark Signature Areas" button
5. Click "Enable Marking Mode"
6. Navigate to **Page 2** using page navigation
7. Click on the PDF to place a signature field
8. Navigate to **Page 3**
9. Navigate back to **Page 2**

**Expected Result:** 
- Signature field appears exactly where you placed it on page 2
- Field does NOT move or appear on other pages
- Field stays in same position when returning to page 2

**Pass/Fail:** ___

### Test 2: Coordinate Accuracy
**Objective:** Verify signature fields use correct coordinates

1. Place a signature field on page 1 at a specific location (e.g., top-right corner)
2. Note the visual position
3. Save the signature fields
4. Close and reopen the signature marking dialog

**Expected Result:**
- Field reappears at EXACT same position
- No drift or offset
- Coordinates are preserved accurately

**Pass/Fail:** ___

### Test 3: Zoom Independence
**Objective:** Verify fields maintain position with browser zoom

1. Place a signature field on any page
2. Use browser zoom (Ctrl/Cmd + Plus/Minus) to change zoom level
3. Observe field position

**Expected Result:**
- Field stays aligned with same PDF content
- No displacement when zooming in/out
- Field dimensions scale appropriately

**Pass/Fail:** ___

### Test 4: Drag and Resize
**Objective:** Verify field manipulation works correctly

1. Place a signature field on any page
2. Drag the field to a different location
3. Use resize handles to change field size
4. Save and reload

**Expected Result:**
- Field moves smoothly during drag
- Resize works correctly
- Position and size are preserved after save/reload

**Pass/Fail:** ___

### Test 5: Final PDF Export
**Objective:** Verify signatures appear on correct pages in final PDF

1. Place signature fields on different pages (e.g., page 1, page 2, page 3)
2. Save signature field locations
3. Send contract for signing or sign it
4. Draw a signature
5. Complete the signing process
6. Download the signed PDF
7. Open signed PDF and check each page

**Expected Result:**
- Signature appears on ALL marked pages
- Signatures are on the CORRECT pages (not all on page 1)
- Signatures are positioned correctly within each page

**Pass/Fail:** ___

### Test 6: Browser Compatibility
**Objective:** Verify functionality across browsers

Repeat Tests 1-4 in:
- [ ] Chrome/Chromium
- [ ] Firefox
- [ ] Safari (if available)
- [ ] Edge

**Expected Result:**
- All tests pass in all browsers
- No browser-specific issues

## Technical Verification

### Verify Backend Data Format

Check that signature fields are stored with correct format in database:

```sql
SELECT id, page, x, y, w, h FROM contract_signature_fields WHERE contract_id = <test_contract_id>;
```

**Expected:**
- `page`: Integer (1-based), e.g., 1, 2, 3
- `x, y, w, h`: Decimal numbers between 0 and 1 (normalized)
- Example: `page=2, x=0.5, y=0.3, w=0.15, h=0.05`

### Verify PDF Info Endpoint

Test that PDF info endpoint returns page dimensions:

```bash
curl -X GET http://localhost:5000/api/contracts/<contract_id>/pdf-info \
  -H "Cookie: session=..." \
  --cookie-jar cookies.txt
```

**Expected Response:**
```json
{
  "contract_id": 123,
  "filename": "contract.pdf",
  "page_count": 3,
  "pages": [
    {"page_number": 0, "width": 612.0, "height": 792.0},
    {"page_number": 1, "width": 612.0, "height": 792.0},
    {"page_number": 2, "width": 612.0, "height": 792.0}
  ]
}
```

### Check Browser Console

Open browser DevTools and check console for debug logs:

**Expected logs during field placement:**
```
[SignatureFieldMarker] Click at {clickX: 250, clickY: 300, iframeWidth: 800, iframeHeight: 1000, pdfPageWidth: 612, pdfPageHeight: 792}
[SignatureFieldMarker] Normalized coords: {relX: 0.254, relY: 0.237}
[SignatureFieldMarker] Created field: {id: "...", page: 2, x: 0.229, y: 0.205, w: 0.245, h: 0.063, ...}
```

## Acceptance Criteria

✅ **All tests must pass** for the feature to be considered complete:

- [ ] Test 1: Multi-Page Placement - PASS
- [ ] Test 2: Coordinate Accuracy - PASS
- [ ] Test 3: Zoom Independence - PASS
- [ ] Test 4: Drag and Resize - PASS
- [ ] Test 5: Final PDF Export - PASS
- [ ] Test 6: Browser Compatibility - PASS (all browsers)

## Troubleshooting

### Issue: Fields appear offset from expected position

**Possible Cause:** Browser zoom or display scaling
**Solution:** 
- Reset browser zoom to 100%
- Check if `window.devicePixelRatio` is > 1
- Verify iframe dimensions match expectations

### Issue: Fields move when scrolling

**Possible Cause:** Overlay positioning issue
**Solution:**
- Check that overlay is positioned absolutely at left: 16px, top: 16px (matching iframe padding)
- Verify `iframeLoaded` state is true before rendering
- Check console for errors

### Issue: Wrong page number saved

**Possible Cause:** Page index conversion error
**Solution:**
- Verify `currentPage` is 1-based (UI shows "Page 1, 2, 3...")
- Check that `pageIndex = currentPage - 1` for 0-based array access
- Verify `field.page` is set to `currentPage` (1-based) not `pageIndex`

## Code Review Checklist

- [ ] `handleOverlayClick` uses `pdfPageDimensions[pageIndex]` for calculations
- [ ] Display scale calculated as: `displayScale = iframeWidth / pdfPageWidth`
- [ ] Click coords converted: pixel → PDF points → normalized (0-1)
- [ ] `renderSignatureFields` converts normalized → display pixels
- [ ] Fields positioned using absolute pixels, not percentages
- [ ] Overlay positioned to exactly match iframe bounds
- [ ] `iframeLoaded` state prevents premature rendering
- [ ] Drag/resize handlers use same coordinate transformations

## Performance Notes

The changes add minimal overhead:
- One-time fetch of PDF info (page dimensions) on component mount
- Simple arithmetic operations for coordinate transformations
- No continuous polling or expensive calculations
- Iframe load state prevents unnecessary re-renders

## Related Files

- `client/src/components/SignatureFieldMarker.tsx` - Main component with fixes
- `server/routes_contracts.py` - Backend endpoints
- `server/services/pdf_signing_service.py` - PDF manipulation service

## Additional Documentation

See also:
- `CONTRACT_SIGNATURE_PDF_OVERLAY_FIX.md` - Previous overlay fix documentation
- `PDF_SIGNATURE_PLACEMENT_COMPLETE.md` - Overall signature feature documentation
