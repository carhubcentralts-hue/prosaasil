import React, { useState, useEffect } from 'react';
import { useParams } from 'wouter';
import axios from 'axios';
import { 
  ArrowRight, 
  Building2, 
  Users, 
  Phone, 
  MessageSquare, 
  Activity,
  CheckCircle,
  XCircle,
  AlertCircle 
} from 'lucide-react';

const BusinessViewPage = () => {
  const { id } = useParams();
  const [businessInfo, setBusinessInfo] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchBusinessData();
  }, [id]);

  const fetchBusinessData = async () => {
    try {
      setLoading(true);
      
      const [infoRes, leadsRes] = await Promise.all([
        axios.get(`/api/business/info?business_id=${id}`),
        axios.get(`/api/business/leads?business_id=${id}`)
      ]);
      
      setBusinessInfo(infoRes.data);
      setLeads(leadsRes.data || []);
    } catch (error) {
      console.error('Error fetching business data:', error);
      setError('שגיאה בטעינת נתוני העסק');
    } finally {
      setLoading(false);
    }
  };

  const returnToAdmin = () => {
    // Clear business context and return to admin
    localStorage.removeItem('business_id');
    localStorage.setItem('user_role', 'admin');
    window.location.href = '/admin/dashboard';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 font-hebrew" dir="rtl">
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 font-hebrew">טוען נתוני עסק...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 font-hebrew" dir="rtl">
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <p className="text-red-600 font-hebrew mb-4">{error}</p>
            <button
              onClick={returnToAdmin}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-hebrew"
            >
              חזרה למנהל
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew" dir="rtl">
      {/* Header with navigation */}
      <div className="bg-gradient-to-l from-purple-600 to-blue-600 text-white p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={returnToAdmin}
                className="flex items-center gap-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
              >
                <ArrowRight className="w-4 h-4" />
                חזרה למנהל
              </button>
              <div className="w-px h-6 bg-white/30"></div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Building2 className="w-6 h-6" />
                צפייה בעסק: {businessInfo?.name || 'עסק לא זמין'}
              </h1>
            </div>
            <div className="bg-white/20 px-3 py-1 rounded-full text-sm">
              מצב צפייה בלבד
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Business Info Card */}
        {businessInfo && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              פרטי העסק
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div>
                <p className="text-sm text-gray-600 font-hebrew mb-1">שם העסק</p>
                <p className="font-medium font-hebrew">{businessInfo.name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 font-hebrew mb-1">טלפון</p>
                <p className="font-medium font-hebrew">{businessInfo.phone || 'לא זמין'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 font-hebrew mb-1">סוג עסק</p>
                <p className="font-medium font-hebrew">{businessInfo.type || 'לא זמין'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 font-hebrew mb-1">משתמשים</p>
                <p className="font-medium font-hebrew">{businessInfo.users_count || 0}</p>
              </div>
            </div>
          </div>
        )}

        {/* Services Status */}
        {businessInfo?.services && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              שירותים פעילים
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className={`p-4 rounded-lg border-2 ${businessInfo.services.crm ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                <div className="flex items-center gap-3 mb-2">
                  <Users className={`w-5 h-5 ${businessInfo.services.crm ? 'text-green-600' : 'text-gray-400'}`} />
                  <span className="font-medium font-hebrew">CRM</span>
                  {businessInfo.services.crm ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-gray-400" />
                  )}
                </div>
                <p className="text-sm text-gray-600 font-hebrew">
                  {businessInfo.services.crm ? 'פעיל' : 'לא פעיל'}
                </p>
              </div>

              <div className={`p-4 rounded-lg border-2 ${businessInfo.services.whatsapp ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                <div className="flex items-center gap-3 mb-2">
                  <MessageSquare className={`w-5 h-5 ${businessInfo.services.whatsapp ? 'text-green-600' : 'text-gray-400'}`} />
                  <span className="font-medium font-hebrew">WhatsApp</span>
                  {businessInfo.services.whatsapp ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-gray-400" />
                  )}
                </div>
                <p className="text-sm text-gray-600 font-hebrew">
                  {businessInfo.services.whatsapp ? 'פעיל' : 'לא פעיל'}
                </p>
              </div>

              <div className={`p-4 rounded-lg border-2 ${businessInfo.services.calls ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                <div className="flex items-center gap-3 mb-2">
                  <Phone className={`w-5 h-5 ${businessInfo.services.calls ? 'text-green-600' : 'text-gray-400'}`} />
                  <span className="font-medium font-hebrew">שיחות</span>
                  {businessInfo.services.calls ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-gray-400" />
                  )}
                </div>
                <p className="text-sm text-gray-600 font-hebrew">
                  {businessInfo.services.calls ? 'פעיל' : 'לא פעיל'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Leads Table */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-6 flex items-center gap-2">
            <Users className="w-5 h-5" />
            לידים ולקוחות ({leads.length})
          </h2>
          
          {leads.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-right py-3 px-4 font-medium text-gray-700 font-hebrew">שם</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-700 font-hebrew">טלפון</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-700 font-hebrew">מקור</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-700 font-hebrew">סטטוס</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-700 font-hebrew">תאריך יצירה</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead, index) => (
                    <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4 font-hebrew">{lead.name || 'לא זמין'}</td>
                      <td className="py-3 px-4 font-hebrew">{lead.phone || 'לא זמין'}</td>
                      <td className="py-3 px-4 font-hebrew">{lead.source || 'לא זמין'}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-hebrew ${
                          lead.status === 'active' ? 'bg-green-100 text-green-800' :
                          lead.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {lead.status === 'active' ? 'פעיל' :
                           lead.status === 'pending' ? 'ממתין' : 'לא זמין'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-gray-600 font-hebrew">
                        {lead.created_at ? new Date(lead.created_at).toLocaleDateString('he-IL') : 'לא זמין'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8">
              <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 font-hebrew">אין לידים זמינים עבור עסק זה</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BusinessViewPage;