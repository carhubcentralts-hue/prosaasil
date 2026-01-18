/**
 * Forbidden Page - 403 Access Denied
 * הנחיית-על: דף אין הרשאה
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldOff, ArrowRight } from 'lucide-react';

export function ForbiddenPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-red-100 mb-4">
            <ShieldOff className="w-10 h-10 text-red-600" />
          </div>
          <h1 className="text-4xl font-bold text-slate-900 mb-2">
            אין הרשאה
          </h1>
          <p className="text-lg text-slate-600">
            לא נמצאו הרשאות לצפייה בדף זה
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">
            מה ניתן לעשות?
          </h2>
          <ul className="text-right text-slate-700 space-y-2">
            <li className="flex items-start">
              <span className="text-blue-600 ml-2">•</span>
              <span>פנה למנהל המערכת שלך לקבלת הרשאות</span>
            </li>
            <li className="flex items-start">
              <span className="text-blue-600 ml-2">•</span>
              <span>ודא שהדף פעיל עבור העסק שלך</span>
            </li>
            <li className="flex items-start">
              <span className="text-blue-600 ml-2">•</span>
              <span>בדוק שהתפקיד שלך מאפשר גישה לדף זה</span>
            </li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => navigate(-1)}
            className="px-6 py-3 bg-white border border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 transition-colors font-medium"
          >
            חזרה אחורה
          </button>
          <button
            onClick={() => navigate('/app/business/overview')}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2"
          >
            <ArrowRight className="w-5 h-5" />
            חזרה לדף הבית
          </button>
        </div>

        <p className="text-sm text-slate-500 mt-8">
          קוד שגיאה: 403 - Forbidden
        </p>
      </div>
    </div>
  );
}
