import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  LogOut,
  CheckCircle,
  XCircle,
  AlertCircle,
  BarChart
} from 'lucide-react';
import PasswordChangeModal from '../components/PasswordChangeModal';

const BusinessDashboard = () => {
  const navigate = useNavigate();
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
  const [businessId, setBusinessId] = useState(null);

  const userName = localStorage.getItem('user_name') || 'משתמש עסק';


  
  // קבלת business_id מהטוקן - כעת reactive!
  const getBusinessId = () => {
    try {
      const token = localStorage.getItem('auth_token');
      console.log('🔍 Getting business_id from token:', !!token);
      
      if (token && token !== 'null' && token !== 'undefined') {
        const parts = token.split('.');
        if (parts.length === 3) {
          let base64Url = parts[1];
          const missingPadding = base64Url.length % 4;
          if (missingPadding) {
            base64Url += '='.repeat(4 - missingPadding);
          }
          
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const decoded = JSON.parse(atob(base64));
          
          console.log('🔍 Decoded token payload:', decoded);
          if (decoded.business_id) {
            console.log('✅ Using business_id from token:', decoded.business_id);
            return parseInt(decoded.business_id);
          }
        }
      }
    } catch (error) {
      console.log('⚠️ Token decode failed:', error);
    }
    
    // Fallback
    const fallbackId = localStorage.getItem('business_id') || '1';
    console.log('📋 Using fallback business_id:', fallbackId);
    return parseInt(fallbackId);
  };

  // Effect לעדכון business_id כשהטוקן משתנה
  useEffect(() => {
    const updateBusinessId = () => {
      const newBusinessId = getBusinessId();
      console.log('🔄 BusinessDashboard: Setting business_id to:', newBusinessId);
      setBusinessId(newBusinessId);
    };
    
    // ניסיון מיידי
    updateBusinessId();
    
    // ניסיון חוזר אחרי delay קטן
    const timeout = setTimeout(updateBusinessId, 200);
    
    // האזנה לשינויים ב-localStorage
    const handleStorageChange = () => {
      console.log('📡 Storage changed, updating business_id');
      updateBusinessId();
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    // בדיקה תקופתית עד שיש business_id תקין
    const interval = setInterval(() => {
      const currentBusinessId = getBusinessId();
      if (currentBusinessId && currentBusinessId !== businessId) {
        console.log('🔄 Periodic check found new business_id:', currentBusinessId);
        setBusinessId(currentBusinessId);
        clearInterval(interval);
      }
    }, 500);
    
    return () => {
      clearTimeout(timeout);
      clearInterval(interval);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  // Effect לטעינת נתונים כש-businessId משתנה
  useEffect(() => {
    if (businessId) {
      console.log('📊 BusinessDashboard: Loading data for business_id:', businessId);
      fetchData();
    }
  }, [businessId]);

  const fetchData = async () => {
    if (!businessId) {
      console.log('⚠️ No business_id, skipping fetch');
      return;
    }
    
    try {
      setLoading(true);
      console.log('📡 Fetching data for business_id:', businessId);
      
      const [infoRes, servicesRes, statusRes, usersRes] = await Promise.all([
        axios.get(`/api/business/info?business_id=${businessId}`),
        axios.get(`/api/business/services?business_id=${businessId}`),
        axios.get('/api/status'),
        axios.get(`/api/business/users?business_id=${businessId}`)
      ]);

      console.log('✅ Data loaded for business_id:', businessId, 'Business name:', infoRes.data?.name);
      setBusinessInfo(infoRes.data);
      setServices(servicesRes.data);
      setSystemStatus(statusRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      console.error('❌ Error fetching business data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    // בדיקה אם אנחנו במצב השתלטות מנהל
    const adminTakeoverMode = localStorage.getItem('admin_takeover_mode');
    const originalAdminToken = localStorage.getItem('original_admin_token');
    
    if (adminTakeoverMode && originalAdminToken) {
      // חזרה למנהל
      if (window.confirm('האם אתה רוצה לחזור לדשבורד המנהל?')) {
        localStorage.removeItem('admin_takeover_mode');
        localStorage.setItem('auth_token', originalAdminToken);
        localStorage.setItem('user_role', 'admin');
        localStorage.setItem('user_name', 'מנהל');
        localStorage.removeItem('original_admin_token');
        localStorage.removeItem('business_id'); // ניקוי business_id כשחוזרים למנהל
        navigate('/admin/dashboard');
      }
    } else {
      // יציאה רגילה
      if (window.confirm('האם אתה בטוח שברצונך להתנתק?')) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_name');
        localStorage.removeItem('business_id');
        navigate('/login');
      }
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    
    if (!passwordForm.current_password) {
      alert('יש להזין את הסיסמה הנוכחית');
      return;
    }
    
    if (!passwordForm.new_password) {
      alert('יש להזין סיסמה חדשה');
      return;
    }
    
    if (passwordForm.new_password.length < 6) {
      alert('הסיסמה החדשה חייבת להכיל לפחות 6 תווים');
      return;
    }
    
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
              {localStorage.getItem('admin_takeover_mode') === 'true' 
                ? `שלום מנהל (שולט ב-${businessInfo?.name || 'עסק'})`
                : `שלום ${businessInfo?.name || 'עסק'}`}
            </h1>
            <p className="text-gray-600 font-hebrew">{getHebrewDate()}</p>
          </div>
          <div className="flex gap-4">
            {localStorage.getItem('admin_takeover_mode') === 'true' ? (
              <button 
                onClick={() => {
                  const originalAdminToken = localStorage.getItem('original_admin_token');
                  if (originalAdminToken) {
                    localStorage.removeItem('admin_takeover_mode');
                    localStorage.setItem('auth_token', originalAdminToken);
                    localStorage.setItem('user_role', 'admin');
                    localStorage.setItem('user_name', 'מנהל');
                    localStorage.removeItem('original_admin_token');
                    navigate('/admin/dashboard');
                  }
                }}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-hebrew"
              >
                <LogOut className="w-4 h-4" />
                חזרה למנהל
              </button>
            ) : (
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 text-red-600 hover:text-red-700 font-hebrew"
              >
                <LogOut className="w-5 h-5" />
                התנתק
              </button>
            )}
          </div>
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
                <div className="relative">
                  <button 
                    onClick={() => navigate('/business/crm/advanced')}
                    className="w-full flex items-center gap-3 p-4 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors text-right"
                  >
                    <Users className="w-6 h-6 text-blue-600" />
                    <div>
                      <p className="font-medium font-hebrew">מערכת CRM מתקדמת</p>
                      <p className="text-sm text-gray-600 font-hebrew">לקוחות, חוזים, חשבוניות והתממשקות</p>
                    </div>
                  </button>
                  <div className="absolute top-2 left-2">
                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                  </div>
                </div>
              )}
              {services.whatsapp && (
                <div className="relative">
                  <button 
                    onClick={() => navigate('/business/whatsapp')}
                    className="w-full flex items-center gap-3 p-4 bg-green-50 hover:bg-green-100 rounded-xl transition-colors text-right"
                  >
                    <MessageSquare className="w-6 h-6 text-green-600" />
                    <div>
                      <p className="font-medium font-hebrew">WhatsApp עסקי</p>
                      <p className="text-sm text-gray-600 font-hebrew">
                        {systemStatus?.systems?.baileys?.status === 'operational' ? 'מחובר ופעיל' : 'לא מחובר'}
                      </p>
                    </div>
                  </button>
                  <div className="absolute top-2 left-2">
                    <div className={`w-3 h-3 rounded-full ${
                      systemStatus?.systems?.baileys?.status === 'operational' ? 'bg-green-500' : 'bg-red-500'
                    }`}></div>
                  </div>
                </div>
              )}
              {services.calls && (
                <div className="relative">
                  <button 
                    onClick={() => navigate('/business/calls')}
                    className="w-full flex items-center gap-3 p-4 bg-purple-50 hover:bg-purple-100 rounded-xl transition-colors text-right"
                  >
                    <Phone className="w-6 h-6 text-purple-600" />
                    <div>
                      <p className="font-medium font-hebrew">שיחות AI</p>
                      <p className="text-sm text-gray-600 font-hebrew">
                        {systemStatus?.systems?.twilio?.status === 'operational' ? 'מחובר ופעיל' : 'לא מחובר'}
                      </p>
                    </div>
                  </button>
                  <div className="absolute top-2 left-2">
                    <div className={`w-3 h-3 rounded-full ${
                      systemStatus?.systems?.twilio?.status === 'operational' ? 'bg-green-500' : 'bg-red-500'
                    }`}></div>
                  </div>
                </div>
              )}
              
              {/* כפתור AgentLocator Dashboard - תמיד זמין */}
              <div className="relative">
                <button 
                  onClick={() => navigate('/agentlocator')}
                  className="w-full flex items-center gap-3 p-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-xl transition-all transform hover:scale-105 shadow-lg text-right"
                >
                  <BarChart className="w-6 h-6 text-white" />
                  <div>
                    <p className="font-bold font-hebrew">דשבורד AgentLocator</p>
                    <p className="text-sm text-blue-100 font-hebrew">מערכת ניהול מתקדמת עם APIs</p>
                  </div>
                </button>
                <div className="absolute top-2 left-2">
                  <div className="w-3 h-3 bg-yellow-400 rounded-full animate-pulse"></div>
                </div>
              </div>
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
      <PasswordChangeModal 
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
        userRole="business"
        businessId={businessId}
      />
    </div>
  );
};

export default BusinessDashboard;