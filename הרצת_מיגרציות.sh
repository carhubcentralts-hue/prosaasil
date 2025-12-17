#!/bin/bash
# הרצת המיגרציות האוטומטית

echo "=================================================="
echo "🔧 הרצת מיגרציות - תיקון כפילות שיחות"
echo "=================================================="
echo ""
echo "המיגרציות כוללות:"
echo "  ✅ Migration 41a: parent_call_sid - מעקב אחר parent/child calls"
echo "  ✅ Migration 41b: twilio_direction - שמירת direction מקורי מTwilio"
echo ""
echo "=================================================="
echo ""

# אופציה 1: הרצה ידנית
echo "🚀 אופציה 1: הרצה ידנית"
echo "   python3 run_call_fix_migration.py"
echo ""

# אופציה 2: דרך מודול
echo "🚀 אופציה 2: דרך מודול מיגרציה"
echo "   python3 -m server.db_migrate"
echo ""

# אופציה 3: אוטומטי בהפעלת שרת
echo "🚀 אופציה 3: אוטומטי בהפעלת שרת (מומלץ)"
echo "   הוסף משתנה סביבה:"
echo "   export RUN_MIGRATIONS_ON_START=1"
echo ""
echo "   או בקובץ .env:"
echo "   RUN_MIGRATIONS_ON_START=1"
echo ""
echo "   ואז הפעל את השרת:"
echo "   python3 run_server.py"
echo ""

# אופציה 4: דרך API endpoint
echo "🚀 אופציה 4: דרך API endpoint (אחרי שהשרת רץ)"
echo "   curl -X POST http://localhost:5000/api/admin/run-migrations"
echo ""

echo "=================================================="
echo "✅ המיגרציות כבר נמצאות ב-server/db_migrate.py"
echo "   הן ירוצו אוטומטית בפעם הראשונה שהשרת יעלה"
echo "=================================================="
echo ""
echo "📊 לאחר הרצת המיגרציות, בדוק:"
echo "   SELECT column_name FROM information_schema.columns"
echo "   WHERE table_name = 'call_log'"
echo "   AND column_name IN ('parent_call_sid', 'twilio_direction');"
echo ""
echo "   צפוי לראות:"
echo "   - parent_call_sid"
echo "   - twilio_direction"
echo ""
