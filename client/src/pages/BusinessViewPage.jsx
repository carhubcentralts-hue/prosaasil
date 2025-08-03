import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowRight,
  Eye, 
  Building2, 
  Users, 
  Activity,
  MessageSquare,
  Phone,
  UserCheck,
  AlertTriangle
} from 'lucide-react';

const BusinessViewPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [businessInfo, setBusinessInfo] = useState(null);
  const [services, setServices] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({ name: '', role: 'business', email: '' });

  useEffect(() => {
    fetchData();
  }, [id]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const [businessRes, statusRes] = await Promise.all([
        axios.get(`/api/admin/businesses/${id}`),
        axios.get('/api/status')
      ]);

      setBusinessInfo(businessRes.data);
      setServices(businessRes.data.services);
      setSystemStatus(statusRes.data);
      // אחרי שנקבל את businessInfo, נוסיף משתמשים דמי
      setUsers([
        { 
          id: 1, 
          name: 'משתמש עסק ראשי', 
          role: 'business', 
          status: 'active',
          last_login: new Date().toISOString(),
          email: `business${id}@system.com`
        }
      ]);
    } catch (error) {
      console.error('Error fetching business data:', error);
    } finally {
      setLoading(false);
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
        {/* כותרת עם חזרה */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => navigate('/admin/dashboard')}
            className="flex items-center gap-2 text-blue-600 hover:text-blue-700 font-hebrew"
          >
            <ArrowRight className="w-5 h-5" />
            חזור לדשבורד מנהל
          </button>
        </div>

        {/* תווית מצב תצוגה */}
        <div className="bg-orange-100 border border-orange-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-orange-600" />
            <p className="text-orange-800 font-hebrew font-medium">
              מצב תצוגה - מנהל צופה בדשבורד העסקי של {businessInfo?.name}
            </p>
          </div>
          <p className="text-orange-700 text-sm font-hebrew mt-1">
            זהו מצב תצוגה בלבד. לא ניתן לבצע פעולות בפועל.
          </p>
        </div>

        {/* כותרת עסק */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 font-hebrew mb-2">
            שלום {businessInfo?.name || 'עסק'}
          </h1>
          <p className="text-gray-600 font-hebrew">{getHebrewDate()}</p>
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
                <p className="text-sm text-gray-600 font-hebrew">סטטוס חבילה</p>
                <p className="font-bold text-green-600 font-hebrew">פעילה (מנוהלת ידנית)</p>
              </div>
            </div>
          </div>
        )}

        {/* שירותים פעילים */}
        {services && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4">
              שירותים זמינים
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {services.crm && (
                <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl opacity-75">
                  <Users className="w-6 h-6 text-blue-600" />
                  <div className="text-right">
                    <p className="font-medium font-hebrew">מערכת CRM</p>
                    <p className="text-sm text-gray-600 font-hebrew">ניהול לקוחות ומשימות</p>
                  </div>
                </div>
              )}
              {services.whatsapp && (
                <div className="flex items-center gap-3 p-4 bg-green-50 rounded-xl opacity-75">
                  <MessageSquare className="w-6 h-6 text-green-600" />
                  <div className="text-right">
                    <p className="font-medium font-hebrew">WhatsApp עסקי</p>
                    <p className="text-sm text-gray-600 font-hebrew">שיחות עם לקוחות</p>
                  </div>
                </div>
              )}
              {services.calls && (
                <div className="flex items-center gap-3 p-4 bg-purple-50 rounded-xl opacity-75">
                  <Phone className="w-6 h-6 text-purple-600" />
                  <div className="text-right">
                    <p className="font-medium font-hebrew">שיחות AI</p>
                    <p className="text-sm text-gray-600 font-hebrew">ניהול שיחות אוטומטיות</p>
                  </div>
                </div>
              )}
            </div>
            {!services.crm && !services.whatsapp && !services.calls && (
              <p className="text-gray-600 font-hebrew text-center py-8">
                אין שירותים פעילים עבור עסק זה
              </p>
            )}
          </div>
        )}

        {/* זמינות מערכת */}
        {systemStatus && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
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

        {/* משתמשי העסק */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew flex items-center gap-2">
              <UserCheck className="w-5 h-5" />
              משתמשי העסק
            </h2>
            <button 
              onClick={() => setShowAddUser(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              + הוסף משתמש
            </button>
          </div>
          
          <div className="space-y-3">
            {users.map((user) => (
              <div key={user.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <UserCheck className="w-5 h-5 text-green-600" />
                <div className="flex-1">
                  <p className="font-medium font-hebrew">{user.name}</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    תפקיד: {user.role === 'business' ? 'עסק' : 'מנהל'} | אימייל: {user.email}
                  </p>
                </div>
                <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-hebrew">
                  {user.status === 'active' ? 'פעיל' : 'לא פעיל'}
                </span>
              </div>
            ))}
          </div>
          
          {users.length === 0 && (
            <div className="text-center py-8 text-gray-500 font-hebrew">
              אין משתמשים רשומים עדיין
            </div>
          )}
        </div>

        {/* מודל הוספת משתמש */}
        {showAddUser && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
            <div className="bg-white rounded-2xl p-6 max-w-md w-full mx-4">
              <h3 className="text-xl font-bold text-gray-900 font-hebrew mb-4">הוסף משתמש חדש</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">שם מלא</label>
                  <input
                    type="text"
                    value={newUser.name}
                    onChange={(e) => setNewUser({...newUser, name: e.target.value})}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
                    placeholder="הכנס שם המשתמש"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">אימייל</label>
                  <input
                    type="email"
                    value={newUser.email}
                    onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="user@example.com"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 font-hebrew mb-1">תפקיד</label>
                  <select
                    value={newUser.role}
                    onChange={(e) => setNewUser({...newUser, role: e.target.value})}
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
                  >
                    <option value="business">משתמש עסק</option>
                    <option value="admin">מנהל</option>
                  </select>
                </div>
              </div>
              
              <div className="flex gap-3 mt-6">
                <button 
                  onClick={() => {
                    // הוספת משתמש חדש למערך
                    const newUserId = users.length + 1;
                    setUsers([...users, {
                      id: newUserId,
                      name: newUser.name,
                      role: newUser.role,
                      email: newUser.email,
                      status: 'active',
                      last_login: new Date().toISOString()
                    }]);
                    setNewUser({ name: '', role: 'business', email: '' });
                    setShowAddUser(false);
                  }}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg font-medium transition-colors font-hebrew"
                >
                  הוסף משתמש
                </button>
                <button 
                  onClick={() => {
                    setShowAddUser(false);
                    setNewUser({ name: '', role: 'business', email: '' });
                  }}
                  className="flex-1 bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded-lg font-medium transition-colors font-hebrew"
                >
                  ביטול
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BusinessViewPage;