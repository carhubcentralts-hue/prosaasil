#!/usr/bin/env python3
"""
Migration: Add unique constraint on whatsapp_message.provider_message_id
Prevents duplicate messages from webhook retries

This adds:
- UNIQUE constraint on provider_message_id (nullable)
- Index for faster lookups
"""

def migrate_up(db):
    """Apply migration"""
    print("Adding unique constraint on whatsapp_message.provider_message_id...")
    
    # First, remove any existing duplicates (keep oldest)
    db.execute("""
        DELETE FROM whatsapp_message
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM whatsapp_message
            WHERE provider_message_id IS NOT NULL
            GROUP BY provider_message_id
        )
        AND provider_message_id IS NOT NULL
    """)
    
    rows_deleted = db.rowcount
    if rows_deleted > 0:
        print(f"  Removed {rows_deleted} duplicate messages")
    
    # Add unique constraint (partial - only for non-NULL values)
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_message_provider_id_unique
        ON whatsapp_message(provider_message_id)
        WHERE provider_message_id IS NOT NULL
    """)
    
    print("✓ Unique constraint added successfully")


def migrate_down(db):
    """Rollback migration"""
    print("Removing unique constraint on whatsapp_message.provider_message_id...")
    
    db.execute("""
        DROP INDEX IF EXISTS idx_whatsapp_message_provider_id_unique
    """)
    
    print("✓ Unique constraint removed")


if __name__ == '__main__':
    # For manual testing
    from server.db import db
    from server.app_factory import create_app
    
    app = create_app()
    with app.app_context():
        print("Testing migration...")
        migrate_up(db.session)
        db.session.commit()
        print("Migration test successful!")
