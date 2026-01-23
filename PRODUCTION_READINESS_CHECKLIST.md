# Production Readiness Checklist for Receipt Processing System

## ⚠️ Current Status: ARCHITECTURE COMPLETE, TEST COVERAGE INSUFFICIENT

This checklist defines the **mandatory requirements** before the receipt processing system can be considered production-ready.

---

## 📋 Definition of Done

### 1. Test Coverage Requirements (HARD REQUIREMENTS)

**Minimum Fixture Count: 20 fixtures**

Must include:
- ✅ **Stripe (4 variants minimum)**:
  - [ ] Payment receipt (simple)
  - [ ] Invoice (itemized)
  - [ ] Subscription billing
  - [ ] Hosted invoice page

- ✅ **AliExpress (2 variants minimum)**:
  - [ ] Order confirmation
  - [ ] Refund notice

- ✅ **Additional Vendors (10 minimum)**:
  - [ ] PayPal
  - [ ] Apple (App Store/Apple Pay)
  - [ ] Google (Play Store/Google Workspace)
  - [ ] AWS
  - [ ] Meta (Facebook Ads)
  - [ ] Replit
  - [ ] GitHub
  - [ ] DigitalOcean
  - [ ] Netlify
  - [ ] Vercel

- ✅ **Complex Scenarios (4 minimum)**:
  - [ ] HTML with sticky header (large top section)
  - [ ] HTML with cookie banner/modal
  - [ ] HTML with lazy-loaded images
  - [ ] PDF scanned (image inside PDF)
  - [ ] PDF textual (searchable text)

**Current Progress: 3/20 fixtures (15%)**

---

### 2. Quality Gates (MEASURABLE THRESHOLDS)

Tests must demonstrate:

#### Preview Generation Quality
- **≥95% valid previews** (not blank, not logo-only)
  - Current: Unknown (need artifacts to measure)
  - Target: 19/20 fixtures generate valid preview images

#### Data Extraction Accuracy
- **≥90% extraction success** (all required fields extracted)
  - Current: Unknown (only 3 fixtures tested)
  - Target: 18/20 fixtures extract amount/vendor/currency/date

#### Amount Accuracy
- **≥95% amount accuracy** (for fixtures with clear amounts)
  - Current: 3/3 (100%) but sample too small
  - Target: Maintain 95%+ across all 20 fixtures

#### Error Handling
- **100% of failures have specific error codes**
  - Current: Generic errors only
  - Required error codes:
    - `LOGO_ONLY` - Preview contains only logo
    - `BLANK` - Preview is blank/white
    - `OCR_FAIL` - Could not detect text in image
    - `PARSE_FAIL` - Could not parse amount/date
    - `RENDER_TIMEOUT` - Playwright timeout during render
    - `NETWORK_ERROR` - Failed to load external resources
    - `MISSING_AMOUNT` - No amount found
    - `MISSING_VENDOR` - No vendor identified
    - `INVALID_FORMAT` - Unexpected email/PDF format

---

### 3. Artifacts (MANDATORY FOR VALIDATION)

**Every test run MUST generate artifacts to:**
- `server/tests/artifacts/{fixture_name}/`

Required artifacts per fixture:
1. **`full.png`** - Full page screenshot before cropping
2. **`cropped.png`** - Final cropped preview image
3. **`extraction.json`** - Extracted data with confidence scores
4. **`metadata.json`** - Test run metadata (timestamp, versions, duration)

If preview fails:
5. **`failure.png`** - Screenshot at point of failure
6. **`failure_reason.txt`** - Detailed failure reason with error code

Optional but recommended:
7. **`ocr.json`** - OCR results if text detection performed
8. **`debug.log`** - Detailed execution log

**Why artifacts are mandatory:**
- Visual validation - see what the system actually generated
- Debugging - understand why tests fail
- Regression detection - compare artifacts across commits
- Quality verification - manually review 20 generated images

**Current Status: NO ARTIFACTS - Cannot validate quality**

---

### 4. Enhanced Playwright Requirements

The screenshot generation must prove it handles real-world complexity:

#### Network & Loading
- [x] `wait_for_load_state('networkidle')` - Already implemented
- [ ] `wait_for_fonts()` - Ensure fonts loaded
- [ ] Wait for external images (detect <img> tags)
- [ ] Handle lazy-loaded content (scroll + wait)

#### Content Detection
- [x] Wait for content indicators - Already implemented
- [ ] Detect and close cookie banners/modals
- [ ] Scroll to trigger lazy-load
- [ ] Wait for dynamic content (spinners disappear)

#### Cropping Strategy
- [x] Basic main content detection - Already implemented
- [ ] **Content bounding box** - Crop to actual content area
- [ ] Verify important text not cut off (amount, total, paid)
- [ ] Minimum content height validation (>300px)

#### Failure Handling
- [ ] Save screenshot on timeout
- [ ] Log network failures
- [ ] Detect and report blocked resources
- [ ] Graceful degradation if elements missing

**Current Status: Basic waiting implemented, advanced detection missing**

---

### 5. Preview Validation (STRONG CHECKS)

Beyond "not blank" - prove preview is useful:

#### Text Detection
- [ ] OCR-based text detection in preview image
- [ ] Minimum text lines detected (>10 lines)
- [ ] Key terms present ("total", "amount", "paid", currency symbol)

#### Content Area Validation
- [ ] Preview contains >20% non-white pixels
- [ ] Center region (50% of image) has text content
- [ ] Not just logo/header (detect repetitive patterns)

#### Cropping Quality
- [ ] Amount text visible in preview
- [ ] Date text visible in preview
- [ ] Vendor name visible in preview
- [ ] No critical content cut off at edges

**Current Status: Only white pixel percentage check - INSUFFICIENT**

---

### 6. Storage & Database Validation

Prove the full pipeline works:

#### Storage Validation
- [ ] PNG/JPG actually created (valid image format)
- [ ] Image saved to mocked storage
- [ ] Storage key returned correctly
- [ ] Image retrievable from storage

#### Database Validation
- [ ] `preview_image_key` updated in database
- [ ] `preview_source` set correctly
- [ ] `extraction_status` reflects actual result
- [ ] `extraction_error` contains error code if failed

#### API Contract
- [ ] UI can fetch preview via API
- [ ] Preview URL works (even with mocked storage)
- [ ] Metadata matches database record

**Current Status: Mocked but not fully validated**

---

### 7. Error Code Implementation

Every failure must have a specific, actionable error code:

#### Required Error Codes
```python
class ExtractionErrorCode(Enum):
    LOGO_ONLY = "preview_logo_only"
    BLANK = "preview_blank"
    OCR_FAIL = "ocr_failed"
    PARSE_FAIL = "parse_failed"
    RENDER_TIMEOUT = "render_timeout"
    NETWORK_ERROR = "network_error"
    MISSING_AMOUNT = "missing_amount"
    MISSING_VENDOR = "missing_vendor"
    MISSING_CURRENCY = "missing_currency"
    INVALID_FORMAT = "invalid_format"
    PLAYWRIGHT_ERROR = "playwright_error"
```

#### UI Display
- [ ] Error code shown in receipts list
- [ ] User-friendly message mapped from error code
- [ ] Suggested action for each error type
- [ ] Link to documentation for error codes

**Current Status: Generic error messages only - INSUFFICIENT**

---

## 🎯 Summary: What Blocks Production Deployment

### BLOCKERS (Must Fix):
1. ❌ **Only 3/20 fixtures** - Need 17 more covering diverse vendors and scenarios
2. ❌ **No artifacts saved** - Cannot validate quality without visual inspection
3. ❌ **No quality gates measured** - Don't know actual success rates
4. ❌ **No error codes** - Failures are not actionable
5. ❌ **Weak preview validation** - "Not blank" is insufficient

### WORKING (Keep):
1. ✅ Test infrastructure - Framework is solid and expandable
2. ✅ Progress bars - Work correctly with localStorage
3. ✅ Cancel functionality - Graceful shutdown works
4. ✅ Worker stability - No crashes, proper batching
5. ✅ Architecture - No duplicates, clean separation

---

## 📝 Action Items (Priority Order)

### Immediate (Before Production):
1. **Collect 17 more real receipt fixtures** from actual emails
2. **Implement artifact generation** - Save images and metadata
3. **Add error codes** to all failure paths
4. **Enhance preview validation** - OCR text detection
5. **Run tests and measure quality gates** - Get actual percentages

### Important (Before Scaling):
6. **Enhanced Playwright** - Fonts, lazy-load, cookie banners
7. **Content bounding box cropping** - Better crop strategy
8. **UI error code display** - Show specific errors to users
9. **Documentation** - Error code meanings and solutions

### Nice to Have (Continuous Improvement):
10. **Performance benchmarks** - Processing time per receipt
11. **Stress testing** - 100+ receipts in one batch
12. **Multi-language** - Hebrew, Arabic, Chinese receipts
13. **Receipt variations** - Split payments, refunds, credits

---

## 🚫 DON'T CLAIM "PRODUCTION READY" UNTIL:

- ✅ 20+ fixtures covering diverse scenarios
- ✅ Artifacts generated and manually reviewed
- ✅ Quality gates measured and ≥95%/≥90% achieved
- ✅ All failures have specific error codes
- ✅ Preview validation includes text detection
- ✅ Full pipeline validated with storage and database

**Currently at: ~20% ready for production**
**With current infrastructure: 80% of work is collecting real fixtures**

The framework is excellent - now it needs comprehensive test data to prove production readiness.
