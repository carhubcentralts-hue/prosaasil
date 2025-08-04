import React from 'react';
import MondayStyleCRM from '../components/MondayStyleCRM';
import { ArrowLeft } from 'lucide-react';

const BusinessCRMAdvanced = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Back Button */}
      <div className="p-4">
        <button 
          onClick={() => window.location.href = '/business/dashboard'}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-800 font-hebrew transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          חזרה לדשבורד עסק
        </button>
      </div>
      
      {/* Monday.com Style CRM for Business */}
      <MondayStyleCRM isAdmin={false} />
    </div>
  );
};

export default BusinessCRMAdvanced;