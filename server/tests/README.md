# Receipt Processing Test Infrastructure

## Overview

This directory contains a comprehensive test suite that **proves** the receipt processing system works correctly WITHOUT needing real Gmail/Stripe connections.

All tests use static fixtures (HTML files) and compare results against golden expected outputs.

## Directory Structure

```
server/tests/
├── fixtures/
│   └── receipts/           # Static HTML receipt samples
│       ├── stripe_email.html
│       ├── aliexpress_email.html
│       ├── contabo_email.html
│       ├── logo_only.html  (negative test)
│       └── blank.html      (negative test)
│
├── golden/                 # Expected extraction results
│   ├── stripe_email.expected.json
│   ├── aliexpress_email.expected.json
│   ├── contabo_email.expected.json
│   ├── logo_only.expected.json
│   └── blank.expected.json
│
└── test_receipt_processing.py  # Comprehensive test suite
```

## Test Coverage

### Test 1: Preview Generation
**Validates:** Images are not blank or logo-only

- ✅ Real receipts (Stripe, AliExpress, Contabo) generate valid previews
- ✅ Logo-only pages are rejected
- ✅ Blank pages are rejected
- ✅ Preview images have reasonable size (>1KB)

### Test 2: Data Extraction
**Validates:** Amount, vendor, currency, date extraction

- ✅ Extracts correct amounts from all fixtures
- ✅ Identifies vendors correctly
- ✅ Detects currencies (EUR, USD)
- ✅ Extracts dates and invoice numbers

### Test 3: Full Pipeline
**Validates:** End-to-end processing with mocked storage

- ✅ Complete flow: HTML → Preview → Extract → Save
- ✅ Storage mocking works (no real R2/S3 calls)
- ✅ Results match expected golden outputs

### Test 4: Idempotency
**Validates:** Processing same receipt twice doesn't duplicate

- ✅ Can process same receipt multiple times
- ✅ No duplicate previews created
- ✅ No errors on re-processing

### Test 5: Error Handling
**Validates:** Proper error messages

- ✅ Blank pages return specific errors
- ✅ Logo-only pages flagged correctly
- ✅ Missing data has clear error messages

## Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run comprehensive tests
python server/tests/test_receipt_processing.py

# Or use pytest (if available)
pytest server/tests/test_receipt_processing.py -v
```

## Adding New Fixtures

To add a new receipt type for testing:

1. **Create HTML fixture:**
   ```bash
   # Add HTML file with actual receipt content
   server/tests/fixtures/receipts/vendor_name_email.html
   ```

2. **Create golden output:**
   ```json
   // server/tests/golden/vendor_name_email.expected.json
   {
     "vendor": "VendorName",
     "amount": 99.99,
     "currency": "USD",
     "date": "2026-01-23",
     "invoice_number": "INV-12345",
     "preview_should_be_valid": true
   }
   ```

3. **Tests auto-discover:**
   The test suite automatically finds and tests all fixtures!

## Golden Output Format

### Valid Receipt
```json
{
  "vendor": "Stripe",
  "amount": 34.40,
  "currency": "EUR",
  "date": "2025-12-22",
  "invoice_number": "ch_3QR4x2L9vK2QMnzE1XYZ1234",
  "preview_should_be_valid": true
}
```

### Invalid Receipt (Expected to Fail)
```json
{
  "vendor": null,
  "amount": null,
  "currency": null,
  "date": null,
  "invoice_number": null,
  "preview_should_be_valid": false,
  "expected_error": "preview_blank"
}
```

## Definition of Done

Tests pass when:
- ✅ 100% of valid fixtures generate valid previews
- ✅ 100% of valid fixtures extract required fields
- ✅ Logo-only and blank fixtures fail with correct errors
- ✅ Full pipeline test passes
- ✅ Idempotency test passes

## Benefits

### No External Dependencies
- ❌ No Gmail API needed
- ❌ No Stripe API needed
- ❌ No real email accounts
- ✅ All tests run locally
- ✅ Fast execution (<30 seconds)
- ✅ CI/CD friendly

### Reproducible
- ✅ Same fixtures every time
- ✅ Same expected results
- ✅ No flaky tests
- ✅ Easy to debug failures

### Comprehensive Coverage
- ✅ Real-world receipt samples
- ✅ Multiple vendors (Stripe, AliExpress, Contabo)
- ✅ Negative tests (blank, logo-only)
- ✅ Full pipeline validation
- ✅ Idempotency verification

## Test Output Example

```
🧪 COMPREHENSIVE RECEIPT PROCESSING TESTS
======================================================================

Using fixtures from: server/tests/fixtures/receipts
Using golden outputs from: server/tests/golden

🧪 Testing 3 valid receipt fixtures...
  ✅ stripe_email: Valid preview (45,231 bytes)
  ✅ aliexpress_email: Valid preview (38,442 bytes)
  ✅ contabo_email: Valid preview (41,556 bytes)

📊 Preview Generation: 3/3 passed

🧪 Testing amount extraction from 3 fixtures...
  ✅ stripe_email: Amount 34.4 EUR (expected 34.4)
  ✅ aliexpress_email: Amount 67.89 USD (expected 67.89)
  ✅ contabo_email: Amount 19.62 EUR (expected 19.62)

📊 Amount Extraction: 3/3 passed

🎉 ALL TESTS PASSED!
```

## Troubleshooting

### Playwright Not Installed
If you see "Playwright not installed" error:
```bash
pip install playwright
playwright install chromium
```

### Tests Fail
1. Check fixture HTML is valid
2. Verify golden output matches expected format
3. Run with verbose flag: `python server/tests/test_receipt_processing.py -v`
4. Check logs for specific error messages

## Future Enhancements

Ideas for expanding test coverage:

- [ ] Add PDF fixtures (not just HTML)
- [ ] Add image receipt fixtures (JPG/PNG)
- [ ] Test multi-page PDFs
- [ ] Test receipts with attachments
- [ ] Test receipts in different languages (Hebrew, German, etc.)
- [ ] Performance benchmarks
- [ ] Stress tests (100+ receipts)

## License

Part of the ProSaaS receipt processing system.
