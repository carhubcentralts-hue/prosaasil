import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Users, 
  Building2, 
  Phone, 
  MessageSquare, 
  Activity,
  Shield,
  Settings,
  Eye,
  Key,
  Trash2,
  Edit,
  Plus
} from 'lucide-react';

const AdminDashboard = () => {
  const [summary, setSummary] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const userName = localStorage.getItem('user_name') || 'מנהל';

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // שליפת נתונים בבת אחת
      const [summaryRes, businessesRes, statusRes] = await Promise.all([
        axios.get('/api/admin/summary'),
        axios.get('/api/admin/businesses'),
        axios.get('/api/status')
      ]);

      setSummary(summaryRes.data);
      setBusinesses(businessesRes.data);
      setSystemStatus(statusRes.data);
    } catch (error) {
      console.error('Error fetching admin data:', error);
    } finally {
      setLoading(false);
    }
  };

  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [selectedBusinessId, setSelectedBusinessId] = useState(null);
  const [showBusinessModal, setShowBusinessModal] = useState(false);
  const [editingBusiness, setEditingBusiness] = useState(null);

  const handleResetPassword = (businessId) => {
    setSelectedBusinessId(businessId);
    setShowPasswordModal(true);
  };

  const handlePasswordReset = async (oldPassword, newPassword) => {
    try {
      await axios.post('/api/admin/reset-password', {
        business_id: selectedBusinessId,
        old_password: oldPassword,
        new_password: newPassword
      });
      alert('הסיסמה שונתה בהצלחה');
      setShowPasswordModal(false);
      setSelectedBusinessId(null);
    } catch (error) {
      console.error('Error resetting password:', error);
      alert('שגיאה בשינוי הסיסמה');
    }
  };

  const handleAddBusiness = () => {
    setEditingBusiness(null);
    setShowBusinessModal(true);
  };

  const handleEditBusiness = (business) => {
    setEditingBusiness(business);
    setShowBusinessModal(true);
  };

  const handleDeleteBusiness = async (businessId, businessName) => {
    const confirmDelete = window.confirm(`האם אתה בטוח שברצונך למחוק את העסק "${businessName}"?`);
    if (!confirmDelete) return;

    try {
      await axios.delete(`/api/admin/businesses/${businessId}`);
      alert('העסק נמחק בהצלחה');
      fetchData(); // רענון הנתונים
    } catch (error) {
      console.error('Error deleting business:', error);
      alert('שגיאה במחיקת העסק');
    }
  };

  const handleViewBusiness = (businessId) => {
    window.location.href = `/admin/business/${businessId}/view`;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'operational': return <div className="w-3 h-3 bg-green-500 rounded-full"></div>;
      case 'warning': return <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>;
      case 'error': return <div className="w-3 h-3 bg-red-500 rounded-full"></div>;
      default: return <div className="w-3 h-3 bg-gray-400 rounded-full"></div>;
    }
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
      <div className="max-w-7xl mx-auto p-6">
        {/* כותרת */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 font-hebrew mb-2">
            שלום {userName}
          </h1>
          <p className="text-gray-600 font-hebrew">
            דשבורד ניהול מערכת AgentLocator
          </p>
        </div>

        {/* סטטוס מערכות */}
        {systemStatus && (
          <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5" />
              סטטוס מערכות
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.gpt?.status)}
                <div>
                  <p className="font-medium font-hebrew">OpenAI GPT</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.gpt?.message}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.twilio?.status)}
                <div>
                  <p className="font-medium font-hebrew">Twilio</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.twilio?.message}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(systemStatus.systems.baileys?.status)}
                <div>
                  <p className="font-medium font-hebrew">Baileys WhatsApp</p>
                  <p className="text-sm text-gray-600 font-hebrew">
                    {systemStatus.systems.baileys?.message}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* סטטיסטיקות כלליות */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-2xl shadow-md p-6">
              <div className="flex items-center gap-3 mb-2">
                <Building2 className="w-8 h-8 text-blue-600" />
                <div>
                  <p className="text-2xl font-bold text-gray-900">{summary.businesses.total}</p>
                  <p className="text-sm text-gray-600 font-hebrew">עסקים פעילים</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl shadow-md p-6">
              <div className="flex items-center gap-3 mb-2">
                <Users className="w-8 h-8 text-green-600" />
                <div>
                  <p className="text-2xl font-bold text-gray-900">{summary.users.total}</p>
                  <p className="text-sm text-gray-600 font-hebrew">משתמשים</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl shadow-md p-6">
              <div className="flex items-center gap-3 mb-2">
                <Phone className="w-8 h-8 text-purple-600" />
                <div>
                  <p className="text-2xl font-bold text-gray-900">{summary.today.calls}</p>
                  <p className="text-sm text-gray-600 font-hebrew">שיחות היום</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-2xl shadow-md p-6">
              <div className="flex items-center gap-3 mb-2">
                <MessageSquare className="w-8 h-8 text-orange-600" />
                <div>
                  <p className="text-2xl font-bold text-gray-900">{summary.today.messages}</p>
                  <p className="text-sm text-gray-600 font-hebrew">הודעות היום</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* כפתורי גישה מהירה */}
        <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 font-hebrew mb-4">
            גישה מהירה למערכות
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button 
              onClick={() => window.location.href = '/admin/crm'}
              className="flex items-center gap-3 p-4 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors"
            >
              <Users className="w-6 h-6 text-blue-600" />
              <div className="text-right">
                <p className="font-medium font-hebrew">CRM מנהל</p>
                <p className="text-sm text-gray-600 font-hebrew">ניהול לקוחות כללי</p>
              </div>
            </button>
            <button 
              onClick={() => window.location.href = '/admin/whatsapp'}
              className="flex items-center gap-3 p-4 bg-green-50 hover:bg-green-100 rounded-xl transition-colors"
            >
              <MessageSquare className="w-6 h-6 text-green-600" />
              <div className="text-right">
                <p className="font-medium font-hebrew">WhatsApp מנהל</p>
                <p className="text-sm text-gray-600 font-hebrew">ניהול הודעות כללי</p>
              </div>
            </button>
            <button 
              onClick={() => window.location.href = '/admin/calls'}
              className="flex items-center gap-3 p-4 bg-purple-50 hover:bg-purple-100 rounded-xl transition-colors"
            >
              <Phone className="w-6 h-6 text-purple-600" />
              <div className="text-right">
                <p className="font-medium font-hebrew">שיחות מוקד</p>
                <p className="text-sm text-gray-600 font-hebrew">ניהול שיחות כללי</p>
              </div>
            </button>
          </div>
        </div>

        {/* טבלת עסקים */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold text-gray-900 font-hebrew">
              ניהול עסקים
            </h2>
            <button 
              onClick={handleAddBusiness}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-hebrew">
              <Plus className="w-4 h-4" />
              הוסף עסק חדש
            </button>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-right py-3 px-4 font-hebrew">שם העסק</th>
                  <th className="text-right py-3 px-4 font-hebrew">מזהה</th>
                  <th className="text-right py-3 px-4 font-hebrew">שירותים פעילים</th>
                  <th className="text-right py-3 px-4 font-hebrew">סטטוס מערכות</th>
                  <th className="text-right py-3 px-4 font-hebrew">פעולות</th>
                </tr>
              </thead>
              <tbody>
                {businesses.map((business) => (
                  <tr key={business.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-4 px-4">
                      <div>
                        <p className="font-medium font-hebrew">{business.name}</p>
                        <p className="text-sm text-gray-600 font-hebrew">{business.type}</p>
                      </div>
                    </td>
                    <td className="py-4 px-4 font-hebrew">#{business.id}</td>
                    <td className="py-4 px-4">
                      <div className="flex gap-2">
                        {business.services.crm && (
                          <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-hebrew">CRM</span>
                        )}
                        {business.services.whatsapp && (
                          <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-hebrew">WhatsApp</span>
                        )}
                        {business.services.calls && (
                          <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs font-hebrew">שיחות</span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex gap-2">
                        {getStatusIcon('operational')}
                        {getStatusIcon('operational')}
                        {getStatusIcon('warning')}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex gap-2">
                        <button 
                          onClick={() => handleViewBusiness(business.id)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                          title="צפה בעסק"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleResetPassword(business.id)}
                          className="p-2 text-orange-600 hover:bg-orange-50 rounded"
                          title="שנה סיסמה"
                        >
                          <Key className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleEditBusiness(business)}
                          className="p-2 text-green-600 hover:bg-green-50 rounded"
                          title="ערוך עסק"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDeleteBusiness(business.id, business.name)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded"
                          title="מחק עסק"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* מודל שינוי סיסמה */}
        {showPasswordModal && (
          <PasswordModal 
            businessId={selectedBusinessId}
            onClose={() => setShowPasswordModal(false)}
            onSubmit={handlePasswordReset}
          />
        )}

        {/* מודל עריכת עסק */}
        {showBusinessModal && (
          <BusinessModal 
            business={editingBusiness}
            onClose={() => setShowBusinessModal(false)}
            onSubmit={() => {
              setShowBusinessModal(false);
              fetchData(); // רענון נתונים
            }}
          />
        )}
      </div>
    </div>
  );
};

// מודל שינוי סיסמה
const PasswordModal = ({ businessId, onClose, onSubmit }) => {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!oldPassword || !newPassword) {
      alert('יש למלא את כל השדות');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      alert('הסיסמאות החדשות אינן תואמות');
      return;
    }
    
    if (newPassword.length < 6) {
      alert('הסיסמה החדשה חייבת להכיל לפחות 6 תווים');
      return;
    }
    
    onSubmit(oldPassword, newPassword);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-lg p-6 w-96 font-hebrew">
        <h3 className="text-lg font-bold mb-4">שינוי סיסמה</h3>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              סיסמה נוכחית
            </label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              סיסמה חדשה
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md"
              required
            />
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              אימות סיסמה חדשה
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md"
              required
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700"
            >
              שמור
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-md hover:bg-gray-400"
            >
              ביטול
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// מודל עריכת עסק
const BusinessModal = ({ business, onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    name: business?.name || '',
    type: business?.type || '',
    phone: business?.phone || '',
    whatsapp_phone: business?.whatsapp_phone || '',
    ai_prompt: business?.ai_prompt || '',
    crm_enabled: business?.services?.crm || false,
    whatsapp_enabled: business?.services?.whatsapp || false,
    calls_enabled: business?.services?.calls || false
  });
  
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      if (business) {
        // עריכת עסק קיים
        await axios.put(`/api/admin/businesses/${business.id}`, formData);
      } else {
        // יצירת עסק חדש
        await axios.post('/api/admin/businesses', formData);
      }
      
      alert(business ? 'העסק עודכן בהצלחה' : 'העסק נוצר בהצלחה');
      onSubmit();
    } catch (error) {
      console.error('Error saving business:', error);
      alert('שגיאה בשמירת העסק');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-lg p-6 w-[600px] max-h-[90vh] overflow-y-auto font-hebrew">
        <h3 className="text-lg font-bold mb-4">
          {business ? 'עריכת עסק' : 'הוספת עסק חדש'}
        </h3>
        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                שם העסק
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-md"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                סוג העסק
              </label>
              <input
                type="text"
                value={formData.type}
                onChange={(e) => setFormData({...formData, type: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-md"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                טלפון ישראלי
              </label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({...formData, phone: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-md"
                placeholder="+972-XX-XXX-XXXX"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                טלפון WhatsApp
              </label>
              <input
                type="text"
                value={formData.whatsapp_phone}
                onChange={(e) => setFormData({...formData, whatsapp_phone: e.target.value})}
                className="w-full p-2 border border-gray-300 rounded-md"
                placeholder="+1-XXX-XXX-XXXX"
              />
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              שירותים פעילים
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.crm_enabled}
                  onChange={(e) => setFormData({...formData, crm_enabled: e.target.checked})}
                  className="mr-2"
                />
                CRM
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.whatsapp_enabled}
                  onChange={(e) => setFormData({...formData, whatsapp_enabled: e.target.checked})}
                  className="mr-2"
                />
                WhatsApp
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.calls_enabled}
                  onChange={(e) => setFormData({...formData, calls_enabled: e.target.checked})}
                  className="mr-2"
                />
                שיחות AI
              </label>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              הוראות AI
            </label>
            <textarea
              value={formData.ai_prompt}
              onChange={(e) => setFormData({...formData, ai_prompt: e.target.value})}
              className="w-full p-2 border border-gray-300 rounded-md h-32"
              placeholder="הכנס הוראות מיוחדות לבוט AI..."
            />
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'שומר...' : 'שמור'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-md hover:bg-gray-400"
            >
              ביטול
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AdminDashboard;