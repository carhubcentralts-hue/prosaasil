import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowRight, Building2, Phone, MessageSquare, Users, Calendar, DollarSign, Settings, Eye, LogOut } from 'lucide-react';

const AdminBusinessControlPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [business, setBusiness] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchBusinessData();
  }, [id]);

  const fetchBusinessData = async () => {
    try {
      const response = await axios.get(`/api/admin/businesses/${id}`);
      setBusiness(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching business:', error);
      setLoading(false);
    }
  };

  const handleTakeover = async () => {
    try {
      console.log('🚀 מתחיל השתלטות על עסק:', id);
      const response = await axios.post(`/api/admin/impersonate/${id}`);
      
      if (response.data.success) {
        // שמירת מצב השתלטות
        localStorage.setItem('admin_takeover_mode', 'true');
        localStorage.setItem('original_admin_token', localStorage.getItem('token'));
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user_role', 'business');
        localStorage.setItem('user_name', `מנהל שולט ב-${business?.name || 'עסק'}`);
        
        console.log('✅ השתלטות הושלמה, מעבר לדשבורד העסק');
        
        // מעבר לדשבורד העסק
        window.location.href = '/business/dashboard';
      }
    } catch (error) {
      console.error('Error taking over business:', error);
      alert('שגיאה בהשתלטות על העסק');
    }
  };

  const returnToAdmin = () => {
    navigate('/admin/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני העסק...</p>
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <h1 className="text-2xl font-bold text-red-600 mb-4">עסק לא נמצא</h1>
          <p className="text-gray-600 mb-4">לא ניתן למצוא עסק עם מזהה {id}</p>
          <button 
            onClick={returnToAdmin}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            חזור לדשבורד מנהל
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* כותרת עליונה */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={returnToAdmin}
                className="flex items-center gap-2 text-gray-600 hover:text-gray-800"
              >
                <ArrowRight className="w-4 h-4" />
                <span className="font-hebrew">חזור לדשבורד מנהל</span>
              </button>
              <div className="text-sm text-gray-400">|</div>
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" />
                <h1 className="text-xl font-bold text-gray-900 font-hebrew">
                  שליטת מנהל: {business.name}
                </h1>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600 font-hebrew">מצב: מנהל</span>
              <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* מידע על העסק */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6">
            <h2 className="text-lg font-bold text-gray-900 font-hebrew mb-4">מידע על העסק</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">שם העסק</label>
                <p className="text-gray-900 font-hebrew">{business.name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">סוג עסק</label>
                <p className="text-gray-900 font-hebrew">{business.type}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">מזהה עסק</label>
                <p className="text-gray-900 font-hebrew">#{business.id}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">משתמשים</label>
                <p className="text-gray-900 font-hebrew">{business.users_count || 0}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">תאריך תפוגת תוכנית</label>
                <p className="text-gray-900 font-hebrew">{business.plan_expires || 'לא הוגדר'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">מספר טלפון</label>
                <p className="text-gray-900 font-hebrew">{business.phone || 'לא הוגדר'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">WhatsApp</label>
                <p className="text-gray-900 font-hebrew">{business.whatsapp_phone || 'לא הוגדר'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">סטטוס</label>
                <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                  business.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}>
                  {business.is_active ? 'פעיל' : 'לא פעיל'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* שירותים זמינים */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6">
            <h2 className="text-lg font-bold text-gray-900 font-hebrew mb-4">שירותים זמינים</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-lg">
                <Users className="w-5 h-5 text-blue-600" />
                <span className="font-hebrew text-blue-800">CRM</span>
                <span className="text-xs text-blue-600">{business.services?.crm ? '✓' : '✗'}</span>
              </div>
              <div className="flex items-center gap-2 p-3 bg-green-50 rounded-lg">
                <MessageSquare className="w-5 h-5 text-green-600" />
                <span className="font-hebrew text-green-800">WhatsApp</span>
                <span className="text-xs text-green-600">{business.services?.whatsapp ? '✓' : '✗'}</span>
              </div>
              <div className="flex items-center gap-2 p-3 bg-purple-50 rounded-lg">
                <Phone className="w-5 h-5 text-purple-600" />
                <span className="font-hebrew text-purple-800">שיחות</span>
                <span className="text-xs text-purple-600">{business.services?.calls ? '✓' : '✗'}</span>
              </div>
              <div className="flex items-center gap-2 p-3 bg-orange-50 rounded-lg">
                <Calendar className="w-5 h-5 text-orange-600" />
                <span className="font-hebrew text-orange-800">יומן</span>
                <span className="text-xs text-orange-600">✓</span>
              </div>
            </div>
          </div>
        </div>

        {/* פעולות שליטה */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6">
            <h2 className="text-lg font-bold text-gray-900 font-hebrew mb-4">פעולות שליטה</h2>
            <div className="space-y-4">
              <div className="p-4 border-2 border-purple-200 rounded-lg bg-purple-50">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-purple-900 font-hebrew">השתלטות מלאה על העסק</h3>
                    <p className="text-sm text-purple-700 font-hebrew mt-1">
                      כניסה למערכת העסק עם הרשאות מלאות כאילו אתה בעל העסק
                    </p>
                  </div>
                  <button 
                    onClick={handleTakeover}
                    className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 flex items-center gap-2 font-hebrew"
                  >
                    <LogOut className="w-4 h-4" />
                    השתלט על העסק
                  </button>
                </div>
              </div>

              <div className="p-4 border-2 border-blue-200 rounded-lg bg-blue-50">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-blue-900 font-hebrew">צפייה בלבד</h3>
                    <p className="text-sm text-blue-700 font-hebrew mt-1">
                      צפייה במידע העסק ללא יכולת עריכה או שינוי
                    </p>
                  </div>
                  <button 
                    className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 flex items-center gap-2 font-hebrew"
                    disabled
                  >
                    <Eye className="w-4 h-4" />
                    צפייה (בפיתוח)
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* הודעת אזהרה */}
        <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 bg-yellow-400 rounded-full flex items-center justify-center">
              <span className="text-yellow-800 text-xs font-bold">!</span>
            </div>
            <p className="text-yellow-800 font-hebrew">
              <strong>אזהרה:</strong> השתלטות על עסק תעביר אותך למערכת העסק עם הרשאות מלאות. 
              תוכל לחזור לדשבורד המנהל בכל עת.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminBusinessControlPage;