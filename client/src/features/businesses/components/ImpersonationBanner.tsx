import React from 'react';
import { AlertTriangle, X, LogOut, Shield } from 'lucide-react';
import { useBusinessActions } from '../useBusinessActions';
import { useImpersonation } from '../hooks/useImpersonation';

export function ImpersonationBanner() {
  const { isImpersonating, originalUser, impersonatedBusiness, exitImpersonation: hookExitImpersonation } = useImpersonation();
  const { isLoading } = useBusinessActions();

  // Don't render if not impersonating or missing data
  if (!isImpersonating || !originalUser || !impersonatedBusiness) {
    return null;
  }

  const handleExitImpersonation = async () => {
    try {
      await hookExitImpersonation();
    } catch (error) {
      console.error('שגיאה ביציאה מהתחזות:', error);
    }
  };

  return (
    <div className="bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-lg border-b-2 border-red-600" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-100" />
              <Shield className="h-5 w-5 text-orange-100" />
            </div>
            
            <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <span className="bg-orange-400 bg-opacity-30 px-2 py-1 rounded text-xs font-bold tracking-wide">
                  מצב התחזות
                </span>
                <span>אתה מתחזה לעסק</span>
                <span className="font-bold text-orange-100">"{impersonatedBusiness.name}"</span>
              </div>
              
              <div className="flex items-center gap-2 text-xs text-orange-100">
                <span>משתמש מקורי:</span>
                <span className="font-medium">{originalUser.name}</span>
                <span>({originalUser.email})</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleExitImpersonation}
            disabled={isLoading('exit-impersonation')}
            className="flex items-center gap-2 px-4 py-2 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-lg transition-all duration-200 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed group"
            data-testid="button-exit-impersonation"
          >
            {isLoading('exit-impersonation') ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                יוצא...
              </>
            ) : (
              <>
                <LogOut className="h-4 w-4 group-hover:scale-110 transition-transform" />
                יציאה מהתחזות
              </>
            )}
          </button>
        </div>
        
        {/* Warning message */}
        <div className="mt-2 text-xs text-orange-100 flex items-center gap-2">
          <AlertTriangle className="h-3 w-3" />
          <span>
            הפעולות שתבצע יתועדו כביצוע של המשתמש המקורי במצב התחזות • 
            זכור לצאת מהתחזות בסיום העבודה
          </span>
        </div>
      </div>
    </div>
  );
}