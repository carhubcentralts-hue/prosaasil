import React from 'react';
import { ArrowRight, Shield } from 'lucide-react';
import { Link } from 'react-router-dom';

export function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Back to Login */}
        <Link 
          to="/login" 
          className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-6"
        >
          <ArrowRight className="w-4 h-4" />
          חזרה לדף הכניסה
        </Link>
        
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <Shield className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">מדיניות פרטיות</h1>
              <p className="text-sm text-slate-500">עדכון אחרון: ינואר 2026</p>
            </div>
          </div>
        </div>
        
        {/* Content */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8 space-y-6">
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">1. מבוא</h2>
            <p className="text-slate-600 leading-relaxed">
              ProSaaS CRM ("המערכת", "אנחנו", "שלנו") מחויבת להגנה על פרטיות המשתמשים שלנו. 
              מדיניות פרטיות זו מסבירה כיצד אנו אוספים, משתמשים ומגנים על המידע שלכם.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">2. מידע שאנו אוספים</h2>
            <p className="text-slate-600 leading-relaxed mb-2">אנו אוספים את סוגי המידע הבאים:</p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li><strong>מידע חשבון:</strong> שם, כתובת מייל, מספר טלפון</li>
              <li><strong>מידע עסקי:</strong> נתוני לידים, שיחות, הודעות WhatsApp</li>
              <li><strong>מידע טכני:</strong> כתובת IP, סוג דפדפן, זמני גישה</li>
              <li><strong>תקשורת:</strong> הקלטות שיחות (באישורכם), תמלולים</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">3. שימוש במידע</h2>
            <p className="text-slate-600 leading-relaxed mb-2">אנו משתמשים במידע שלכם כדי:</p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li>לספק ולתפעל את שירותי המערכת</li>
              <li>לשפר את חוויית המשתמש</li>
              <li>לשלוח עדכונים והתראות חשובות</li>
              <li>לעמוד בדרישות חוקיות ורגולטוריות</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">4. שיתוף מידע</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו לא מוכרים את המידע האישי שלכם. אנו משתפים מידע רק עם:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4 mt-2">
              <li>ספקי שירות הכרחיים (אירוח, תקשורת)</li>
              <li>רשויות חוק כאשר נדרש על פי דין</li>
              <li>צדדים שלישיים באישורכם המפורש</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">5. אבטחת מידע</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו מיישמים אמצעי אבטחה מתקדמים להגנה על המידע שלכם, כולל:
            </p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4 mt-2">
              <li>הצפנת נתונים בתעבורה (TLS/SSL)</li>
              <li>הצפנת נתונים באחסון</li>
              <li>בקרות גישה מבוססות תפקידים</li>
              <li>מעקב ואודיט פעילות</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">6. זכויותיכם</h2>
            <p className="text-slate-600 leading-relaxed mb-2">על פי חוק הגנת הפרטיות, יש לכם את הזכות:</p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li>לגשת למידע האישי שלכם</li>
              <li>לתקן מידע שגוי</li>
              <li>למחוק את המידע שלכם ("הזכות להישכח")</li>
              <li>להגביל את עיבוד המידע</li>
              <li>להעביר את המידע שלכם (ניידות מידע)</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">7. שמירת מידע</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו שומרים את המידע שלכם למשך הזמן הנדרש למטרות שלשמן נאסף, 
              או כנדרש על פי חוק. הקלטות שיחות נמחקות אוטומטית לאחר 7 ימים 
              אלא אם כן נדרשת שמירה ארוכה יותר.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">8. יצירת קשר</h2>
            <p className="text-slate-600 leading-relaxed">
              לשאלות בנושא פרטיות או למימוש זכויותיכם, ניתן לפנות אלינו בכתובת: 
              <a href="mailto:privacy@prosaas.co.il" className="text-blue-600 hover:underline mr-1">
                privacy@prosaas.co.il
              </a>
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">9. עדכונים למדיניות</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו עשויים לעדכן מדיניות זו מעת לעת. נודיע לכם על שינויים משמעותיים 
              באמצעות הודעה במערכת או בדוא"ל.
            </p>
          </section>
        </div>
        
        {/* Footer Links */}
        <div className="mt-6 text-center text-sm text-slate-500">
          <Link to="/terms" className="text-blue-600 hover:underline ml-4">תנאי שימוש</Link>
          <Link to="/login" className="text-blue-600 hover:underline">כניסה למערכת</Link>
        </div>
      </div>
    </div>
  );
}
