import React from 'react';
import { ArrowRight, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';

export function TermsOfServicePage() {
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
            <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <FileText className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">תנאי שימוש</h1>
              <p className="text-sm text-slate-500">עדכון אחרון: ינואר 2025</p>
            </div>
          </div>
        </div>
        
        {/* Content */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8 space-y-6">
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">1. הסכמה לתנאים</h2>
            <p className="text-slate-600 leading-relaxed">
              בשימוש במערכת ProSaaS CRM ("המערכת"), אתם מסכימים לתנאי השימוש הבאים. 
              אם אינכם מסכימים לתנאים אלה, אנא הימנעו משימוש במערכת.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">2. תיאור השירות</h2>
            <p className="text-slate-600 leading-relaxed">
              המערכת מספקת פלטפורמת CRM מתקדמת הכוללת ניהול לידים, שיחות טלפון חכמות עם AI, 
              אינטגרציית WhatsApp, ניהול משימות, ועוד. השירותים עשויים להשתנות מעת לעת.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">3. חשבון משתמש</h2>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li>אתם אחראים לשמירת סודיות פרטי הגישה שלכם</li>
              <li>עליכם לדווח מיד על כל שימוש לא מורשה בחשבונכם</li>
              <li>אתם אחראים לכל הפעילות המתבצעת תחת החשבון שלכם</li>
              <li>נדרש גיל 18 ומעלה לשימוש במערכת</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">4. שימוש מותר</h2>
            <p className="text-slate-600 leading-relaxed mb-2">אתם מתחייבים להשתמש במערכת רק למטרות חוקיות ובאופן שאינו:</p>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li>מפר זכויות קניין רוחני של צדדים שלישיים</li>
              <li>מכיל תוכן בלתי חוקי, מטריד, או פוגעני</li>
              <li>מנסה לגשת למערכות ללא הרשאה</li>
              <li>משבש את פעילות המערכת או השרתים</li>
              <li>משמש לספאם או שליחת הודעות לא רצויות</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">5. קניין רוחני</h2>
            <p className="text-slate-600 leading-relaxed">
              כל הזכויות במערכת, כולל קוד, עיצוב, תוכן וטכנולוגיות, שייכות ל-ProSaaS. 
              אין להעתיק, לשכפל, או להפיץ כל חלק מהמערכת ללא אישור בכתב.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">6. תשלומים</h2>
            <ul className="list-disc list-inside space-y-2 text-slate-600 mr-4">
              <li>התשלום על השירותים ייעשה בהתאם לתוכנית שנבחרה</li>
              <li>המחירים עשויים להשתנות עם הודעה מראש של 30 יום</li>
              <li>אין החזרים על תקופות שימוש שחלפו</li>
              <li>אי תשלום עלול לגרום להשעיית החשבון</li>
            </ul>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">7. הקלטות ותמלולים</h2>
            <p className="text-slate-600 leading-relaxed">
              באחריותכם לוודא שיש לכם את כל האישורים הנדרשים להקלטת שיחות בהתאם לחוק. 
              המערכת מספקת את הכלים הטכניים בלבד ואינה אחראית לעמידה בדרישות החוק.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">8. הגבלת אחריות</h2>
            <p className="text-slate-600 leading-relaxed">
              המערכת מסופקת "כמות שהיא" (AS IS). אנו לא נישא באחריות לנזקים עקיפים, 
              מיוחדים, או תוצאתיים הנובעים משימוש במערכת, כולל אובדן נתונים או הפסדים עסקיים.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">9. זמינות השירות</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו שואפים לספק שירות זמין 24 שעות ביממה, אך אין אנו מתחייבים לזמינות מושלמת. 
              תחזוקה מתוכננת תתואם מראש ככל האפשר.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">10. סיום השירות</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו שומרים על הזכות להשעות או לסגור חשבונות המפרים את תנאי השימוש. 
              תוכלו לסיים את השימוש בכל עת על ידי פנייה לתמיכה.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">11. שינויים בתנאים</h2>
            <p className="text-slate-600 leading-relaxed">
              אנו שומרים על הזכות לעדכן תנאים אלה. שינויים משמעותיים יפורסמו באתר 
              ויכנסו לתוקף 30 יום לאחר הפרסום.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">12. דין וסמכות שיפוט</h2>
            <p className="text-slate-600 leading-relaxed">
              תנאים אלה כפופים לדין הישראלי. סמכות השיפוט הבלעדית לכל סכסוך 
              נתונה לבתי המשפט המוסמכים במחוז תל אביב-יפו.
            </p>
          </section>
          
          <section>
            <h2 className="text-xl font-semibold text-slate-900 mb-3">13. יצירת קשר</h2>
            <p className="text-slate-600 leading-relaxed">
              לשאלות בנוגע לתנאי השימוש, ניתן לפנות אלינו בכתובת: 
              <a href="mailto:legal@prosaas.co.il" className="text-blue-600 hover:underline mr-1">
                legal@prosaas.co.il
              </a>
            </p>
          </section>
        </div>
        
        {/* Footer Links */}
        <div className="mt-6 flex justify-center items-center gap-4 text-sm">
          <Link to="/privacy" className="text-blue-600 hover:underline px-3 py-2">מדיניות פרטיות</Link>
          <span className="text-slate-300">|</span>
          <Link to="/login" className="text-blue-600 hover:underline px-3 py-2">כניסה למערכת</Link>
        </div>
      </div>
    </div>
  );
}
