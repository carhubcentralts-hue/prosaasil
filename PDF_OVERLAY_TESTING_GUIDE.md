# PDF Signature Overlay - Visual Testing Guide

## Overview
This guide helps verify that the PDF signature overlay fix is working correctly. The overlay should be transparent with only borders visible, never hiding the PDF content.

## Test Environment Setup

### Prerequisites
1. Access to the ProSaaSil application
2. Contract with PDF document
3. Modern web browser (Chrome, Firefox, Safari, or Edge)
4. Browser DevTools knowledge (F12)

### Test Data Needed
- One or more contracts with PDF documents
- Public signing token (optional, for public signing page tests)

## Test Scenarios

### 🧪 Test 1: Signature Area Marking - Initial Load

**Steps:**
1. Navigate to Contracts page
2. Open a contract with a PDF
3. Click "Mark Signature Areas" button
4. Wait for the marking screen to load

**Expected Results:**
- ✅ PDF displays fully without white overlays
- ✅ PDF content is clearly visible
- ✅ No loading spinner stuck on screen
- ✅ "Enable Marking Mode" button visible

**DevTools Verification:**
1. Open DevTools (F12) → Elements tab
2. Find the overlay div (search for "inset-0" class)
3. Check Computed styles:
   - `background-color`: Should be `rgba(0, 0, 0, 0)` or `transparent`
   - `z-index`: Should be `2`
   - `pointer-events`: Should be `none` (when marking mode is off)

**Screenshot Points:**
- [ ] Full marking screen showing PDF clearly
- [ ] DevTools showing overlay styles

---

### 🧪 Test 2: Marking Mode Toggle

**Steps:**
1. From marking screen, click "Enable Marking Mode" button
2. Observe the cursor change
3. Click "Disable Marking Mode" (toggle off)
4. Try to scroll/zoom the PDF

**Expected Results:**
- ✅ When enabled: Cursor changes to crosshair
- ✅ When enabled: Can click on PDF to create signature fields
- ✅ When disabled: Can scroll/zoom PDF normally
- ✅ PDF always remains visible

**DevTools Verification (Marking Mode ON):**
- `pointer-events`: Should be `auto` on overlay
- PDF still fully visible beneath

**DevTools Verification (Marking Mode OFF):**
- `pointer-events`: Should be `none` on overlay
- Can interact with PDF directly

**Screenshot Points:**
- [ ] Marking mode enabled (crosshair cursor visible)
- [ ] Marking mode disabled (normal cursor, can scroll)

---

### 🧪 Test 3: Creating Signature Fields

**Steps:**
1. Enable marking mode
2. Click on PDF to create first signature field
3. Create 2-3 more signature fields on same page
4. Create signature field on different page (if multi-page)

**Expected Results:**
- ✅ Green bordered box appears at click location
- ✅ PDF content visible inside signature box
- ✅ Signature box has semi-transparent background (20% opacity)
- ✅ Border is visible but not opaque
- ✅ Label "חתימה #1" appears above box

**Color Expectations:**
- Normal field: Green border with very light green background
- Selected field: Blue border with very light blue background
- Background should NOT hide PDF text/content

**Screenshot Points:**
- [ ] Multiple signature fields on PDF
- [ ] Close-up showing transparency (PDF text visible through field)
- [ ] DevTools showing field backgroundColor: `rgba(34, 197, 94, 0.2)`

---

### 🧪 Test 4: Dragging and Resizing

**Steps:**
1. Create a signature field
2. Click and drag the field to a new position
3. Click and drag corner handle to resize
4. Observe PDF visibility during drag/resize

**Expected Results:**
- ✅ Field moves smoothly
- ✅ Field resizes smoothly
- ✅ PDF remains visible at all times
- ✅ No white boxes or opaque overlays during interaction
- ✅ No jumping or flickering

**Screenshot Points:**
- [ ] During drag operation (field in motion)
- [ ] During resize operation (corner handle visible)

---

### 🧪 Test 5: Multi-Page Navigation

**Steps:**
1. Create signature field on page 1
2. Navigate to page 2 using arrow buttons
3. Create signature field on page 2
4. Navigate back to page 1

**Expected Results:**
- ✅ Page changes smoothly
- ✅ Signature fields appear only on their designated page
- ✅ PDF renders correctly on each page
- ✅ No stuck overlays between page changes

**Screenshot Points:**
- [ ] Page 1 with signature field
- [ ] Page 2 with different signature field

---

### 🧪 Test 6: Zoom and Scale

**Steps:**
1. Create signature fields
2. Use zoom controls (if visible) or browser zoom
3. Observe signature field positioning
4. Try dragging/resizing at different zoom levels

**Expected Results:**
- ✅ Signature fields scale with PDF
- ✅ Positions remain accurate relative to PDF content
- ✅ Transparency maintained at all zoom levels
- ✅ No layout breaks or overflow

---

### 🧪 Test 7: Public Signing Page

**Steps:**
1. Access public signing page with token
2. View PDF with pre-marked signature fields
3. Draw signature in signature pad
4. Observe preview fields on PDF

**Expected Results:**
- ✅ Purple dashed border preview fields visible
- ✅ PDF content visible through preview fields
- ✅ Background opacity very low (8%)
- ✅ Preview fields show where signature will be placed
- ✅ Fields are read-only (pointer-events: none)

**DevTools Verification:**
- Preview field `backgroundColor`: `rgba(168, 85, 247, 0.08)`
- `pointer-events`: `none`

**Screenshot Points:**
- [ ] Public signing page with preview fields
- [ ] Close-up of preview field showing transparency

---

### 🧪 Test 8: Save and Reload

**Steps:**
1. Create multiple signature fields
2. Click "Save" button
3. Close marking screen
4. Re-open marking screen
5. Verify fields are in correct positions

**Expected Results:**
- ✅ Fields saved correctly
- ✅ Fields reload in exact same positions
- ✅ Coordinates accurate (percentage-based)
- ✅ PDF still fully visible

---

### 🧪 Test 9: Mobile/Responsive View

**Steps:**
1. Resize browser window to mobile size (or use DevTools device mode)
2. Test all previous scenarios on mobile view
3. Use touch events if on actual mobile device

**Expected Results:**
- ✅ Layout adapts to smaller screen
- ✅ Touch interactions work correctly
- ✅ PDF and overlays scale properly
- ✅ No white boxes or hidden content

---

### 🧪 Test 10: Browser Compatibility

**Test on each browser:**
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari (if available)
- [ ] Mobile Safari (if available)
- [ ] Mobile Chrome (if available)

**Expected Results:**
- ✅ Consistent behavior across all browsers
- ✅ Z-index layering works correctly
- ✅ Transparency renders correctly
- ✅ Pointer-events work as expected

---

## DevTools Deep Inspection

### For Main Overlay Container

**Find element with classes:** `absolute inset-0 cursor-crosshair` (or `cursor-default`)

**Check these computed values:**
```
position: absolute ✓
top: 0px ✓
left: 0px ✓
right: 0px ✓
bottom: 0px ✓
z-index: 2 ✓
background-color: rgba(0, 0, 0, 0) or transparent ✓
pointer-events: none (when marking mode off) or auto (when on) ✓
```

### For Individual Signature Fields

**Find element with classes:** `absolute border-3 bg-opacity-40`

**Check these computed values:**
```
position: absolute ✓
z-index: 5 (normal) or 10 (selected) ✓
background-color: rgba(34, 197, 94, 0.2) or rgba(59, 130, 246, 0.2) ✓
border-width: 3px ✓
pointer-events: auto ✓
```

### For PDF Canvas

**Find element:** `<canvas>` element

**Check these computed values:**
```
position: relative ✓
z-index: 1 ✓
display: block ✓
```

---

## Common Issues and Solutions

### ❌ Issue: White box covering PDF

**Symptoms:**
- Opaque white overlay blocks PDF content
- Cannot see PDF text/images

**Root Cause:**
- Background color set to opaque value
- Z-index inverted (overlay below canvas)

**Verification:**
- Check overlay `background-color` in DevTools
- Should be `transparent` or `rgba(0, 0, 0, 0)`
- Check z-index: canvas (1), overlay (2)

**Fix Applied:** ✅ This fix ensures transparent backgrounds

---

### ❌ Issue: Cannot interact with PDF

**Symptoms:**
- Cannot scroll PDF
- Cannot zoom PDF
- Clicks do nothing

**Root Cause:**
- Overlay has `pointer-events: auto` when should be `none`

**Verification:**
- Check overlay `pointer-events` when marking mode is OFF
- Should be `none`

**Fix Applied:** ✅ Conditional pointer-events based on marking mode

---

### ❌ Issue: Signature fields jump when dragging

**Symptoms:**
- Fields snap to wrong positions
- Coordinates inaccurate

**Root Cause:**
- Coordinate calculations using pixels instead of percentages
- Overlay dimensions not matching PDF viewport

**Verification:**
- Check field coordinates are 0-1 range
- Check overlay dimensions match canvas display size

**Fix Applied:** ✅ Already using percentage-based coordinates

---

### ❌ Issue: Fields disappear at different zoom levels

**Symptoms:**
- Fields visible at 100% but not at other zooms
- Overlay size doesn't match PDF

**Root Cause:**
- Overlay using fixed dimensions instead of matching canvas

**Verification:**
- Overlay width/height should equal canvas CSS size (not internal size)

**Fix Applied:** ✅ Overlay dimensions set from canvas.style.width/height

---

## Test Report Template

```markdown
# PDF Overlay Fix - Test Report

**Tester:** [Your Name]
**Date:** [Date]
**Browser:** [Chrome/Firefox/Safari/etc.]
**Version:** [Browser Version]

## Test Results Summary

| Test | Status | Notes |
|------|--------|-------|
| Initial Load | ✅ / ❌ | |
| Marking Mode Toggle | ✅ / ❌ | |
| Creating Fields | ✅ / ❌ | |
| Dragging/Resizing | ✅ / ❌ | |
| Multi-Page | ✅ / ❌ | |
| Zoom/Scale | ✅ / ❌ | |
| Public Signing | ✅ / ❌ | |
| Save/Reload | ✅ / ❌ | |
| Mobile/Responsive | ✅ / ❌ | |
| Browser Compat | ✅ / ❌ | |

## Issues Found

[List any issues]

## Screenshots

[Attach screenshots]

## Overall Assessment

- [ ] All tests passed
- [ ] Minor issues (non-blocking)
- [ ] Major issues (blocking)

## Additional Comments

[Any other observations]
```

---

## Acceptance Criteria Verification

✅ **Before considering this fix complete, verify:**

1. **PDF Visibility**
   - [ ] PDF content always visible
   - [ ] No white boxes or opaque overlays
   - [ ] Text and images readable through signature fields

2. **Transparency**
   - [ ] Overlay has transparent background
   - [ ] Signature fields have semi-transparent (20%) backgrounds
   - [ ] Border visible but not blocking content

3. **Interaction**
   - [ ] Can scroll/zoom PDF when marking mode off
   - [ ] Can create fields when marking mode on
   - [ ] Can drag/resize fields at any time

4. **Accuracy**
   - [ ] Signature fields stay in correct positions
   - [ ] Coordinates accurate across zoom levels
   - [ ] Fields persist after save/reload

5. **Stability**
   - [ ] No jumping or flickering
   - [ ] No stuck loading overlays
   - [ ] Smooth page navigation

---

## Security Verification

✅ **Security checks passed:**
- [x] CodeQL analysis: 0 alerts
- [x] No new dependencies
- [x] No authentication changes
- [x] No data storage changes
- [x] Only CSS/styling modifications

---

## Contact

If you find any issues during testing, please report with:
1. Description of issue
2. Steps to reproduce
3. Screenshots/video
4. Browser and version
5. Any error messages from console

---

**Test Status:** 🟡 Pending Manual Verification
**Fix Applied:** ✅ Complete
**Code Review:** ✅ Passed
**Security Scan:** ✅ Passed (0 alerts)
