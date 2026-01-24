"""
Migration: Normalize Gemini voice names to lowercase
Ensures all Gemini voices in the database are lowercase as required by Gemini API.
Also validates that voice names are in the allowed list and falls back to default if invalid.

This prevents INVALID_ARGUMENT errors from Gemini TTS API.

Background:
- Gemini API requires lowercase voice names (e.g., "pulcherrima", not "Pulcherrima")
- Old voice catalog had mixed case (e.g., "Puck", "Charon")
- New voice catalog uses only lowercase (e.g., "puck", "charon", "pulcherrima")
"""
import os
import sys
from sqlalchemy import create_engine, text

# Valid Gemini voices (lowercase only) - from requirements
VALID_GEMINI_VOICES = [
    "achernar", "achird", "algenib", "algieba", "alnilam",
    "aoede", "autonoe", "callirrhoe", "charon", "despina",
    "enceladus", "erinome", "fenrir", "gacrux", "iapetus",
    "kore", "laomedeia", "leda", "orus", "puck",
    "pulcherrima", "rasalgethi", "sadachbia", "sadaltager", "schedar",
    "sulafat", "umbriel", "vindemiatrix", "zephyr", "zubenelgenubi"
]

# Default Gemini voice
DEFAULT_GEMINI_VOICE = "pulcherrima"

# Default OpenAI voice (for reference)
DEFAULT_OPENAI_VOICE = "alloy"


def run_migration():
    """Normalize Gemini voice names to lowercase"""
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)
    
    print("🔧 Starting Gemini voice normalization migration...")
    print(f"✅ Valid Gemini voices: {len(VALID_GEMINI_VOICES)} voices")
    print(f"🎤 Default Gemini voice: {DEFAULT_GEMINI_VOICE}")
    
    # Create engine
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Check which columns exist
                check_columns = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'businesses' 
                    AND column_name IN ('voice_name', 'voice_id', 'tts_voice_id', 'ai_provider', 'tts_provider')
                """)
                existing_columns = {row[0] for row in conn.execute(check_columns)}
                
                if not existing_columns:
                    print("ℹ️ No voice columns exist in businesses table - skipping migration")
                    trans.rollback()
                    return
                
                print(f"✅ Found columns: {', '.join(sorted(existing_columns))}")
                
                # Step 1: Get all businesses with Gemini provider
                print("\n📊 Finding businesses using Gemini...")
                
                gemini_conditions = []
                if 'ai_provider' in existing_columns:
                    gemini_conditions.append("ai_provider = 'gemini'")
                if 'tts_provider' in existing_columns:
                    gemini_conditions.append("tts_provider = 'gemini'")
                
                if not gemini_conditions:
                    print("ℹ️ No provider columns found - cannot identify Gemini users")
                    trans.rollback()
                    return
                
                query = text(f"""
                    SELECT id, business_name, ai_provider, voice_name, voice_id, tts_voice_id, tts_provider
                    FROM businesses
                    WHERE ({' OR '.join(gemini_conditions)})
                """)
                gemini_businesses = conn.execute(query).fetchall()
                
                print(f"  Found {len(gemini_businesses)} businesses using Gemini")
                
                if not gemini_businesses:
                    print("✅ No Gemini businesses found - nothing to migrate")
                    trans.rollback()
                    return
                
                # Step 2: Normalize voice names for each Gemini business
                updated_count = 0
                invalid_count = 0
                
                for business in gemini_businesses:
                    biz_id = business[0]
                    biz_name = business[1]
                    ai_provider = business[2] if len(business) > 2 else None
                    voice_name = business[3] if len(business) > 3 else None
                    voice_id = business[4] if len(business) > 4 else None
                    tts_voice_id = business[5] if len(business) > 5 else None
                    tts_provider = business[6] if len(business) > 6 else None
                    
                    # Determine which voice field to use (priority: voice_name > tts_voice_id > voice_id)
                    current_voice = voice_name or tts_voice_id or voice_id
                    
                    if not current_voice:
                        # No voice set, use default
                        new_voice = DEFAULT_GEMINI_VOICE
                        print(f"  • Business {biz_id} ({biz_name}): No voice set → {new_voice}")
                        invalid_count += 1
                    else:
                        # Normalize to lowercase
                        normalized_voice = current_voice.lower().strip()
                        
                        # Check if valid
                        if normalized_voice in VALID_GEMINI_VOICES:
                            new_voice = normalized_voice
                            if current_voice != new_voice:
                                print(f"  • Business {biz_id} ({biz_name}): '{current_voice}' → '{new_voice}' (normalized)")
                            else:
                                print(f"  • Business {biz_id} ({biz_name}): '{current_voice}' (already valid)")
                        else:
                            # Invalid voice, use default
                            new_voice = DEFAULT_GEMINI_VOICE
                            print(f"  ⚠️ Business {biz_id} ({biz_name}): '{current_voice}' → '{new_voice}' (invalid, using default)")
                            invalid_count += 1
                    
                    # Update all voice fields to ensure consistency
                    update_fields = []
                    if 'voice_name' in existing_columns:
                        update_fields.append("voice_name = :new_voice")
                    if 'voice_id' in existing_columns:
                        update_fields.append("voice_id = :new_voice")
                    if 'tts_voice_id' in existing_columns:
                        update_fields.append("tts_voice_id = :new_voice")
                    
                    if update_fields:
                        update_query = text(f"""
                            UPDATE businesses
                            SET {', '.join(update_fields)}
                            WHERE id = :biz_id
                        """)
                        conn.execute(update_query, {"new_voice": new_voice, "biz_id": biz_id})
                        updated_count += 1
                
                # Commit transaction
                trans.commit()
                
                print("\n" + "="*60)
                print(f"✅ Migration completed successfully!")
                print(f"  • Total Gemini businesses: {len(gemini_businesses)}")
                print(f"  • Updated: {updated_count}")
                print(f"  • Invalid/missing voices fixed: {invalid_count}")
                print(f"  • Default voice used: {DEFAULT_GEMINI_VOICE}")
                print("="*60)
                
            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                raise
                
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("="*60)
    print("🔊 Gemini Voice Normalization Migration")
    print("="*60)
    run_migration()
