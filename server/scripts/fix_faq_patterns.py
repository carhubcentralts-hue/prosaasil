#!/usr/bin/env python3
"""
FAQ patterns_json Migration Script

Fixes malformed patterns_json data in the faqs table.
Converts double-escaped JSON strings to proper JSON arrays.

Usage:
    python server/scripts/fix_faq_patterns.py
"""
import os
import sys
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.models_sql import FAQ, db
from server.app_factory import create_app

app = create_app()

def normalize_patterns(payload):
    """
    Normalize patterns_json to ensure it's always a List[str]
    Same logic as routes_business_management.py
    """
    if payload is None or payload == "":
        return []
    
    if isinstance(payload, list):
        cleaned = [str(p).strip() for p in payload if p and str(p).strip()]
        return cleaned
    
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return []
        
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                cleaned = [str(p).strip() for p in parsed if p and str(p).strip()]
                return cleaned
            else:
                logger.warning(f"⚠️ WARNING: patterns_json is not a list: {type(parsed).__name__}")
                return []
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ WARNING: Invalid JSON in patterns_json: {e}")
            return []
    
    logger.warning(f"⚠️ WARNING: Unexpected patterns_json type: {type(payload).__name__}")
    return []

def fix_faq_patterns():
    """Fix all FAQ patterns_json entries"""
    with app.app_context():
        logger.info("🔍 Scanning all FAQs for malformed patterns_json...")
        
        faqs = FAQ.query.all()
        total_count = len(faqs)
        fixed_count = 0
        error_count = 0
        skipped_count = 0
        
        logger.info(f"📊 Found {total_count} total FAQs")
        
        for faq in faqs:
            try:
                original = faq.patterns_json
                
                # Check if already a proper list
                if isinstance(original, list):
                    skipped_count += 1
                    continue
                
                # Normalize
                normalized = normalize_patterns(original)
                
                # Update
                faq.patterns_json = normalized
                fixed_count += 1
                
                logger.info(f"✅ Fixed FAQ ID={faq.id} (business={faq.business_id})")
                logger.info(f"   Before: {repr(original)[:100]}")
                logger.info(f"   After:  {normalized}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ ERROR fixing FAQ ID={faq.id}: {e}")
        
        # Commit all changes
        if fixed_count > 0:
            try:
                db.session.commit()
                logger.info(f"\n✅ Successfully committed {fixed_count} fixes")
            except Exception as e:
                db.session.rollback()
                logger.error(f"\n❌ COMMIT FAILED: {e}")
                return
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("📊 MIGRATION SUMMARY")
        logger.info("="*50)
        logger.info(f"Total FAQs:   {total_count}")
        logger.info(f"✅ Fixed:     {fixed_count}")
        logger.info(f"⏭️  Skipped:   {skipped_count} (already correct)")
        logger.error(f"❌ Errors:    {error_count}")
        logger.info("="*50)
        
        # Invalidate cache for all affected businesses
        if fixed_count > 0:
            logger.info("\n🗑️  Invalidating FAQ cache for all businesses...")
            try:
                from server.services.faq_cache import faq_cache
                affected_businesses = set(faq.business_id for faq in faqs if faq.patterns_json)
                for business_id in affected_businesses:
                    faq_cache.invalidate(business_id)
                logger.info(f"✅ Invalidated cache for {len(affected_businesses)} businesses")
            except Exception as e:
                logger.error(f"⚠️ Cache invalidation failed: {e}")

if __name__ == "__main__":
    logger.info("🚀 Starting FAQ patterns_json migration...\n")
    fix_faq_patterns()
    logger.info("\n✅ Migration complete!")
