#!/bin/bash
# Quick ARI registration verification script

echo "🔍 בודק רישום ARI..."
echo "================================"

# Check if Asterisk container is running
if ! docker ps | grep -q prosaas-asterisk; then
    echo "❌ Asterisk לא רץ"
    echo "הרץ: docker-compose -f docker-compose.sip.yml up -d asterisk"
    exit 1
fi

echo "✅ Asterisk רץ"
echo ""

# Check Stasis apps
echo "📋 Stasis Apps רשומים:"
docker exec prosaas-asterisk asterisk -rx "stasis show apps" 2>/dev/null

echo ""
echo "🔍 בדיקה אם prosaas_ai רשום:"
if docker exec prosaas-asterisk asterisk -rx "stasis show apps" 2>/dev/null | grep -q "prosaas_ai"; then
    echo "✅ prosaas_ai רשום ב-Asterisk!"
    echo ""
    echo "📊 פרטים:"
    docker exec prosaas-asterisk asterisk -rx "stasis show app prosaas_ai" 2>/dev/null
else
    echo "❌ prosaas_ai לא רשום!"
    echo ""
    echo "🔧 תיקונים אפשריים:"
    echo "1. ודא ש-backend רץ:"
    echo "   docker-compose -f docker-compose.sip.yml ps backend"
    echo ""
    echo "2. בדוק logs של backend:"
    echo "   docker-compose -f docker-compose.sip.yml logs backend | grep ARI"
    echo ""
    echo "3. ודא ש-ARI_APP_NAME מוגדר:"
    echo "   docker exec prosaas-backend env | grep ARI"
fi

echo ""
echo "================================"
