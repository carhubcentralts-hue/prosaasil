import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Building2, 
  Users, 
  Calendar,
  Activity,
  MessageSquare,
  Phone,
  UserCheck,
  Settings,
  Key,
  LogOut
} from 'lucide-react';

const BusinessDashboard = () => {
  const [businessInfo, setBusinessInfo] = useState(null);
  const [services, setServices] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });

  const userName = localStorage.getItem('user_name') || 'משתמש עסק';
  const businessId = localStorage.getItem('business_id') || 1;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const [infoRes, servicesRes, statusRes, usersRes] = await Promise.all([
        axios.get(`/api/business/info?business_id=${businessId}`),
        axios.get(`/api/business/services?business_id=${businessId}`),
        axios.get('/api/status'),
        axios.get(`/api/business/users?business_id=${businessId}`)
      ]);

      setBusinessInfo(infoRes.data);
      setServices(servicesRes.data);
      setSystemStatus(statusRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      console.error('Error fetching business data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('הסיסמאות החדשות אינן תואמות');
      return;
    }

    try {
      await axios.post('/api/business/change-password', {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      });
      
      alert('הסיסמה שונתה בהצלחה');
      setShowPasswordModal(false);
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (error) {
      console.error('Error changing password:', error);
      alert('שגיאה בשינוי הסיסמה');
    }
  };

  const handleLogout = () => {
    if (confirm('האם אתה בטוח שברצונך להתנתק?')) {
      localStorage.clear();
      window.location.href = '/login';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'operational': return <div className="w-3 h-3 bg-green-500 rounded-full"></div>;
      case 'warning': return <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>;
      case 'error': return <div className="w-3 h-3 bg-red-500 rounded-full"></div>;
      default: return <div className="w-3 h-3 bg-gray-400 rounded-full"></div>;
    }
  };

  const getHebrewDate = () => {
    const options = { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric',
      weekday: 'long'
    };
    return new Date().toLocaleDateString('he-IL', options);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתונים...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="max-w-6xl mx-auto p-6">
        {/* כותרת */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 font-hebrew mb-2">
              שלום {businessInfo?.name || 'עסק'}
            </h1>
            <p className="text-gray-600 font-hebrew">{getHebrewDate()}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-red-600 hover:text-red-700 font-hebrew"
          >
            <LogOut className="w-5 h-5" />
            התנתק
          </button>
        </div>

        {/* פרטי עסק */}
        {businessInfo && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              פרטי העסק
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <p className="text-sm text-gray-600 font-hebrew">מזהה עסק</p>
                <p className="font-bold font-hebrew">#{businessInfo.id}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 font-hebrew">מספר משתמשים</p>
                <p className="font-bold font-hebrew">{businessInfo.users_count}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 font-hebrew">תוקף חבילה</p>
                <p className="font-bold text-green-600 font-hebrew">{businessInfo.plan_expires}</p>
              </div>
            </div>
          </div>
        )}

        {/* ממשק שינוי סיסמה */}
        <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
            <Key className="w-5 h-5" />
            ניהול סיסמה
          </h2>
          <button
            onClick={() => setShowPasswordModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-hebrew"
          >
            שנה סיסמה
          </button>
        </div>

        {/* שירותים פעילים */}
        {services && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4">
              השירותים שלך
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {services.crm && (
                <button 
                  onClick={() => window.location.href = '/crm'}
                  className="flex items-center gap-3 p-4 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors text-right"
                >
                  <Users className="w-6 h-6 text-blue-600" />
                  <div>
                    <p className="font-medium font-hebrew">מערכת CRM</p>
                    <p className="text-sm text-gray-600 font-hebrew">ניהול לקוחות ומשימות</p>
                  </div>
                </button>
              )}
              {services.whatsapp && (
                <button 
                  onClick={() => window.location.href = '/whatsapp'}
                  className="flex items-center gap-3 p-4 bg-green-50 hover:bg-green-100 rounded-xl transition-colors text-right"
                >
                  <MessageSquare className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-medium font-hebrew">WhatsApp עסקי</p>
                    <p className="text-sm text-gray-600 font-hebrew">שיחות עם לקוחות</p>
                  </div>
                </button>
              )}
              {services.calls && (
                <button 
                  onClick={() => window.location.href = '/calls'}
                  className="flex items-center gap-3 p-4 bg-purple-50 hover:bg-purple-100 rounded-xl transition-colors text-right"
                >
                  <Phone className="w-6 h-6 text-purple-600" />
                  <div>
                    <p className="font-medium font-hebrew">שיחות AI</p>
                    <p className="text-sm text-gray-600 font-hebrew">ניהול שיחות אוטומטיות</p>
                  </div>
                </button>
              )}
            </div>
            {!services.crm && !services.whatsapp && !services.calls && (
              <p className="text-gray-600 font-hebrew text-center py-8">
                אין שירותים פעילים עבור העסק שלך
              </p>
            )}
          </div>
        )}

        {/* זמינות מערכת */}
        {systemStatus && (
          <div className="bg-white rounded-2xl shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              זמינות מערכת
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.gpt?.status)}
                <div>
                  <p className="font-medium font-hebrew">GPT (בינה מלאכותית)</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.gpt?.status === 'operational' ? 'פעיל' : 'לא זמין'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.twilio?.status)}
                <div>
                  <p className="font-medium font-hebrew">Twilio (שיחות)</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.twilio?.status === 'operational' ? 'פעיל' : 'לא זמין'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.baileys?.status)}
                <div>
                  <p className="font-medium font-hebrew">Baileys (WhatsApp)</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.baileys?.status === 'operational' ? 'מחובר' : 'לא מחובר'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal שינוי סיסמה */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4">
            <h3 className="text-xl font-bold text-gray-900 font-hebrew mb-4">שינוי סיסמה</h3>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 font-hebrew">
                  סיסמה נוכחית
                </label>
                <input
                  type="password"
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({...passwordForm, current_password: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 font-hebrew">
                  סיסמה חדשה
                </label>
                <input
                  type="password"
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({...passwordForm, new_password: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 font-hebrew">
                  אישור סיסמה חדשה
                </label>
                <input
                  type="password"
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({...passwordForm, confirm_password: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors font-hebrew"
                >
                  שמור
                </button>
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-400 transition-colors font-hebrew"
                >
                  ביטול
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BusinessDashboard;