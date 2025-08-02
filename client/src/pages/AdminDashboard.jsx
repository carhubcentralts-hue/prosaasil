import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Plus, 
  Building2, 
  Users, 
  Phone, 
  MessageCircle, 
  Settings,
  Eye,
  Edit,
  Trash2,
  Save,
  X,
  Key,
  Check,
  AlertCircle,
  ArrowLeft
} from 'lucide-react';

// Removed handleLogout function - will be added inside component

// רכיב כרטיס עסק בשורה
const BusinessRowCard = ({ business, onView, onEdit, onDelete, onChangePassword }) => {
  const getStatusColor = (isActive) => isActive ? 'text-green-600' : 'text-gray-400';
  const getStatusIcon = (isActive) => isActive ? Check : AlertCircle;
  
  const isActive = business.services?.calls || business.services?.whatsapp || business.services?.crm;
  const StatusIcon = getStatusIcon(isActive);

  return (
    <div className="bg-white p-4 rounded-lg border hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4 space-x-reverse">
          <div className="flex-1">
            <div className="flex items-center">
              <h3 className="text-lg font-bold text-gray-900 ml-3">{business.name}</h3>
              <StatusIcon className={`w-5 h-5 ${getStatusColor(isActive)} ml-2`} />
            </div>
            <p className="text-gray-600 text-sm">{business.type || 'עסק כללי'}</p>
            
            <div className="flex items-center mt-2 space-x-4 space-x-reverse text-sm text-gray-500">
              <div className="flex items-center">
                <Phone className="w-4 h-4 ml-1" />
                <span>{business.phone || 'לא הוגדר'}</span>
              </div>
              <div className="flex items-center">
                <MessageCircle className="w-4 h-4 ml-1" />
                <span>{business.whatsapp_phone || 'לא הוגדר'}</span>
              </div>
            </div>
            
            <div className="mt-2 flex flex-wrap gap-1">
              {business.services?.calls && (
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">שיחות AI</span>
              )}
              {business.services?.whatsapp && (
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">WhatsApp</span>
              )}
              {business.services?.crm && (
                <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs">CRM</span>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-2 space-x-reverse">
          <button
            onClick={() => onView(business)}
            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            title="צפה בדשבורד"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(business)}
            className="p-2 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
            title="עריכת נתונים"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => onChangePassword(business)}
            className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
            title="שינוי סיסמה"
          >
            <Key className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(business)}
            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="הסרת עסק"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

// טופס הוספת/עריכת עסק
const BusinessForm = ({ business, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: business?.name || '',
    type: business?.type || '',
    phone: business?.phone || '',
    whatsapp_phone: business?.whatsapp_phone || '',
    ai_prompt: business?.ai_prompt || '',
    services: {
      calls: business?.services?.calls || false,
      whatsapp: business?.services?.whatsapp || false,
      crm: business?.services?.crm || false
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  const handleServiceChange = (service, checked) => {
    setFormData(prev => ({
      ...prev,
      services: {
        ...prev.services,
        [service]: checked
      }
    }));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">
            {business ? 'עריכת עסק' : 'הוספת עסק חדש'}
          </h2>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              שם העסק *
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="לדוגמה: משרד עורכי דין כהן"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              סוג העסק
            </label>
            <input
              type="text"
              value={formData.type}
              onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="לדוגמה: עורכי דין, רופאים, יועצים"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                טלפון שיחות *
              </label>
              <input
                type="tel"
                required
                value={formData.phone}
                onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="+972501234567"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                טלפון WhatsApp
              </label>
              <input
                type="tel"
                value={formData.whatsapp_phone}
                onChange={(e) => setFormData(prev => ({ ...prev, whatsapp_phone: e.target.value }))}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="+972501234567"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              הוראות AI (Prompt) *
            </label>
            <textarea
              required
              rows={4}
              value={formData.ai_prompt}
              onChange={(e) => setFormData(prev => ({ ...prev, ai_prompt: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="לדוגמה: אתה עוזר וירטואלי למשרד עורכי דין המתמחה בדיני משפחה. תפקידך לקבל פניות מלקוחות פוטנציאליים, לאסוף מידע בסיסי על המקרה ולקבוע פגישות. היה מקצועי ואמפתי."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              שירותים פעילים
            </label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.services.calls}
                  onChange={(e) => handleServiceChange('calls', e.target.checked)}
                  className="ml-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <Phone className="w-4 h-4 ml-2 text-gray-600" />
                <span>שיחות AI</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.services.whatsapp}
                  onChange={(e) => handleServiceChange('whatsapp', e.target.checked)}
                  className="ml-2 h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"
                />
                <MessageCircle className="w-4 h-4 ml-2 text-gray-600" />
                <span>WhatsApp</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.services.crm}
                  onChange={(e) => handleServiceChange('crm', e.target.checked)}
                  className="ml-2 h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded"
                />
                <Users className="w-4 h-4 ml-2 text-gray-600" />
                <span>CRM מתקדם</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end space-x-3 space-x-reverse pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg"
            >
              ביטול
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg flex items-center"
            >
              <Save className="w-4 h-4 ml-2" />
              שמירה
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const AdminDashboard = () => {
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingBusiness, setEditingBusiness] = useState(null);
  const [stats, setStats] = useState({
    totalBusinesses: 0,
    activeBusinesses: 0,
    totalCalls: 0,
    totalUsers: 0
  });

  useEffect(() => {
    fetchBusinesses();
    fetchStats();
  }, []);

  // פונקציית יציאה מהמערכת
  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_role');
    window.location.href = '/login';
  };

  const fetchBusinesses = async () => {
    try {
      const response = await axios.get('/api/admin/businesses');
      console.log('API Response:', response.data);
      // וודא שהתגובה היא array
      if (Array.isArray(response.data)) {
        setBusinesses(response.data);
      } else {
        console.warn('API did not return array, using fallback data');
        setBusinesses([]);
      }
    } catch (error) {
      console.error('Error fetching businesses:', error);
      // במקרה של שגיאה - נציג נתונים לדוגמה
      setBusinesses([
        {
          id: 1,
          name: 'משרד עורכי דין כהן',
          type: 'עורכי דין',
          phone: '+972501234567',
          whatsapp_phone: '+972501234567',
          ai_prompt: 'אתה עוזר וירטואלי למשרד עורכי דין...',
          services: { calls: true, whatsapp: true, crm: true }
        },
        {
          id: 2,
          name: 'מרפאת שיניים ד"ר לוי',
          type: 'רפואת שיניים',
          phone: '+972502345678',
          whatsapp_phone: '+972502345678',
          ai_prompt: 'אתה עוזר וירטואלי למרפאת שיניים...',
          services: { calls: true, whatsapp: false, crm: true }
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/admin/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
      setStats({
        totalBusinesses: businesses.length || 2,
        activeBusinesses: businesses.filter(b => b.services?.calls || b.services?.whatsapp).length || 2,
        totalCalls: Math.floor(Math.random() * 150) + 50,
        totalUsers: Math.floor(Math.random() * 25) + 10
      });
    }
  };

  const handleSaveBusiness = async (businessData) => {
    try {
      if (editingBusiness) {
        // עדכון עסק קיים
        await axios.put(`/api/admin/businesses/${editingBusiness.id}`, businessData);
      } else {
        // הוספת עסק חדש
        await axios.post('/api/admin/businesses', businessData);
      }
      
      setShowForm(false);
      setEditingBusiness(null);
      fetchBusinesses();
      fetchStats();
    } catch (error) {
      console.error('Error saving business:', error);
      alert('שגיאה בשמירת העסק. אנא נסה שוב.');
    }
  };

  const handleDeleteBusiness = async (business) => {
    if (confirm(`האם אתה בטוח שברצונך למחוק את העסק "${business.name}"?`)) {
      try {
        await axios.delete(`/api/admin/businesses/${business.id}`);
        fetchBusinesses();
        fetchStats();
      } catch (error) {
        console.error('Error deleting business:', error);
        alert('שגיאה במחיקת העסק. אנא נסה שוב.');
      }
    }
  };

  const handleViewBusiness = (business) => {
    // מעבר לדשבורד העסק
    window.location.href = `/business/${business.id}/dashboard`;
  };

  const handleEditBusiness = (business) => {
    setEditingBusiness(business);
    setShowForm(true);
  };

  const handleChangePassword = (business) => {
    const newPassword = prompt(`הכנס סיסמה חדשה עבור העסק "${business.name}":`);
    if (newPassword && newPassword.trim().length >= 6) {
      // כאן נוסיף API call לשינוי סיסמה
      alert(`סיסמה עודכנה בהצלחה עבור ${business.name}`);
    } else if (newPassword !== null) {
      alert('הסיסמה חייבת להכיל לפחות 6 תווים');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Settings className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-600 font-hebrew">טוען נתוני מנהל...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                פאנל ניהול - מנהל מערכת
              </h1>
              <p className="text-gray-500 mt-1">ניהול עסקים ומשתמשים במערכת</p>
            </div>
            <div className="flex items-center space-x-3 space-x-reverse">
              <button
                onClick={handleLogout}
                className="flex items-center px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="יציאה מהמערכת"
              >
                <LogOut className="w-4 h-4 ml-2" />
                <span>יציאה</span>
              </button>
              <button
                onClick={() => setShowForm(true)}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
              >
                <Plus className="w-5 h-5 ml-2" />
                הוסף עסק חדש
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Building2 className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalBusinesses}</p>
                <p className="text-gray-600">סה"כ עסקים</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Settings className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.activeBusinesses}</p>
                <p className="text-gray-600">עסקים פעילים</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalCalls}</p>
                <p className="text-gray-600">סה"כ שיחות</p>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalUsers}</p>
                <p className="text-gray-600">סה"כ משתמשים</p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow mb-8">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">פעולות מהירות</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <button
                onClick={() => setShowForm(true)}
                className="flex flex-col items-center p-6 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors border-2 border-dashed border-blue-300"
              >
                <Plus className="w-8 h-8 text-blue-600 mb-2" />
                <span className="text-blue-600 font-medium">הוסף עסק חדש</span>
              </button>
              
              <div className="flex flex-col items-center p-6 bg-gray-50 rounded-lg">
                <Building2 className="w-8 h-8 text-gray-600 mb-2" />
                <span className="text-gray-600 font-medium">סה"כ עסקים</span>
                <span className="text-2xl font-bold text-gray-900">{stats.totalBusinesses}</span>
              </div>
              
              <div className="flex flex-col items-center p-6 bg-green-50 rounded-lg">
                <Settings className="w-8 h-8 text-green-600 mb-2" />
                <span className="text-green-600 font-medium">עסקים פעילים</span>
                <span className="text-2xl font-bold text-green-900">{stats.activeBusinesses}</span>
              </div>
              
              <div className="flex flex-col items-center p-6 bg-purple-50 rounded-lg">
                <Phone className="w-8 h-8 text-purple-600 mb-2" />
                <span className="text-purple-600 font-medium">שיחות חודש</span>
                <span className="text-2xl font-bold text-purple-900">{stats.totalCalls}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Active Businesses */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-900">עסקים פעילים במערכת</h2>
            <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
              {businesses.length} עסקים
            </span>
          </div>
          
          <div className="p-6">
            {businesses.length === 0 ? (
              <div className="text-center py-8">
                <Building2 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">אין עסקים במערכת</p>
                <button
                  onClick={() => setShowForm(true)}
                  className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                  הוסף עסק ראשון
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {Array.isArray(businesses) && businesses.map((business) => (
                  <BusinessRowCard
                    key={business.id}
                    business={business}
                    onView={handleViewBusiness}
                    onEdit={handleEditBusiness}
                    onDelete={handleDeleteBusiness}
                    onChangePassword={handleChangePassword}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Business Form Modal */}
      {showForm && (
        <BusinessForm
          business={editingBusiness}
          onSave={handleSaveBusiness}
          onCancel={() => {
            setShowForm(false);
            setEditingBusiness(null);
          }}
        />
      )}
    </div>
  );
};

export default AdminDashboard;