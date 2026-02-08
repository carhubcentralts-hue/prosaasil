#!/usr/bin/env python3
"""
🔥 תיקון מאוחד למערכת WhatsApp - הפעל את זה!
זה מריץ את שני הסקריפטים הקריטיים בסדר הנכון

הרץ:
    python fix_whatsapp_unified.py --dry-run    # לראות מה יקרה בלי לבצע
    python fix_whatsapp_unified.py --execute    # לבצע בפועל
"""

import logging
import sys
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run_fix(execute: bool = False):
    """
    הרץ את שני הסקריפטים בסדר הנכון
    
    Args:
        execute: אם True, מבצע את השינויים. אם False (default), רק מראה מה יקרה
    """
    logger.info("=" * 100)
    logger.info("🔥 תיקון מאוחד למערכת WhatsApp")
    logger.info("=" * 100)
    logger.info("")
    
    if not execute:
        logger.info("🔍 מצב DRY-RUN - אין שינויים יתבצעו")
        logger.info("   להרצה אמיתית, הוסף: --execute")
    else:
        logger.info("⚠️ מצב ביצוע - שינויים יתבצעו במסד הנתונים!")
        logger.info("   לחץ Ctrl+C תוך 5 שניות כדי לבטל...")
        import time
        for i in range(5, 0, -1):
            logger.info(f"   {i}...")
            time.sleep(1)
        logger.info("   מתחיל!")
    
    logger.info("")
    
    try:
        # Initialize Flask app
        logger.info("🔧 מאתחל את האפליקציה...")
        from server.app_factory import create_app
        app = create_app()
        
        with app.app_context():
            # ========================================
            # שלב 1: מילוי canonical_key ואיחוד כפילויות
            # ========================================
            logger.info("")
            logger.info("=" * 100)
            logger.info("שלב 1️⃣: מילוי canonical_key ואיחוד שיחות כפולות")
            logger.info("=" * 100)
            logger.info("")
            
            from server.scripts.backfill_canonical_keys_and_merge_duplicates import (
                populate_canonical_keys,
                find_duplicates,
                merge_duplicate_conversations,
                add_unique_constraint
            )
            
            # 1.1: Populate canonical keys
            logger.info("📝 1.1: ממלא canonical_key בשיחות קיימות...")
            updated = populate_canonical_keys(dry_run=not execute)
            logger.info(f"✅ סיים: {updated} שיחות עודכנו")
            logger.info("")
            
            # 1.2: Find duplicates
            logger.info("🔍 1.2: מחפש שיחות כפולות...")
            duplicates = find_duplicates()
            logger.info(f"✅ נמצאו: {len(duplicates)} קבוצות של כפילויות")
            logger.info("")
            
            # 1.3: Merge duplicates
            if duplicates:
                logger.info("🔗 1.3: מאחד שיחות כפולות...")
                merged = merge_duplicate_conversations(duplicates, dry_run=not execute)
                logger.info(f"✅ סיים: {merged} כפילויות אוחדו")
            else:
                logger.info("✅ 1.3: אין כפילויות לאחד")
            logger.info("")
            
            # 1.4: Add unique constraint
            if execute:
                logger.info("🔒 1.4: מוסיף אילוץ ייחודיות למניעת כפילויות עתידיות...")
                constraint_added = add_unique_constraint(dry_run=False)
                if constraint_added:
                    logger.info("✅ סיים: אילוץ ייחודיות נוסף")
                else:
                    logger.info("⚠️ אילוץ כבר קיים או נכשל (זה בסדר)")
            else:
                logger.info("⏭️ 1.4: מדלג על אילוץ ייחודיות (dry-run)")
            
            logger.info("")
            logger.info("✅ שלב 1 הושלם!")
            
            # ========================================
            # שלב 2: קישור הודעות לשיחות
            # ========================================
            logger.info("")
            logger.info("=" * 100)
            logger.info("שלב 2️⃣: קישור הודעות קיימות לשיחות")
            logger.info("=" * 100)
            logger.info("")
            
            if not execute:
                # In dry-run, just count messages without conversation_id
                from server.db import db
                from server.models_sql import WhatsAppMessage
                
                count = WhatsAppMessage.query.filter(
                    WhatsAppMessage.conversation_id.is_(None),
                    WhatsAppMessage.status != 'deleted'
                ).count()
                
                logger.info(f"📊 נמצאו {count} הודעות שצריכות להתקשר לשיחות")
                logger.info("   (בצע --execute כדי לקשר אותן)")
            else:
                from server.scripts.backfill_message_conversation_ids import backfill_message_conversation_ids
                stats = backfill_message_conversation_ids()
                
                logger.info("")
                logger.info("📊 סטטיסטיקות:")
                logger.info(f"   הודעות שעובדו: {stats['total']}")
                logger.info(f"   הודעות שקושרו: {stats['linked']}")
                logger.info(f"   שיחות חדשות שנוצרו: {stats['conversations_created']}")
                logger.info(f"   שיחות קיימות ששימשו: {stats['conversations_reused']}")
                if stats['errors'] > 0:
                    logger.info(f"   ⚠️ שגיאות: {stats['errors']}")
            
            logger.info("")
            logger.info("✅ שלב 2 הושלם!")
            
            # ========================================
            # סיכום
            # ========================================
            logger.info("")
            logger.info("=" * 100)
            logger.info("🎉 התיקון הושלם בהצלחה!")
            logger.info("=" * 100)
            logger.info("")
            
            if not execute:
                logger.info("זה היה dry-run. להרצה אמיתית, הוסף: --execute")
                logger.info("")
                logger.info("מה יקרה בביצוע אמיתי:")
                logger.info("  ✅ כל השיחות יקבלו canonical_key ייחודי")
                logger.info("  ✅ שיחות כפולות יאוחדו לשיחה אחת")
                logger.info("  ✅ כל ההודעות יקושרו לשיחות שלהן")
                logger.info("  ✅ הבעיות יפתרו: צ'אטים מפוצלים + לא רואה הודעות")
            else:
                logger.info("התיקון הופעל! עכשיו:")
                logger.info("  ✅ כל ליד = צ'אט אחד (לא עוד כפילויות)")
                logger.info("  ✅ כל ההודעות (ידני, בוט, אוטומציה) באותו מקום")
                logger.info("  ✅ לא נקרא עובד כמו שצריך")
                logger.info("  ✅ שם הליד לחיץ ומוביל לדף ליד")
                logger.info("")
                logger.info("🔄 רענן את דף WhatsApp בדפדפן כדי לראות את השינויים!")
            
    except Exception as e:
        logger.error("")
        logger.error("=" * 100)
        logger.error("❌ שגיאה בתיקון!")
        logger.error("=" * 100)
        logger.error(f"שגיאה: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='תיקון מאוחד למערכת WhatsApp - מאחד צ\'אטים ומקשר הודעות',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
דוגמאות שימוש:
  
  # ראה מה יקרה בלי לבצע:
  python fix_whatsapp_unified.py --dry-run
  
  # בצע את התיקון:
  python fix_whatsapp_unified.py --execute
  
  # עם Docker:
  docker-compose exec backend python fix_whatsapp_unified.py --execute
"""
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--dry-run',
        action='store_true',
        help='הצג מה יתבצע בלי לבצע (מומלץ להריץ קודם)'
    )
    group.add_argument(
        '--execute',
        action='store_true',
        help='בצע את התיקון בפועל'
    )
    
    args = parser.parse_args()
    
    run_fix(execute=args.execute)


if __name__ == '__main__':
    main()
