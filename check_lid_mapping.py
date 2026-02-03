#!/usr/bin/env python3
"""
Quick script to check LID→Phone mappings in the database
"""
import sys
sys.path.insert(0, '/app')

from server import dao_crm

# Check contact_identities table
print("=" * 60)
print("LID Mappings in contact_identities:")
print("=" * 60)

rows = dao_crm.execute_raw_query("""
    SELECT id, business_id, lid_jid, phone_e164, source, created_at, updated_at
    FROM contact_identities
    WHERE lid_jid IS NOT NULL
    ORDER BY updated_at DESC
    LIMIT 10
""")

if rows:
    for row in rows:
        print(f"ID: {row[0]}, Business: {row[1]}, LID: {row[2]}, Phone: {row[3]}, Source: {row[4]}, Updated: {row[6]}")
else:
    print("No LID mappings found!")

print("\n" + "=" * 60)
print("Recent conversations with LID:")
print("=" * 60)

# Check conversations for LID
convos = dao_crm.execute_raw_query("""
    SELECT id, business_id, channel_id, phone_e164, created_at
    FROM conversations
    WHERE channel_id LIKE '%@lid'
    ORDER BY created_at DESC
    LIMIT 5
""")

if convos:
    for c in convos:
        print(f"Convo ID: {c[0]}, Business: {c[1]}, Channel (LID): {c[2]}, Phone: {c[3]}, Created: {c[4]}")
else:
    print("No conversations with @lid channel_id found")

print("\n" + "=" * 60)
print("Searching for specific LID: 87621728518253@lid")
print("=" * 60)

# Search for specific LID
specific = dao_crm.execute_raw_query("""
    SELECT id, business_id, lid_jid, phone_e164, source
    FROM contact_identities
    WHERE lid_jid = '87621728518253@lid'
""")

if specific:
    print(f"Found! Phone: {specific[0][3]}")
else:
    print("Not found in contact_identities")

# Check if conversation exists
convo_lid = dao_crm.execute_raw_query("""
    SELECT id, phone_e164, channel_id
    FROM conversations
    WHERE channel_id = '87621728518253@lid'
    LIMIT 1
""")

if convo_lid:
    print(f"Found conversation! ID: {convo_lid[0][0]}, Phone: {convo_lid[0][1]}, Channel: {convo_lid[0][2]}")
else:
    print("No conversation found with this LID")
