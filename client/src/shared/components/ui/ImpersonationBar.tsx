import React from 'react';
import { X, AlertTriangle, User, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ImpersonationBarProps {
  businessName?: string;
  onExit: () => void;
}

export function ImpersonationBar({ businessName, onExit }: ImpersonationBarProps) {
  const navigate = useNavigate();

  const handleExitImpersonation = () => {
    onExit();
    navigate('/app/admin/businesses');
  };

  return (
    <div className="bg-amber-500 text-white px-4 py-2 flex items-center justify-between shadow-sm" dir="rtl">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          <span className="font-medium">מצב התחזות פעיל</span>
        </div>
        
        {businessName && (
          <div className="flex items-center gap-2 text-amber-100">
            <User className="h-4 w-4" />
            <span className="text-sm">מתחזה לעסק: {businessName}</span>
          </div>
        )}
      </div>

      <button
        onClick={handleExitImpersonation}
        className="flex items-center gap-2 px-3 py-1 bg-amber-600 hover:bg-amber-700 rounded-lg transition-colors text-sm font-medium"
        data-testid="button-exit-impersonation"
      >
        <ArrowLeft className="h-4 w-4" />
        יציאה מהתחזות
      </button>
    </div>
  );
}