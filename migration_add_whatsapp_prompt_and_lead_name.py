#!/usr/bin/env python3
"""
Migration: Add WhatsApp system prompt and Lead name tracking
Part 1: WhatsApp prompt management (business.whatsapp_system_prompt)
Part 2: Lead name tracking (leads.name, name_source, name_updated_at)

This migration adds:
Business table:
- whatsapp_system_prompt (TEXT) - Dedicated WhatsApp AI prompt
- whatsapp_temperature (FLOAT) - Temperature for WhatsApp responses
- whatsapp_model (VARCHAR(50)) - Model for WhatsApp responses
- whatsapp_max_tokens (INT) - Max tokens for WhatsApp responses

Lead table:
- name (VARCHAR(255)) - Lead's full name (computed from first_name+last_name or standalone)
- name_source (VARCHAR(32)) - Source of name: 'whatsapp', 'call', 'manual'
- name_updated_at (TIMESTAMP) - When name was last updated
"""

def migrate_up(db):
    """Apply migration"""
    print("Adding WhatsApp prompt and Lead name tracking columns...")
    
    # Part 1: Add WhatsApp prompt columns to business table
    try:
        print("  Adding whatsapp_system_prompt to business...")
        db.execute("""
            ALTER TABLE business 
            ADD COLUMN IF NOT EXISTS whatsapp_system_prompt TEXT
        """)
        print("  ✓ whatsapp_system_prompt added")
    except Exception as e:
        print(f"  Note: whatsapp_system_prompt may already exist: {e}")
    
    try:
        print("  Adding whatsapp_temperature to business...")
        db.execute("""
            ALTER TABLE business 
            ADD COLUMN IF NOT EXISTS whatsapp_temperature FLOAT DEFAULT 0.0
        """)
        print("  ✓ whatsapp_temperature added")
    except Exception as e:
        print(f"  Note: whatsapp_temperature may already exist: {e}")
    
    try:
        print("  Adding whatsapp_model to business...")
        db.execute("""
            ALTER TABLE business 
            ADD COLUMN IF NOT EXISTS whatsapp_model VARCHAR(50) DEFAULT 'gpt-4o-mini'
        """)
        print("  ✓ whatsapp_model added")
    except Exception as e:
        print(f"  Note: whatsapp_model may already exist: {e}")
    
    try:
        print("  Adding whatsapp_max_tokens to business...")
        db.execute("""
            ALTER TABLE business 
            ADD COLUMN IF NOT EXISTS whatsapp_max_tokens INTEGER DEFAULT 350
        """)
        print("  ✓ whatsapp_max_tokens added")
    except Exception as e:
        print(f"  Note: whatsapp_max_tokens may already exist: {e}")
    
    # Part 2: Add name tracking columns to leads table
    try:
        print("  Adding name to leads...")
        db.execute("""
            ALTER TABLE leads 
            ADD COLUMN IF NOT EXISTS name VARCHAR(255)
        """)
        print("  ✓ name added")
    except Exception as e:
        print(f"  Note: name may already exist: {e}")
    
    try:
        print("  Adding name_source to leads...")
        db.execute("""
            ALTER TABLE leads 
            ADD COLUMN IF NOT EXISTS name_source VARCHAR(32)
        """)
        print("  ✓ name_source added")
    except Exception as e:
        print(f"  Note: name_source may already exist: {e}")
    
    try:
        print("  Adding name_updated_at to leads...")
        db.execute("""
            ALTER TABLE leads 
            ADD COLUMN IF NOT EXISTS name_updated_at TIMESTAMP
        """)
        print("  ✓ name_updated_at added")
    except Exception as e:
        print(f"  Note: name_updated_at may already exist: {e}")
    
    # Migrate existing lead names to new name column
    print("  Migrating existing lead names...")
    db.execute("""
        UPDATE leads 
        SET name = CASE 
            WHEN first_name IS NOT NULL AND last_name IS NOT NULL 
                THEN first_name || ' ' || last_name
            WHEN first_name IS NOT NULL 
                THEN first_name
            WHEN last_name IS NOT NULL 
                THEN last_name
            ELSE NULL
        END,
        name_source = 'manual',
        name_updated_at = updated_at
        WHERE name IS NULL 
        AND (first_name IS NOT NULL OR last_name IS NOT NULL)
    """)
    rows_updated = db.rowcount
    print(f"  ✓ Migrated {rows_updated} existing lead names")
    
    print("✓ Migration completed successfully")


def migrate_down(db):
    """Rollback migration"""
    print("Removing WhatsApp prompt and Lead name tracking columns...")
    
    # Remove business columns
    try:
        db.execute("ALTER TABLE business DROP COLUMN IF EXISTS whatsapp_system_prompt")
        db.execute("ALTER TABLE business DROP COLUMN IF EXISTS whatsapp_temperature")
        db.execute("ALTER TABLE business DROP COLUMN IF EXISTS whatsapp_model")
        db.execute("ALTER TABLE business DROP COLUMN IF EXISTS whatsapp_max_tokens")
        print("  ✓ Business columns removed")
    except Exception as e:
        print(f"  Error removing business columns: {e}")
    
    # Remove leads columns
    try:
        db.execute("ALTER TABLE leads DROP COLUMN IF EXISTS name")
        db.execute("ALTER TABLE leads DROP COLUMN IF EXISTS name_source")
        db.execute("ALTER TABLE leads DROP COLUMN IF EXISTS name_updated_at")
        print("  ✓ Lead columns removed")
    except Exception as e:
        print(f"  Error removing lead columns: {e}")
    
    print("✓ Rollback completed")


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
