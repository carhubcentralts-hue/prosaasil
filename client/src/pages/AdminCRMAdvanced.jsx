import React from 'react';
import { useNavigate } from 'react-router-dom';
import MondayStyleCRM from '../components/MondayStyleCRM';
import { ArrowLeft } from 'lucide-react';

const AdminCRMAdvanced = () => {
  const navigate = useNavigate();
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Back Button */}
      <div className="p-4">
        <button 
          onClick={() => navigate('/admin/dashboard')}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-800 font-hebrew transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          חזרה לדשבורד מנהל
        </button>
      </div>
      
      {/* Monday.com Style CRM */}
      <MondayStyleCRM isAdmin={true} />
    </div>
  );
};

export default AdminCRMAdvanced;