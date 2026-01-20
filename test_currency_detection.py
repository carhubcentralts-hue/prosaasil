"""
Test currency detection improvements in Gmail receipt extraction
"""

import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from server.services.gmail_sync_service import extract_receipt_data

# Test cases
test_cases = [
    {
        'name': 'USD receipt with $ symbol',
        'pdf_text': 'Invoice\nTotal: $150.00\nThank you for your purchase',
        'metadata': {'from_domain': 'amazon.com'},
        'expected_currency': 'USD',
        'expected_amount': 150.0
    },
    {
        'name': 'ILS receipt with ₪ symbol',
        'pdf_text': 'חשבונית\nסה"כ: ₪350.50\nתודה על הקנייה',
        'metadata': {'from_domain': 'icount.co.il'},
        'expected_currency': 'ILS',
        'expected_amount': 350.5
    },
    {
        'name': 'USD receipt with multiple $ symbols',
        'pdf_text': 'Receipt\nSubtotal: $100\nTax: $10\nTotal: $110.00',
        'metadata': {'from_domain': 'stripe.com'},
        'expected_currency': 'USD',
        'expected_amount': 110.0
    },
    {
        'name': 'ILS receipt with Hebrew keywords',
        'pdf_text': 'חשבונית מס\nלתשלום: 250 ₪\nמספר חשבונית: 12345',
        'metadata': {'from_domain': 'greeninvoice.co.il'},
        'expected_currency': 'ILS',
        'expected_amount': 250.0
    },
    {
        'name': 'EUR receipt with € symbol',
        'pdf_text': 'Invoice\nTotal: €99.99\nEUR payment',
        'metadata': {'from_domain': 'example.eu'},
        'expected_currency': 'EUR',
        'expected_amount': 99.99
    },
    {
        'name': 'USD with dollar word',
        'pdf_text': 'Receipt\nAmount: 50 USD\nThank you',
        'metadata': {'from_domain': 'paypal.com'},
        'expected_currency': 'USD',
        'expected_amount': 50.0
    },
    {
        'name': 'Mixed currency ($ appears more)',
        'pdf_text': 'Invoice\nPrice: $200\nDiscount: $20\nTax ₪15\nTotal: $180',
        'metadata': {'from_domain': 'example.com'},
        'expected_currency': 'USD',  # USD should win because it has more occurrences
        'expected_amount': 180.0
    },
    {
        'name': 'No currency symbols - Israeli domain',
        'pdf_text': 'חשבונית\nסה"כ לתשלום: 500\nתודה',
        'metadata': {'from_domain': 'something.co.il'},
        'expected_currency': 'ILS',  # Should infer from .co.il domain
        'expected_amount': 500.0
    },
]

print("Testing Currency Detection Logic\n" + "="*60)

passed = 0
failed = 0

for test_case in test_cases:
    print(f"\nTest: {test_case['name']}")
    print(f"PDF Text: {test_case['pdf_text'][:50]}...")
    
    result = extract_receipt_data(test_case['pdf_text'], test_case['metadata'])
    
    currency_match = result['currency'] == test_case['expected_currency']
    amount_match = result['amount'] == test_case['expected_amount']
    
    if currency_match and amount_match:
        print(f"✅ PASS - Currency: {result['currency']}, Amount: {result['amount']}")
        passed += 1
    else:
        print(f"❌ FAIL")
        print(f"   Expected: {test_case['expected_currency']} {test_case['expected_amount']}")
        print(f"   Got:      {result['currency']} {result['amount']}")
        failed += 1

print("\n" + "="*60)
print(f"Results: {passed}/{len(test_cases)} passed, {failed} failed")

if failed == 0:
    print("✅ All tests passed!")
    sys.exit(0)
else:
    print("❌ Some tests failed")
    sys.exit(1)
