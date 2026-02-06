"""
Backfill canonical_key for existing WhatsAppConversation records and merge duplicates

This script:
1. Populates canonical_key for all existing conversations
2. Identifies and merges duplicate conversations
3. Ensures data integrity and prevents future duplicates

BUILD 138: Conversation Deduplication
"""

import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from server.db import db
from server.models_sql import WhatsAppConversation, WhatsAppMessage, Lead
from server.utils.whatsapp_utils import get_canonical_conversation_key
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def populate_canonical_keys(dry_run: bool = True) -> int:
    """
    Populate canonical_key for all WhatsAppConversation records
    
    Args:
        dry_run: If True, only show what would be updated
        
    Returns:
        Number of records updated
    """
    logger.info("=" * 80)
    logger.info("STEP 1: Populating canonical_key for existing conversations")
    logger.info("=" * 80)
    
    # Get all conversations without canonical_key
    conversations = WhatsAppConversation.query.filter(
        WhatsAppConversation.canonical_key.is_(None)
    ).all()
    
    logger.info(f"Found {len(conversations)} conversations without canonical_key")
    
    updated_count = 0
    error_count = 0
    
    for conv in conversations:
        try:
            # Get phone_e164 from lead or from customer_number
            phone_e164 = None
            
            if conv.lead_id:
                lead = Lead.query.get(conv.lead_id)
                if lead:
                    phone_e164 = lead.phone_e164
            
            # Fallback to customer_number/customer_wa_id
            if not phone_e164:
                phone_raw = conv.customer_number or conv.customer_wa_id
                if phone_raw:
                    # Normalize to E.164
                    if not phone_raw.startswith('+'):
                        phone_e164 = f"+{phone_raw.replace('@s.whatsapp.net', '').strip()}"
                    else:
                        phone_e164 = phone_raw
            
            # Generate canonical key
            if conv.lead_id or phone_e164:
                canonical_key = get_canonical_conversation_key(
                    business_id=conv.business_id,
                    lead_id=conv.lead_id,
                    phone_e164=phone_e164
                )
                
                if dry_run:
                    logger.info(
                        f"[DRY-RUN] Would update conversation {conv.id}: "
                        f"canonical_key={canonical_key} "
                        f"(business_id={conv.business_id}, lead_id={conv.lead_id}, phone={phone_e164})"
                    )
                else:
                    conv.canonical_key = canonical_key
                    logger.info(
                        f"✅ Updated conversation {conv.id}: canonical_key={canonical_key}"
                    )
                
                updated_count += 1
            else:
                logger.warning(
                    f"⚠️ Cannot generate canonical_key for conversation {conv.id}: "
                    f"no lead_id and no phone found"
                )
                error_count += 1
                
        except Exception as e:
            logger.error(f"❌ Error processing conversation {conv.id}: {e}")
            error_count += 1
    
    if not dry_run:
        try:
            db.session.commit()
            logger.info(f"✅ Committed {updated_count} updates to database")
        except Exception as e:
            logger.error(f"❌ Failed to commit changes: {e}")
            db.session.rollback()
            raise
    
    logger.info(f"\nSummary: {updated_count} updated, {error_count} errors")
    return updated_count


def find_duplicates() -> Dict[str, List[WhatsAppConversation]]:
    """
    Find duplicate conversations with the same canonical_key
    
    Returns:
        Dict mapping canonical_key to list of duplicate conversations
    """
    logger.info("=" * 80)
    logger.info("STEP 2: Finding duplicate conversations")
    logger.info("=" * 80)
    
    # Query to find canonical_keys with multiple conversations
    duplicate_keys_query = text("""
        SELECT canonical_key, COUNT(*) as count
        FROM whatsapp_conversation
        WHERE canonical_key IS NOT NULL
        GROUP BY canonical_key
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    
    result = db.session.execute(duplicate_keys_query)
    duplicate_keys = [(row[0], row[1]) for row in result]
    
    logger.info(f"Found {len(duplicate_keys)} canonical_keys with duplicates")
    
    duplicates_map = {}
    
    for canonical_key, count in duplicate_keys:
        conversations = WhatsAppConversation.query.filter_by(
            canonical_key=canonical_key
        ).order_by(WhatsAppConversation.last_message_at.desc()).all()
        
        duplicates_map[canonical_key] = conversations
        logger.info(
            f"  {canonical_key}: {count} conversations "
            f"(IDs: {[c.id for c in conversations]})"
        )
    
    return duplicates_map


def merge_duplicate_conversations(
    duplicates: Dict[str, List[WhatsAppConversation]],
    dry_run: bool = True
) -> int:
    """
    Merge duplicate conversations into a single primary conversation
    
    Strategy:
    1. Choose primary: most recent conversation (by last_message_at)
    2. Move all messages from duplicates to primary
    3. Close and mark duplicate conversations
    4. Update any related records
    
    Args:
        duplicates: Dict mapping canonical_key to list of duplicate conversations
        dry_run: If True, only show what would be merged
        
    Returns:
        Number of conversations merged
    """
    logger.info("=" * 80)
    logger.info("STEP 3: Merging duplicate conversations")
    logger.info("=" * 80)
    
    merged_count = 0
    
    for canonical_key, conversations in duplicates.items():
        if len(conversations) <= 1:
            continue
        
        # Primary: most recent conversation
        primary = conversations[0]
        duplicates_to_merge = conversations[1:]
        
        logger.info(f"\nProcessing canonical_key: {canonical_key}")
        logger.info(f"  Primary conversation: ID={primary.id}, last_message={primary.last_message_at}")
        logger.info(f"  Will merge {len(duplicates_to_merge)} duplicates: {[d.id for d in duplicates_to_merge]}")
        
        for dup in duplicates_to_merge:
            try:
                # Count messages in duplicate (for logging only)
                # Note: WhatsAppMessage doesn't have conversation_id foreign key
                # Messages are linked by business_id + to_number, so they don't need explicit migration
                # We only need to close the duplicate conversation - messages remain accessible
                message_count = WhatsAppMessage.query.filter_by(
                    business_id=dup.business_id,
                    to_number=dup.customer_number
                ).count()
                
                if dry_run:
                    logger.info(
                        f"  [DRY-RUN] Would merge conversation {dup.id} "
                        f"({message_count} messages) into primary {primary.id}"
                    )
                else:
                    # Note: WhatsAppMessage doesn't have conversation_id foreign key
                    # Messages are linked by business_id + to_number
                    # So we just need to close the duplicate conversation
                    
                    # Close duplicate
                    dup.is_open = False
                    dup.summary_created = True
                    dup.updated_at = datetime.utcnow()
                    
                    # Optionally add a note that it was merged
                    if not dup.summary:
                        dup.summary = f"Merged into conversation {primary.id} (duplicate removed)"
                    
                    logger.info(f"  ✅ Closed duplicate conversation {dup.id}")
                
                merged_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ Error merging conversation {dup.id}: {e}")
        
        # Update primary conversation metadata
        if not dry_run:
            try:
                # Ensure primary has the most recent data
                primary.updated_at = datetime.utcnow()
                
                # If primary doesn't have lead_id but duplicate does, copy it
                for dup in duplicates_to_merge:
                    if dup.lead_id and not primary.lead_id:
                        primary.lead_id = dup.lead_id
                        logger.info(f"  ✅ Updated primary {primary.id} with lead_id={dup.lead_id}")
                
            except Exception as e:
                logger.error(f"  ❌ Error updating primary {primary.id}: {e}")
    
    if not dry_run:
        try:
            db.session.commit()
            logger.info(f"\n✅ Committed merge of {merged_count} duplicate conversations")
        except Exception as e:
            logger.error(f"❌ Failed to commit merge: {e}")
            db.session.rollback()
            raise
    
    logger.info(f"\nSummary: {merged_count} duplicate conversations processed")
    return merged_count


def add_unique_constraint(dry_run: bool = True) -> bool:
    """
    Add unique constraint on (business_id, canonical_key)
    
    This prevents future duplicates at the database level.
    
    Args:
        dry_run: If True, only show the SQL that would be executed
        
    Returns:
        True if successful
    """
    logger.info("=" * 80)
    logger.info("STEP 4: Adding unique constraint")
    logger.info("=" * 80)
    
    constraint_name = "uq_whatsapp_conversation_canonical_key"
    
    # Check if constraint already exists
    check_query = text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'whatsapp_conversation' 
        AND constraint_name = :constraint_name
    """)
    
    result = db.session.execute(check_query, {"constraint_name": constraint_name})
    exists = result.fetchone() is not None
    
    if exists:
        logger.info(f"✅ Unique constraint '{constraint_name}' already exists")
        return True
    
    constraint_sql = f"""
        ALTER TABLE whatsapp_conversation
        ADD CONSTRAINT {constraint_name}
        UNIQUE (business_id, canonical_key)
    """
    
    if dry_run:
        logger.info(f"[DRY-RUN] Would execute SQL:")
        logger.info(constraint_sql)
    else:
        try:
            db.session.execute(text(constraint_sql))
            db.session.commit()
            logger.info(f"✅ Added unique constraint '{constraint_name}'")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to add unique constraint: {e}")
            db.session.rollback()
            return False
    
    return True


def main():
    """
    Main function to run the backfill and merge process
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backfill canonical keys and merge duplicate conversations'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually execute the changes (default is dry-run)'
    )
    parser.add_argument(
        '--skip-backfill',
        action='store_true',
        help='Skip backfilling canonical keys'
    )
    parser.add_argument(
        '--skip-merge',
        action='store_true',
        help='Skip merging duplicates'
    )
    parser.add_argument(
        '--skip-constraint',
        action='store_true',
        help='Skip adding unique constraint'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        logger.info("🔍 DRY-RUN MODE - No changes will be made")
        logger.info("Use --execute to apply changes")
    else:
        logger.info("⚠️ EXECUTE MODE - Changes will be written to database")
    
    logger.info("")
    
    try:
        # Initialize Flask app context
        from server.app_factory import create_app
        app = create_app()
        
        with app.app_context():
            # Step 1: Backfill canonical keys
            if not args.skip_backfill:
                updated = populate_canonical_keys(dry_run=dry_run)
                logger.info(f"\n✅ Backfill complete: {updated} records updated\n")
            
            # Step 2: Find duplicates
            duplicates = find_duplicates()
            logger.info(f"\n✅ Found {len(duplicates)} sets of duplicates\n")
            
            # Step 3: Merge duplicates
            if not args.skip_merge and duplicates:
                merged = merge_duplicate_conversations(duplicates, dry_run=dry_run)
                logger.info(f"\n✅ Merge complete: {merged} duplicates processed\n")
            
            # Step 4: Add unique constraint (only if not dry-run)
            if not args.skip_constraint:
                constraint_added = add_unique_constraint(dry_run=dry_run)
                if constraint_added:
                    logger.info(f"\n✅ Unique constraint ready\n")
            
            logger.info("=" * 80)
            logger.info("✅ PROCESS COMPLETE")
            logger.info("=" * 80)
            
            if dry_run:
                logger.info("\nTo apply these changes, run with --execute flag")
    
    except Exception as e:
        logger.error(f"❌ Process failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
