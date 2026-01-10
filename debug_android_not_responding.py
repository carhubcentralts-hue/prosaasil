#!/usr/bin/env python3
"""
בדיקה מעמיקה: למה הבוט לא עונה להודעות מאנדרואיד?

נבדוק:
1. האם ההודעה מגיעה ל-Baileys? (לוגים)
2. האם ההודעה מסומנת בטעות כ-fromMe=true?
3. האם ההודעה נשלחת ל-Flask?
4. האם Flask מזהה את ההודעה?
5. האם יש הבדל בין אנדרואיד לאייפון?
"""

import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')


def test_fromme_detection_logic():
    """בדיקה: האם הגיוני שהודעה מאנדרואיד תסומן כ-fromMe=true?"""
    print("=" * 70)
    print("🔍 בדיקה 1: לוגיקת fromMe")
    print("=" * 70)
    
    # סימולציה של הודעות שמגיעות
    test_messages = [
        {
            'desc': 'הודעה מאייפון (לקוח)',
            'key': {'fromMe': False, 'remoteJid': '972501234567@s.whatsapp.net'},
            'message': {'conversation': 'שלום'},
            'expected_forward': True
        },
        {
            'desc': 'הודעה מאנדרואיד (לקוח)',
            'key': {'fromMe': False, 'remoteJid': '972501234567@s.whatsapp.net'},
            'message': {'extendedTextMessage': {'text': 'שלום'}},
            'expected_forward': True
        },
        {
            'desc': 'הודעה שהבוט שלח (יוצאת)',
            'key': {'fromMe': True, 'remoteJid': '972501234567@s.whatsapp.net'},
            'message': {'conversation': 'היי, איך אני יכול לעזור?'},
            'expected_forward': False
        },
        {
            'desc': 'הודעה מאנדרואיד שנראית כמו יוצאת (bug?)',
            'key': {'fromMe': True, 'remoteJid': '972501234567@s.whatsapp.net'},
            'message': {'extendedTextMessage': {'text': 'למה אתה לא עונה?'}},
            'expected_forward': False,
            'potential_bug': True
        }
    ]
    
    for i, msg in enumerate(test_messages, 1):
        from_me = msg['key'].get('fromMe', False)
        should_forward = not from_me
        
        status = "✅ עובר ל-Flask" if should_forward else "⏭️ מדלג (fromMe=true)"
        
        if msg.get('potential_bug'):
            print(f"\n🔴 תרחיש {i}: {msg['desc']}")
            print(f"   fromMe: {from_me}")
            print(f"   פעולה: {status}")
            print(f"   ⚠️ זו אולי הבעיה! אם אנדרואיד שולח הודעות עם fromMe=true בטעות")
        else:
            print(f"\n✅ תרחיש {i}: {msg['desc']}")
            print(f"   fromMe: {from_me}")
            print(f"   פעולה: {status}")
    
    return True


def test_android_vs_iphone_message_structure():
    """בדיקה: האם יש הבדל במבנה ההודעות?"""
    print("\n" + "=" * 70)
    print("🔍 בדיקה 2: הבדלים במבנה הודעות אנדרואיד vs אייפון")
    print("=" * 70)
    
    iphone_msg = {
        'key': {'fromMe': False, 'remoteJid': '972501234567@s.whatsapp.net'},
        'message': {'conversation': 'שלום'},
        'pushName': 'יוסי'
    }
    
    android_msg = {
        'key': {'fromMe': False, 'remoteJid': '972501234567@s.whatsapp.net'},
        'message': {'extendedTextMessage': {'text': 'שלום'}},
        'pushName': 'יוסי'
    }
    
    print("\n📱 הודעה מאייפון:")
    print(f"   fromMe: {iphone_msg['key']['fromMe']}")
    print(f"   message keys: {list(iphone_msg['message'].keys())}")
    print(f"   תוכן: conversation = '{iphone_msg['message']['conversation']}'")
    
    print("\n🤖 הודעה מאנדרואיד:")
    print(f"   fromMe: {android_msg['key']['fromMe']}")
    print(f"   message keys: {list(android_msg['message'].keys())}")
    print(f"   תוכן: extendedTextMessage.text = '{android_msg['message']['extendedTextMessage']['text']}'")
    
    # בדיקה: האם שניהם יעברו את הפילטר?
    iphone_passes = not iphone_msg['key']['fromMe']
    android_passes = not android_msg['key']['fromMe']
    
    print(f"\n✅ אייפון יעבור פילטר: {iphone_passes}")
    print(f"✅ אנדרואיד יעבור פילטר: {android_passes}")
    
    if iphone_passes and android_passes:
        print("\n🎉 שני הסוגים אמורים לעבור!")
    else:
        print("\n🔴 בעיה! אחד מהם לא עובר!")
    
    return True


def test_message_echo_detection():
    """בדיקה: האם יש בעיה עם echo של הודעות שהבוט שלח?"""
    print("\n" + "=" * 70)
    print("🔍 בדיקה 3: זיהוי הדהוד (Echo) של הודעות")
    print("=" * 70)
    
    # תרחיש: הבוט שולח הודעה, ואז היא חוזרת אליו
    bot_sends = {
        'desc': 'הבוט שולח הודעה (אמור להיות fromMe=true)',
        'key': {'fromMe': True, 'remoteJid': '972501234567@s.whatsapp.net', 'id': 'ABC123'},
        'message': {'conversation': 'היי, איך אני יכול לעזור?'}
    }
    
    echo_back = {
        'desc': 'אותה הודעה חוזרת כהדהוד (bug אם fromMe=false!)',
        'key': {'fromMe': False, 'remoteJid': '972501234567@s.whatsapp.net', 'id': 'ABC123'},
        'message': {'conversation': 'היי, איך אני יכול לעזור?'}
    }
    
    print(f"\n1️⃣ {bot_sends['desc']}")
    print(f"   fromMe: {bot_sends['key']['fromMe']} ✅")
    print(f"   messageId: {bot_sends['key']['id']}")
    
    print(f"\n2️⃣ {echo_back['desc']}")
    print(f"   fromMe: {echo_back['key']['fromMe']} 🔴")
    print(f"   messageId: {echo_back['key']['id']} (זהה!)")
    print(f"   תוכן: {echo_back['message']['conversation']}")
    
    print("\n⚠️ אם זה קורה, הבוט יחשוב שזו הודעה חדשה מהלקוח!")
    print("   הפתרון: בדיקה של messageId או timestamp לזהות הדהודים")
    
    return True


def test_potential_android_bug():
    """בדיקה: תרחיש אפשרי - אנדרואיד שולח fromMe=true בטעות"""
    print("\n" + "=" * 70)
    print("🔍 בדיקה 4: תרחיש Bug אפשרי באנדרואיד")
    print("=" * 70)
    
    print("\n🤔 תרחיש אפשרי:")
    print("   1. משתמש אנדרואיד שולח הודעה")
    print("   2. WhatsApp/Baileys מסמן אותה בטעות כ-fromMe=true")
    print("   3. Baileys מדלג עליה (חושב שזו הודעה שהבוט שלח)")
    print("   4. הבוט לא עונה")
    
    print("\n📊 איך לזהות:")
    print("   - הפעל לוגים מפורטים (כבר עשינו!)")
    print("   - שלח הודעה מאנדרואיד")
    print("   - בדוק בלוגים:")
    print("     • האם יש 'Message 0: fromMe=true' להודעה מהלקוח?")
    print("     • האם יש '⏭️ Skipping X outgoing message(s)'?")
    print("     • האם אין '📨 X incoming message(s) detected'?")
    
    print("\n🔧 הפתרון:")
    print("   אם זה קורה, צריך לבדוק גם:")
    print("   - האם remoteJid הוא של הלקוח (לא שלנו)")
    print("   - האם pushName הוא של הלקוח")
    print("   - האם timestamp מתאים לכניסה חדשה")
    
    return True


def test_flask_receives_message():
    """בדיקה: מה קורה כשההודעה מגיעה ל-Flask?"""
    print("\n" + "=" * 70)
    print("🔍 בדיקה 5: קבלת הודעה ב-Flask")
    print("=" * 70)
    
    # סימולציה של payload שמגיע ל-Flask
    flask_payload = {
        'tenantId': 'business_1',
        'payload': {
            'messages': [
                {
                    'key': {
                        'fromMe': False,
                        'remoteJid': '972501234567@s.whatsapp.net'
                    },
                    'message': {
                        'extendedTextMessage': {
                            'text': 'שלום, אני רוצה לקבוע תור'
                        }
                    }
                }
            ]
        }
    }
    
    print("\n📦 Payload שמגיע ל-Flask:")
    msg = flask_payload['payload']['messages'][0]
    print(f"   tenantId: {flask_payload['tenantId']}")
    print(f"   messages count: {len(flask_payload['payload']['messages'])}")
    print(f"   fromMe: {msg['key']['fromMe']}")
    print(f"   remoteJid: {msg['key']['remoteJid']}")
    print(f"   message type: extendedTextMessage")
    print(f"   text: {msg['message']['extendedTextMessage']['text']}")
    
    # בדיקה: האם Flask יוכל לחלץ את הטקסט?
    message_obj = msg.get('message', {})
    message_text = None
    
    if message_obj.get('conversation'):
        message_text = message_obj.get('conversation')
    elif message_obj.get('extendedTextMessage'):
        message_text = message_obj.get('extendedTextMessage', {}).get('text', '')
    
    if message_text:
        print(f"\n✅ Flask מצליח לחלץ טקסט: '{message_text}'")
        print("   הבוט אמור לעבד את ההודעה ולענות!")
    else:
        print(f"\n🔴 Flask לא מצליח לחלץ טקסט!")
        print("   זו הסיבה שהבוט לא עונה!")
    
    return True


def main():
    """הרץ את כל הבדיקות"""
    print("\n🚨 בדיקה מעמיקה: למה הבוט לא עונה להודעות מאנדרואיד?")
    print("=" * 70)
    
    tests = [
        test_fromme_detection_logic,
        test_android_vs_iphone_message_structure,
        test_message_echo_detection,
        test_potential_android_bug,
        test_flask_receives_message,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"\n❌ שגיאה: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("📋 סיכום המלצות:")
    print("=" * 70)
    print("\n1. בדוק לוגים של Baileys כשמגיעה הודעה מאנדרואיד:")
    print("   docker logs -f prosaas-baileys")
    print("   חפש: 'Message X: fromMe=...'")
    
    print("\n2. אם fromMe=true להודעות מאנדרואיד - זה Bug!")
    print("   פתרון: להוסיף בדיקה נוספת של remoteJid")
    
    print("\n3. אם fromMe=false אבל אין '📨 incoming message(s) detected':")
    print("   פתרון: בעיה בפילטר, צריך לבדוק את הלוגיקה")
    
    print("\n4. אם יש '📨 incoming' אבל אין '✅ Webhook→Flask success':")
    print("   פתרון: בעיה בקריאה ל-Flask, בדוק network/auth")
    
    print("\n5. אם יש 'Webhook→Flask success' אבל הבוט לא עונה:")
    print("   פתרון: בעיה ב-Flask parsing או AI response")
    
    print("\n" + "=" * 70)
    print("🔧 פקודות debug:")
    print("=" * 70)
    print("\n# ראה לוגים בזמן אמת")
    print("docker logs -f prosaas-baileys | grep -E 'Message|incoming|fromMe'")
    
    print("\n# שלח הודעת בדיקה")
    print("# שלח מטלפון אנדרואיד: 'בדיקה 123'")
    print("# חפש בלוגים את המילה 'בדיקה'")
    
    print("\n# בדוק סטטוס חיבור")
    print("curl -H 'X-Internal-Secret: $SECRET' http://localhost:3300/whatsapp/business_1/status | jq")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
