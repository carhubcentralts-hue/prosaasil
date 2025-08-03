import React, { useState, useEffect } from 'react';
import { Users, ArrowLeft, Plus, Edit, Trash2, Phone, Mail, MapPin, Calendar } from 'lucide-react';

const CRMPage = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    company: '',
    address: '',
    status: 'lead'
  });

  useEffect(() => {
    // טוען רשימת לקוחות
    const fetchCustomers = () => {
      // נתונים לדוגמה
      const demoCustomersData = [
        {
          id: 1,
          name: 'יוסי כהן',
          phone: '+972-50-123-4567',
          email: 'yossi@example.com',
          company: 'כהן טכנולוגיות בע"מ',
          address: 'תל אביב',
          status: 'active',
          lastContact: '2025-08-02',
          notes: 'מעוניין בפתרון CRM',
          createdAt: '2025-07-15'
        },
        {
          id: 2,
          name: 'שרה לוי',
          phone: '+972-54-987-6543',
          email: 'sara@company.co.il',
          company: 'לוי ושות\'',
          address: 'ירושלים',
          status: 'lead',
          lastContact: '2025-08-01',
          notes: 'רוצה לשמוע על פתרונות AI',
          createdAt: '2025-07-20'
        },
        {
          id: 3,
          name: 'דוד ישראלי',
          phone: '+972-52-111-2222',
          email: 'david@business.com',
          company: 'ישראלי אנטרפרייז',
          address: 'חיפה',
          status: 'inactive',
          lastContact: '2025-07-28',
          notes: 'הציע הצעת מחיר',
          createdAt: '2025-07-10'
        },
        {
          id: 4,
          name: 'מירי גולדשטיין',
          phone: '+972-50-555-7777',
          email: 'miri@startup.co.il',
          company: 'סטארטאפ חדשני',
          address: 'הרצליה',
          status: 'active',
          lastContact: '2025-08-02',
          notes: 'לקוחה פוטנציאלית חזקה',
          createdAt: '2025-07-25'
        },
        {
          id: 5,
          name: 'אבי רוזנברג',
          phone: '+972-53-888-9999',
          email: 'avi@corporation.com',
          company: 'רוזנברג קורפוריישן',
          address: 'פתח תקווה',
          status: 'lead',
          lastContact: '2025-07-30',
          notes: 'מחפש פתרונות אוטומציה',
          createdAt: '2025-07-22'
        }
      ];
      
      setCustomers(demoCustomersData);
      setLoading(false);
    };

    fetchCustomers();
  }, []);

  const handleBackToDashboard = () => {
    window.location.href = '/business/dashboard';
  };

  const handleAddCustomer = () => {
    setShowAddForm(true);
    setEditingCustomer(null);
    setFormData({
      name: '',
      phone: '',
      email: '',
      company: '',
      address: '',
      status: 'lead'
    });
  };

  const handleEditCustomer = (customer) => {
    setEditingCustomer(customer);
    setFormData(customer);
    setShowAddForm(true);
  };

  const handleDeleteCustomer = (customerId) => {
    if (confirm('האם אתה בטוח שברצונך למחוק את הלקוח?')) {
      setCustomers(customers.filter(c => c.id !== customerId));
    }
  };

  const handleSaveCustomer = () => {
    if (!formData.name || !formData.phone) {
      alert('אנא מלא את השדות החובה');
      return;
    }

    if (editingCustomer) {
      // עריכת לקוח קיים
      setCustomers(customers.map(c => 
        c.id === editingCustomer.id ? { ...c, ...formData } : c
      ));
    } else {
      // הוספת לקוח חדש
      const newCustomer = {
        ...formData,
        id: Math.max(...customers.map(c => c.id)) + 1,
        createdAt: new Date().toISOString().split('T')[0],
        lastContact: new Date().toISOString().split('T')[0]
      };
      setCustomers([...customers, newCustomer]);
    }

    setShowAddForm(false);
    setEditingCustomer(null);
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'lead': return 'text-blue-600 bg-blue-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'active': return 'לקוח פעיל';
      case 'lead': return 'ליד';
      case 'inactive': return 'לא פעיל';
      default: return 'לא ידוע';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Users className="w-8 h-8 text-purple-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-600">טוען לקוחות...</p>
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
            <div className="flex items-center">
              <button
                onClick={handleBackToDashboard}
                className="flex items-center px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors ml-4"
              >
                <ArrowLeft className="w-4 h-4 ml-2" />
                <span>חזרה לדשבורד</span>
              </button>
              <h1 className="text-3xl font-bold text-gray-900">מערכת CRM</h1>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium">
                {customers.length} לקוחות
              </div>
              <button
                onClick={handleAddCustomer}
                className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 flex items-center"
              >
                <Plus className="w-5 h-5 ml-2" />
                הוסף לקוח
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
              <Users className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{customers.length}</p>
                <p className="text-gray-600">סה"כ לקוחות</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{customers.filter(c => c.status === 'active').length}</p>
                <p className="text-gray-600">לקוחות פעילים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{customers.filter(c => c.status === 'lead').length}</p>
                <p className="text-gray-600">לידים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Calendar className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">
                  {customers.filter(c => {
                    const lastContact = new Date(c.lastContact);
                    const today = new Date();
                    const diffDays = Math.ceil((today - lastContact) / (1000 * 60 * 60 * 24));
                    return diffDays <= 7;
                  }).length}
                </p>
                <p className="text-gray-600">פעילות השבוע</p>
              </div>
            </div>
          </div>
        </div>

        {/* Customers List */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">רשימת לקוחות</h2>
          </div>
          <div className="p-6">
            {customers.length === 0 ? (
              <div className="text-center py-8">
                <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">אין לקוחות במערכת</p>
                <button
                  onClick={handleAddCustomer}
                  className="mt-4 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700"
                >
                  הוסף לקוח ראשון
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {customers.map((customer) => (
                  <div key={customer.id} className="border rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4 space-x-reverse">
                        <div className="flex-1">
                          <div className="flex items-center">
                            <h3 className="text-lg font-bold text-gray-900 ml-3">{customer.name}</h3>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(customer.status)}`}>
                              {getStatusText(customer.status)}
                            </span>
                          </div>
                          <p className="text-gray-600">{customer.company}</p>
                          
                          <div className="flex items-center mt-2 space-x-4 space-x-reverse text-sm text-gray-500">
                            <div className="flex items-center">
                              <Phone className="w-4 h-4 ml-1" />
                              <span>{customer.phone}</span>
                            </div>
                            <div className="flex items-center">
                              <Mail className="w-4 h-4 ml-1" />
                              <span>{customer.email}</span>
                            </div>
                            <div className="flex items-center">
                              <MapPin className="w-4 h-4 ml-1" />
                              <span>{customer.address}</span>
                            </div>
                          </div>
                          
                          {customer.notes && (
                            <div className="mt-3 p-3 bg-gray-100 rounded-lg">
                              <p className="text-sm text-gray-700">{customer.notes}</p>
                            </div>
                          )}
                          
                          <div className="mt-2 text-xs text-gray-400">
                            <span>נוצר: {customer.createdAt}</span>
                            <span className="mx-2">•</span>
                            <span>קשר אחרון: {customer.lastContact}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2 space-x-reverse">
                        <button
                          onClick={() => handleEditCustomer(customer)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="עריכה"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteCustomer(customer.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="מחיקה"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add/Edit Customer Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {editingCustomer ? 'עריכת לקוח' : 'הוספת לקוח חדש'}
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="יוסי כהן"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון *</label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="+972-50-123-4567"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="yossi@example.com"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">חברה</label>
                <input
                  type="text"
                  value={formData.company}
                  onChange={(e) => setFormData({...formData, company: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="כהן טכנולוגיות"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">כתובת</label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData({...formData, address: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="תל אביב"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">סטטוס</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({...formData, status: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                >
                  <option value="lead">ליד</option>
                  <option value="active">לקוח פעיל</option>
                  <option value="inactive">לא פעיל</option>
                </select>
              </div>
            </div>
            
            <div className="flex justify-end space-x-3 space-x-reverse mt-6">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                ביטול
              </button>
              <button
                onClick={handleSaveCustomer}
                className="px-4 py-2 bg-purple-600 text-white hover:bg-purple-700 rounded-lg"
              >
                שמירה
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CRMPage;