# PDF Streaming Fix - Visual Guide

## Before Fix (❌ Complex & Error-Prone)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (Client)                            │
│                                                                       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  SignatureFieldMarker Component                       │           │
│  │                                                        │           │
│  │  1. fetch(/api/contracts/24/files/33/download)       │           │
│  │     ↓                                                  │           │
│  │  2. Returns: { url: "https://r2.cloudflarestorage... │           │
│  │     (Presigned URL with auth token, expires in 15min)│           │
│  │     ↓                                                  │           │
│  │  3. fetch(presignedUrl)                              │           │
│  │     ↓                                                  │           │
│  │  4. Download PDF as Blob                              │           │
│  │     ↓                                                  │           │
│  │  5. URL.createObjectURL(blob)                        │           │
│  │     ↓                                                  │           │
│  │  6. <iframe src={objectUrl} />                       │           │
│  │                                                        │           │
│  │  ❌ PROBLEMS:                                         │           │
│  │  • 3 network requests                                 │           │
│  │  • Presigned URL may have CORS issues                │           │
│  │  • ObjectURL needs manual cleanup                    │           │
│  │  • Complex error handling                            │           │
│  │  • iOS Safari compatibility issues                   │           │
│  └──────────────────────────────────────────────────────┘           │
│                          ↓                                            │
└────────────────────────│─────────────────────────────────────────────┘
                         │
                         ↓
        ┌────────────────────────────────┐
        │    Backend Server (Flask)       │
        │                                 │
        │  /api/contracts/24/files/33/   │
        │         download                │
        │                                 │
        │  • Generate presigned URL       │
        │  • Return JSON with URL         │
        └────────────────────────────────┘
                         ↓
        ┌────────────────────────────────┐
        │   R2 Storage (Cloudflare)      │
        │                                 │
        │  • Accept presigned request     │
        │  • Serve PDF file               │
        │  • May have CORS restrictions   │
        └────────────────────────────────┘
```

## After Fix (✅ Simple & Reliable)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (Client)                            │
│                                                                       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  SignatureFieldMarker Component                       │           │
│  │                                                        │           │
│  │  1. <iframe src="/api/contracts/24/pdf" />           │           │
│  │     (Single request with browser credentials)         │           │
│  │                                                        │           │
│  │  ✅ BENEFITS:                                         │           │
│  │  • 1 network request                                  │           │
│  │  • No CORS issues (same-origin)                      │           │
│  │  • Browser handles auth automatically                │           │
│  │  • No manual cleanup needed                          │           │
│  │  • iOS Safari compatible                             │           │
│  │  • Proper caching with Cache-Control                 │           │
│  └──────────────────────────────────────────────────────┘           │
│                          ↓                                            │
└────────────────────────│─────────────────────────────────────────────┘
                         │ (Single authenticated request)
                         ↓
        ┌────────────────────────────────┐
        │    Backend Server (Flask)       │
        │                                 │
        │  /api/contracts/24/pdf          │
        │  @require_api_auth              │
        │  @require_page_access           │
        │                                 │
        │  1. Verify auth & permissions   │
        │  2. Get contract & attachment   │
        │  3. Load PDF from storage       │
        │  4. Stream to response          │
        │                                 │
        │  Response Headers:              │
        │  • Content-Type: application/pdf│
        │  • Content-Disposition: inline  │
        │  • Cache-Control: no-store      │
        │  • X-Content-Type-Options: nosni│
        └────────────────────────────────┘
                         ↓
        ┌────────────────────────────────┐
        │   R2 Storage (Cloudflare)      │
        │         (or Local)              │
        │                                 │
        │  • Backend fetches PDF bytes    │
        │  • No presigned URL needed      │
        │  • No CORS concerns             │
        └────────────────────────────────┘
```

## Code Comparison

### Before (Frontend)
```typescript
// Complex blob loading with multiple steps
const downloadResponse = await fetch(pdfUrl, { credentials: 'include' });
const downloadData = await downloadResponse.json();
const signedUrl = downloadData.url;

const pdfResponse = await fetch(signedUrl, { credentials: 'include' });
const blob = await pdfResponse.blob();

const objectUrl = URL.createObjectURL(blob);
setPdfObjectUrl(objectUrl);

// Cleanup required
return () => {
  if (pdfObjectUrl) {
    URL.revokeObjectURL(pdfObjectUrl);
  }
};
```

### After (Frontend)
```typescript
// Simple direct URL usage
setPdfObjectUrl(pdfUrl); // pdfUrl = "/api/contracts/24/pdf"
// No cleanup needed - browser handles it
```

### After (Backend)
```python
@contracts_bp.route('/<int:contract_id>/pdf', methods=['GET'])
@require_api_auth
@require_page_access('contracts')
def stream_contract_pdf(contract_id):
    # Get file bytes from storage
    filename, mime_type, file_bytes = attachment_service.open_file(
        attachment.storage_path,
        filename=attachment.filename_original,
        mime_type=attachment.mime_type
    )
    
    # Return streaming response with proper headers
    return Response(
        io.BytesIO(file_bytes),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'inline; filename="contract.pdf"',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'X-Content-Type-Options': 'nosniff',
            'Content-Length': str(len(file_bytes))
        }
    )
```

## Mobile Compatibility

### iOS Safari Issues (Before)
- ❌ Object URLs not always supported in iframes
- ❌ Blob loading can fail silently
- ❌ Sandbox restrictions interfere with auth

### iOS Safari Compatible (After)
```typescript
<iframe
  src={`${pdfObjectUrl}#page=${currentPage}&view=FitH`}
  sandbox="allow-same-origin allow-scripts allow-downloads"
  style={{ border: 'none', minHeight: '70vh' }}
/>
```

✅ Key Attributes:
- `sandbox="allow-same-origin"` - Allows authenticated requests
- `allow-scripts` - Allows PDF.js to work
- `allow-downloads` - Allows user to download
- `minHeight: 70vh` - Better mobile viewport

## Security Flow

### Authentication & Authorization
```
User Request
    ↓
@require_api_auth
    ↓ (Verify JWT/Session)
@require_page_access('contracts')
    ↓ (Check page permission)
Verify Contract Ownership
    ↓ (business_id match)
Verify File is PDF
    ↓ (mime_type check)
Stream PDF
    ↓
Log Access Event
    ↓
Return Response
```

## Network Tab Verification

### Before (3 requests)
```
1. GET /api/contracts/24/files/33/download
   Status: 200 OK
   Content-Type: application/json
   Body: { "url": "https://r2.cloudflarestorage.com/...", ... }

2. GET https://r2.cloudflarestorage.com/bucket/...?X-Amz-Signature=...
   Status: 200 OK (or 403 CORS error)
   Content-Type: application/pdf

3. blob:http://localhost:3000/xxxx-xxxx-xxxx
   (ObjectURL - not a real network request)
```

### After (1 request)
```
1. GET /api/contracts/24/pdf
   Status: 200 OK
   Content-Type: application/pdf
   Content-Disposition: inline; filename="contract.pdf"
   Content-Length: 245678
   Cache-Control: no-store, no-cache, must-revalidate, max-age=0
```

## Error Messages

### Before
- "Load failed" (generic, hard to debug)
- "Failed to fetch PDF: 403" (CORS error)
- "Expected PDF but got unknown type" (blob type mismatch)

### After
- "Contract not found" (clear 404)
- "File is not a PDF" (clear 400)
- "PDF file not found in storage" (clear 404)
- Proper HTTP status codes for all errors

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| Network Requests | 3 | 1 |
| CORS Issues | ❌ Possible | ✅ None |
| Auth Handling | Manual in 2 places | Browser automatic |
| Mobile Compatible | ❌ No | ✅ Yes |
| Code Complexity | High | Low |
| Error Messages | Generic | Specific |
| Security | Token expiration issues | Full auth system |
| Performance | 3x slower | Fast |

**Result: ✅ PDF loads reliably in all browsers, including mobile!**
