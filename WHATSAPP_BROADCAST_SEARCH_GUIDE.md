# WhatsApp Broadcast & Global Search - Implementation Guide

## Overview
This document describes the new WhatsApp broadcast audience selection and global search features.

## 1. WhatsApp Broadcast - Multiple Audience Sources

### User Interface Changes

The WhatsApp broadcast page now supports **3 audience sources**:

1. **לידים מהמערכת (Leads from System)**
   - Select specific leads from your CRM
   - Features:
     - Search by name or phone
     - Filter by lead status
     - Checkbox selection with "Select All" / "Clear" options
     - Shows up to 50 leads with scroll (use filters to narrow down)
     - Live recipient counter

2. **רשימת ייבוא (Import List)**
   - Select from existing import lists
   - Dropdown shows all available lists with lead counts
   - Automatically includes all leads from the selected list
   - Live recipient counter

3. **העלאת CSV (CSV Upload)**
   - Traditional CSV file upload
   - CSV format: must have "phone" column
   - Max file size: 5MB
   - Max recipients: 10,000

### How to Use

#### Create Broadcast with Leads from System:
1. Navigate to WhatsApp → תפוצה
2. Click on "לידים מהמערכת" tab
3. Use search box to find leads by name/phone
4. Click status filters to narrow down leads
5. Select individual leads or use "בחר הכל" (Select All)
6. Recipient counter shows total selected
7. Choose template or message
8. Click "שלח תפוצה"

#### Create Broadcast with Import List:
1. Navigate to WhatsApp → תפוצה
2. Click on "רשימת ייבוא" tab
3. Select import list from dropdown
4. Recipient counter shows total leads in list
5. Choose template or message
6. Click "שלח תפוצה"

#### Create Broadcast with CSV:
1. Navigate to WhatsApp → תפוצה
2. Click on "העלאת CSV" tab
3. Upload CSV file (must have "phone" column)
4. Choose template or message
5. Click "שלח תפוצה"

### Backend Changes

**Endpoint**: `POST /api/whatsapp/broadcasts`

**New Parameters**:
- `audience_source`: "leads" | "import-list" | "csv" | "legacy"
- `lead_ids`: JSON array of lead IDs (when source = "leads")
- `import_list_id`: Import list ID (when source = "import-list")
- `csv_file`: File upload (when source = "csv")

**Backward Compatibility**:
- Legacy `statuses` parameter still works
- If no `audience_source` specified, defaults to legacy behavior

**Example Request**:
```javascript
// Lead selection
const formData = new FormData();
formData.append('provider', 'meta');
formData.append('message_type', 'template');
formData.append('template_id', 'hello_world');
formData.append('audience_source', 'leads');
formData.append('lead_ids', JSON.stringify([1, 2, 3, 4, 5]));

// Import list
formData.append('audience_source', 'import-list');
formData.append('import_list_id', '7');

// CSV (no changes)
formData.append('audience_source', 'csv');
formData.append('csv_file', csvFileObject);
```

### Validation Rules

1. **Lead Selection**: Must select at least 1 lead
2. **Import List**: Must select a list
3. **CSV**: Must upload file
4. **Max Recipients**: 10,000 (all sources)
5. **Phone Validation**: Only leads with valid `phone_e164` included

## 2. Global Search Bar

### Features

**Location**: Main header, between the menu button and notifications bell

**Activation**:
- Click search icon 🔍
- Keyboard shortcut: **Ctrl+K** (Windows/Linux) or **Cmd+K** (Mac)

**Search Capabilities**:
- Searches across: Leads, Calls, WhatsApp, Contacts
- Real-time search as you type
- Click result to navigate directly to item
- Full RTL support

### Backend

**Endpoint**: `GET /api/search?q={query}&types={types}`

**Parameters**:
- `q`: Search query (required, min 2 chars)
- `types`: Comma-separated types (optional): "leads,calls,whatsapp,contacts"

**Example**:
```bash
curl https://prosaas.pro/api/search?q=john&types=leads,calls
```

## 3. Testing Checklist

### WhatsApp Broadcast Testing

- [ ] **Lead Selection from System**:
  - [ ] Search for leads by name
  - [ ] Search for leads by phone
  - [ ] Filter by multiple statuses
  - [ ] Select individual leads
  - [ ] Use "Select All" button
  - [ ] Use "Clear" button
  - [ ] Verify recipient counter updates correctly
  - [ ] Create broadcast and verify sends to selected leads only
  - [ ] Test with 1 lead
  - [ ] Test with 50+ leads (verify pagination message)

- [ ] **Import List Selection**:
  - [ ] Verify dropdown shows all import lists
  - [ ] Verify recipient count shown for each list
  - [ ] Select import list
  - [ ] Verify recipient counter updates
  - [ ] Create broadcast and verify sends to all leads in list
  - [ ] Test with empty import list (should show 0)
  - [ ] Test with large import list (1000+ leads)

- [ ] **CSV Upload**:
  - [ ] Upload valid CSV with "phone" column
  - [ ] Verify file size validation (>5MB should fail)
  - [ ] Verify row limit (>10,000 should fail)
  - [ ] Create broadcast and verify sends
  - [ ] Test backward compatibility with legacy CSV method

- [ ] **Cross-Source Testing**:
  - [ ] Switch between tabs and verify state resets
  - [ ] Verify only one source can be active at a time
  - [ ] Test Meta provider with all 3 sources
  - [ ] Test Baileys provider with all 3 sources

### Global Search Testing

- [ ] **Search Button**:
  - [ ] Verify search icon visible in header
  - [ ] Verify positioned next to notifications bell
  - [ ] Click opens search modal
  - [ ] Verify RTL alignment

- [ ] **Keyboard Shortcut**:
  - [ ] Press Ctrl+K (Windows/Linux)
  - [ ] Press Cmd+K (Mac)
  - [ ] Verify modal opens
  - [ ] Verify focus on search input

- [ ] **Search Functionality**:
  - [ ] Type 2+ characters
  - [ ] Verify results appear
  - [ ] Search for existing lead by name
  - [ ] Search for existing call
  - [ ] Search for WhatsApp conversation
  - [ ] Click result navigates to correct page
  - [ ] Press Escape closes modal

- [ ] **API Endpoint**:
  - [ ] `/api/search?q=test` returns results
  - [ ] Returns 200 or 401 (not 404)
  - [ ] Handles Hebrew text correctly
  - [ ] Handles special characters

## 4. Known Limitations

1. **Lead Selection**: Shows max 50 leads in UI (use filters to narrow down)
2. **Import List**: Cannot preview which leads are in list (shows count only)
3. **CSV**: No preview before sending (validates on server)
4. **Recipient Limit**: Hard limit of 10,000 per broadcast

## 5. Troubleshooting

### Issue: "לא נמצאו לידים"
**Solution**: 
- Check if you have leads in the system
- Try removing status filters
- Clear search term

### Issue: "אין רשימות ייבוא זמינות"
**Solution**:
- Import lists must be created first via Outbound Calls → Import
- Check if user has permission to access import lists

### Issue: CSV upload fails
**Solution**:
- Verify CSV has "phone" column
- Check file size < 5MB
- Verify CSV has valid encoding (UTF-8)
- Check row count < 10,000

### Issue: Search modal doesn't open
**Solution**:
- Check browser console for errors
- Verify `/api/search` endpoint returns 200 or 401 (not 404)
- Try clicking search icon instead of keyboard shortcut

## 6. Future Enhancements

- [ ] Save audience as reusable segment
- [ ] Preview leads in import list before sending
- [ ] CSV validation with preview before creating broadcast
- [ ] Bulk actions on lead selection (export, tag, etc.)
- [ ] Search within WhatsApp broadcast history
- [ ] Advanced filters (date range, tags, custom fields)
- [ ] Schedule broadcasts for later
- [ ] A/B testing with different messages
