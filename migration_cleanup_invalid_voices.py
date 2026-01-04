"""
Migration: Clean up invalid voice_id values in businesses table
Only Realtime-supported voices are allowed: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
Any other voice (fable, nova, onyx, or NULL) will be reset to 'cedar' (default)

This prevents session.update timeouts caused by unsupported voices.
"""
import os
import sys
from sqlalchemy import create_engine, text

# Valid Realtime voices
REALTIME_VOICES = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
DEFAULT_VOICE = 'cedar'

def run_migration():
    """Clean up invalid voice_id values in businesses table"""
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)
    
    print("🔧 Starting voice cleanup migration...")
    print(f"✅ Valid Realtime voices: {', '.join(REALTIME_VOICES)}")
    print(f"🎤 Default voice: {DEFAULT_VOICE}")
    
    # Create engine
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Check if voice_id column exists
                check_column = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'businesses' 
                    AND column_name = 'voice_id'
                """)
                result = conn.execute(check_column)
                if not result.fetchone():
                    print("ℹ️ voice_id column does not exist in businesses table - skipping migration")
                    trans.rollback()
                    return
                
                # Find businesses with invalid voices
                check_query = text("""
                    SELECT id, name, voice_id 
                    FROM businesses 
                    WHERE voice_id IS NULL 
                       OR voice_id NOT IN :valid_voices
                    ORDER BY id
                """)
                
                invalid_businesses = conn.execute(
                    check_query,
                    {"valid_voices": tuple(REALTIME_VOICES)}
                ).fetchall()
                
                if not invalid_businesses:
                    print("✅ No businesses with invalid voices found")
                    trans.rollback()
                    return
                
                print(f"\n📊 Found {len(invalid_businesses)} businesses with invalid voices:")
                for biz in invalid_businesses:
                    biz_id, biz_name, voice = biz
                    print(f"  - Business #{biz_id} ({biz_name}): voice_id='{voice}' -> will update to '{DEFAULT_VOICE}'")
                
                # Update invalid voices to default
                update_query = text("""
                    UPDATE businesses 
                    SET voice_id = :default_voice
                    WHERE voice_id IS NULL 
                       OR voice_id NOT IN :valid_voices
                """)
                
                result = conn.execute(
                    update_query,
                    {
                        "default_voice": DEFAULT_VOICE,
                        "valid_voices": tuple(REALTIME_VOICES)
                    }
                )
                
                updated_count = result.rowcount
                print(f"\n✅ Updated {updated_count} businesses to voice_id='{DEFAULT_VOICE}'")
                
                # Verify the update
                verify_query = text("""
                    SELECT COUNT(*) 
                    FROM businesses 
                    WHERE voice_id IS NOT NULL 
                      AND voice_id NOT IN :valid_voices
                """)
                
                remaining = conn.execute(
                    verify_query,
                    {"valid_voices": tuple(REALTIME_VOICES)}
                ).scalar()
                
                if remaining > 0:
                    print(f"⚠️ WARNING: {remaining} businesses still have invalid voices!")
                    trans.rollback()
                    return
                
                # Commit transaction
                trans.commit()
                print("\n🎉 Migration completed successfully!")
                print("✅ All businesses now have valid Realtime voices")
                
            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        sys.exit(1)
    
    finally:
        engine.dispose()

if __name__ == '__main__':
    print("=" * 70)
    print("🎤 Voice Cleanup Migration")
    print("=" * 70)
    run_migration()
    print("=" * 70)
