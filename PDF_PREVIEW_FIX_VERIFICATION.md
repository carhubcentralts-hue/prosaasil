# PDF Preview & Pagination Fix Verification Guide

## Overview
This document describes how to verify the PDF preview and pagination fixes for the contracts signature placement feature.

## Problem Statement
1. **PDF not loading in Preview** - The preview frame was empty
2. **"Next Page" button doesn't navigate** - Unable to mark signatures on other pages

## Root Causes Identified

### Frontend Issues
1. **SignatureFieldMarker.tsx**: The component was passing the API endpoint URL directly to the iframe
   - The endpoint `/api/contracts/{id}/files/{file_id}/download` returns JSON with a `url` field, not the PDF itself
   - The iframe was trying to render JSON instead of the actual PDF

2. **SimplifiedPDFSigning.tsx**: Same issue on the public signing page

3. **Pagination**: Changing `currentPage` state didn't reload the iframe
   - The iframe `src` was changing but the browser wasn't reloading
   - Solution: Added a `key` prop that includes the page number to force React to remount the iframe

### Backend Issues
1. **Missing Headers**: Presigned URLs from R2 weren't forcing proper Content-Type and Content-Disposition headers
   - Added parameters to `generate_signed_url` in R2 provider
   - Updated attachment service to pass mime_type and filename
   - Updated contracts download endpoint to provide metadata

## Solution Implemented

### Frontend Changes

#### SignatureFieldMarker.tsx
```typescript
// 1. Added state for PDF ObjectURL
const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);

// 2. Load PDF as blob and create ObjectURL
useEffect(() => {
  const loadPdf = async () => {
    // Fetch JSON response to get signed URL
    const downloadResponse = await fetch(pdfUrl, { credentials: 'include' });
    const downloadData = await downloadResponse.json();
    const signedUrl = downloadData.url;
    
    // Fetch actual PDF as blob
    const pdfResponse = await fetch(signedUrl, { credentials: 'include' });
    const blob = await pdfResponse.blob();
    
    // Validate it's a PDF
    const contentType = pdfResponse.headers.get('content-type');
    if (!blob.type.includes('pdf') && !contentType?.includes('pdf')) {
      throw new Error('Not a PDF');
    }
    
    // Create ObjectURL
    const objectUrl = URL.createObjectURL(blob);
    setPdfObjectUrl(objectUrl);
  };
  
  loadPdf();
  
  // Cleanup
  return () => {
    if (pdfObjectUrl) URL.revokeObjectURL(pdfObjectUrl);
  };
}, [pdfUrl]);

// 3. Use ObjectURL in iframe with key prop for pagination
<iframe
  key={`${pdfObjectUrl}-${currentPage}`}  // Forces reload when page changes
  src={`${pdfObjectUrl}#page=${currentPage}&view=FitH`}
  className="absolute inset-0 w-full h-full"
  title="PDF Preview"
/>
```

#### SimplifiedPDFSigning.tsx
Same changes applied for public signing page.

### Backend Changes

#### routes_contracts.py
```python
# Pass mime_type and filename to attachment service
signed_url = attachment_service.generate_signed_url(
    attachment.id,
    attachment.storage_path,
    ttl_minutes=ttl_seconds // 60,
    mime_type=attachment.mime_type,      # NEW
    filename=attachment.filename_original  # NEW
)
```

#### attachment_service.py
```python
def generate_signed_url(self, attachment_id: int, storage_key: str, 
                       ttl_minutes: int = 60, 
                       mime_type: str = None,      # NEW
                       filename: str = None):      # NEW
    kwargs = {'ttl_seconds': ttl_seconds}
    
    if mime_type:
        kwargs['content_type'] = mime_type
        
    if filename:
        disposition = 'inline' if mime_type and 'pdf' in mime_type.lower() else 'attachment'
        kwargs['content_disposition'] = f'{disposition}; filename="{filename}"'
    
    return self.storage.generate_signed_url(storage_key, **kwargs)
```

#### r2_provider.py
```python
def generate_signed_url(self, storage_key: str, ttl_seconds: int = 900, 
                       content_type: str = None,         # NEW
                       content_disposition: str = None): # NEW
    params = {
        'Bucket': self.bucket_name,
        'Key': storage_key
    }
    
    # Force headers in presigned URL
    if content_type:
        params['ResponseContentType'] = content_type
    if content_disposition:
        params['ResponseContentDisposition'] = content_disposition
    
    url = self.s3_client.generate_presigned_url(
        'get_object',
        Params=params,
        ExpiresIn=ttl_seconds
    )
    
    return url
```

## Testing Instructions

### 1. Test PDF Preview Loading
1. Navigate to Contracts page
2. Create a new contract or open an existing draft
3. Upload a PDF file
4. Click "סמן אזורי חתימה" (Mark signature areas)
5. **Expected**: PDF should load within 1-2 seconds
6. **Verify**: No console errors about PDF loading
7. **Verify**: Browser DevTools Network tab shows:
   - First request: `/api/contracts/{id}/files/{file_id}/download` returns JSON
   - Second request: Signed URL returns PDF with `Content-Type: application/pdf`

### 2. Test Page Navigation
1. In the signature marking dialog:
2. Click "עמוד הבא" (Next Page)
3. **Expected**: PDF iframe reloads and shows the next page
4. Click "עמוד קודם" (Previous Page)
5. **Expected**: PDF iframe reloads and shows the previous page
6. **Verify**: Page counter updates correctly (e.g., "עמוד 2 מתוך 10")

### 3. Test Signature Field Placement Across Pages
1. On page 1, draw a signature field (click and drag)
2. Navigate to page 2
3. Draw another signature field
4. Navigate back to page 1
5. **Expected**: Original signature field is still visible
6. Navigate back to page 2
7. **Expected**: Second signature field is still visible
8. Click "שמור" (Save)
9. **Expected**: Both signature fields are saved with correct page numbers

### 4. Test Public Signing Page
1. Send a contract for signature
2. Copy the signing URL
3. Open URL in an incognito window
4. **Expected**: PDF loads correctly
5. Navigate between pages
6. **Expected**: Signature areas are visible on correct pages
7. Draw a signature
8. **Expected**: Signature can be placed
9. Click "חתום על המסמך" (Sign document)
10. **Expected**: Document is signed successfully

### 5. Test Mobile/Responsive
1. Open signature marking on mobile device or resize browser
2. **Expected**: PDF scales properly
3. **Expected**: Signature field coordinates remain accurate (normalized 0-1)
4. **Expected**: Touch events work for drawing signature fields

## Console Logs for Debugging

The implementation includes console logs for debugging:

```
[PDF_LOAD] Fetching PDF metadata from: /api/contracts/...
[PDF_LOAD] Got signed URL, fetching PDF blob...
[PDF_LOAD] PDF Content-Type: application/pdf
[PDF_LOAD] PDF blob loaded, size: 123456
[PDF_LOAD] PDF loaded successfully
[PDF_LOAD] Revoking ObjectURL
```

## Expected Behavior

### Success Criteria
✅ PDF loads in 1-2 seconds in preview  
✅ "Next Page"/"Previous Page" buttons navigate between pages  
✅ Can mark signature fields on any page  
✅ Switching pages preserves existing signature fields  
✅ Signature fields use normalized coordinates (0-1) per page  
✅ Mobile/zoom doesn't break signature placement  
✅ No console errors about PDF loading  
✅ Build passes successfully  

### Error Handling
- If PDF fails to load: Shows error message "לא ניתן לטעון PDF"
- If not a PDF: Logs content type and shows error
- If fetch fails: Shows error with status code
- Loading state: Shows spinner while fetching

## Technical Notes

### ObjectURL Lifecycle
- Created when PDF is successfully loaded as blob
- Automatically revoked when component unmounts
- Revoked when new PDF is loaded
- Prevents memory leaks

### Page Navigation
- Uses iframe `key` prop to force remount when page changes
- Format: `key={pdfObjectUrl}-${currentPage}`
- This ensures the browser reloads the PDF with the new page number

### Signature Field Storage
- Fields stored with normalized coordinates (0-1 range)
- Each field includes page number
- Filtered by current page when rendering
- Mobile-friendly (coordinates scale with container)

### Header Forcing in R2
- `ResponseContentType` forces Content-Type in response
- `ResponseContentDisposition` forces Content-Disposition
- Works even if headers weren't set during upload
- Ensures consistent behavior across all PDFs

## Known Limitations

1. **Default Page Count**: Defaults to 10 pages until actual page count is determined
   - User can still navigate beyond if PDF has more pages
   - Backend could add a PDF info endpoint to get actual page count

2. **Page Hash Navigation**: Relies on browser PDF viewer to support `#page=N`
   - Works in Chrome, Firefox, Safari, Edge
   - May not work in some mobile browsers (fallback to page 1)

3. **Large PDFs**: Very large PDFs (>50MB) may take longer to load
   - Consider implementing progressive loading or streaming
   - Current implementation loads entire blob before rendering

## Rollback Instructions

If issues are found, revert these commits:
```bash
git revert 7584adc  # Revert PDF preview and pagination fixes
```

Files affected:
- `client/src/components/SignatureFieldMarker.tsx`
- `client/src/components/SimplifiedPDFSigning.tsx`
- `server/routes_contracts.py`
- `server/services/attachment_service.py`
- `server/services/storage/r2_provider.py`
- `server/services/storage/local_provider.py`
