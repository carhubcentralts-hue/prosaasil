#!/usr/bin/env python3
"""
🔧 Sync Development Database Schema
Run this script to ensure development DB has same tables as production.
This prevents Replit from deleting tables during deployment!

Usage:
    python scripts/sync_dev_schema.py
"""
import os
import sys

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def main():
    print("=" * 60)
    print("🔧 DEVELOPMENT DATABASE SCHEMA SYNC")
    print("=" * 60)
    print()
    print("This script creates missing tables in development DB.")
    print("CRITICAL: Run this BEFORE deploying to prevent data loss!")
    print()
    
    # Import after path setup
    from server.app_factory import create_app
    from server.db_migrate import apply_migrations
    from server.init_database import initialize_production_database
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        print("📊 Connected to database...")
        print(f"   DATABASE_URL: {os.getenv('DATABASE_URL', 'not set')[:50]}...")
        print()
        
        # Apply migrations
        print("🔄 Applying migrations...")
        apply_migrations()
        print()
        
        # Initialize default data (safe - checks if data exists)
        print("🔄 Initializing default data...")
        initialize_production_database()
        print()
        
        print("=" * 60)
        print("✅ DEVELOPMENT DATABASE SCHEMA SYNC COMPLETE!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Verify tables exist using Database pane")
        print("2. Deploy to production safely - no data loss!")
        print()

if __name__ == "__main__":
    main()
