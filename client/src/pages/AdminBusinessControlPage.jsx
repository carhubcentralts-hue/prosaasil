import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, 
  Building2, 
  Users, 
  Phone, 
  MessageSquare,
  Calendar,
  Activity,
  Settings,
  Eye,
  Shield,
  ChevronRight
} from 'lucide-react';

const AdminBusinessControlPage = () => {
  const { id } = useParams();
  const [business, setBusiness] = useState(null);
  const [businessData, setBusinessData] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchBusinessData();
  }, [id]);

  const fetchBusinessData = async () => {
    try {
      setLoading(true);
      
      const [businessRes, dataRes, customersRes, callsRes] = await Promise.all([
        axios.get(`/api/admin/businesses/${id}`),
        axios.get(`/api/business/info?business_id=${id}`),
        axios.get(`/api/business/customers?business_id=${id}`),
        axios.get(`/api/business/calls?business_id=${id}`)
      ]);

      setBusiness(businessRes.data);
      setBusinessData(dataRes.data);
      setCustomers(customersRes.data || []);
      setCalls(callsRes.data || []);
    } catch (error) {
      console.error('Error fetching business control data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBackToAdmin = () => {
    window.location.href = '/admin/dashboard';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני עסק...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* כותרת עם חזרה למנהל */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={handleBackToAdmin}
                className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span className="font-hebrew">חזור לדשבורד מנהל</span>
              </button>
              <div className="w-px h-6 bg-gray-300"></div>
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-purple-600" />
                <span className="font-hebrew font-medium text-gray-900">שליטת מנהל</span>
              </div>
            </div>
            <div className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-hebrew">
              במצב שליטה מלאה
            </div>
          </div>
        </div>
      </div>

      {/* מידע עסק */}
      {business && (
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Building2 className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 font-hebrew">{business.name}</h1>
                <p className="text-gray-600 font-hebrew">{business.type} | עסק #{business.id}</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Phone className="w-5 h-5 text-blue-600" />
                  <span className="font-medium text-blue-900 font-hebrew">טלפון עסק</span>
                </div>
                <p className="text-blue-800 font-bold">{business.phone}</p>
              </div>
              
              <div className="bg-green-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-900 font-hebrew">לקוחות</span>
                </div>
                <p className="text-green-800 font-bold">{customers.length}</p>
              </div>
              
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-5 h-5 text-purple-600" />
                  <span className="font-medium text-purple-900 font-hebrew">שיחות</span>
                </div>
                <p className="text-purple-800 font-bold">{calls.length}</p>
              </div>
            </div>
          </div>

          {/* טאבים */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="border-b border-gray-200">
              <nav className="flex">
                <button
                  onClick={() => setActiveTab('overview')}
                  className={`px-6 py-3 font-hebrew font-medium ${
                    activeTab === 'overview' 
                      ? 'text-blue-600 border-b-2 border-blue-600' 
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  סקירה כללית
                </button>
                <button
                  onClick={() => setActiveTab('customers')}
                  className={`px-6 py-3 font-hebrew font-medium ${
                    activeTab === 'customers' 
                      ? 'text-blue-600 border-b-2 border-blue-600' 
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  לקוחות
                </button>
                <button
                  onClick={() => setActiveTab('calls')}
                  className={`px-6 py-3 font-hebrew font-medium ${
                    activeTab === 'calls' 
                      ? 'text-blue-600 border-b-2 border-blue-600' 
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  שיחות
                </button>
                <button
                  onClick={() => setActiveTab('settings')}
                  className={`px-6 py-3 font-hebrew font-medium ${
                    activeTab === 'settings' 
                      ? 'text-blue-600 border-b-2 border-blue-600' 
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  הגדרות
                </button>
              </nav>
            </div>

            <div className="p-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  <h3 className="text-lg font-bold text-gray-900 font-hebrew">סקירה כללית</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 font-hebrew mb-3">שירותים פעילים</h4>
                      <div className="space-y-2">
                        {business.services?.crm && (
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                            <span className="text-sm font-hebrew text-gray-700">מערכת CRM</span>
                          </div>
                        )}
                        {business.services?.whatsapp && (
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                            <span className="text-sm font-hebrew text-gray-700">WhatsApp עסקי</span>
                          </div>
                        )}
                        {business.services?.calls && (
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                            <span className="text-sm font-hebrew text-gray-700">מוקד שיחות</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 font-hebrew mb-3">סטטיסטיקות</h4>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm font-hebrew text-gray-600">סה"כ לקוחות:</span>
                          <span className="text-sm font-bold text-gray-900">{customers.length}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm font-hebrew text-gray-600">שיחות השבוע:</span>
                          <span className="text-sm font-bold text-gray-900">{calls.length}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'customers' && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 font-hebrew mb-4">רשימת לקוחות</h3>
                  {customers.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-gray-200">
                            <th className="text-right py-3 px-4 font-hebrew text-gray-700">שם</th>
                            <th className="text-right py-3 px-4 font-hebrew text-gray-700">טלפון</th>
                            <th className="text-right py-3 px-4 font-hebrew text-gray-700">מצב</th>
                          </tr>
                        </thead>
                        <tbody>
                          {customers.slice(0, 10).map((customer, index) => (
                            <tr key={index} className="border-b border-gray-100">
                              <td className="py-3 px-4 font-hebrew">{customer.name || 'לקוח ' + (index + 1)}</td>
                              <td className="py-3 px-4">{customer.phone || '---'}</td>
                              <td className="py-3 px-4">
                                <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-hebrew">
                                  פעיל
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500 font-hebrew">
                      אין לקוחות רשומים עדיין
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'calls' && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 font-hebrew mb-4">שיחות אחרונות</h3>
                  {calls.length > 0 ? (
                    <div className="space-y-3">
                      {calls.slice(0, 10).map((call, index) => (
                        <div key={index} className="bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <Phone className="w-4 h-4 text-gray-600" />
                              <span className="font-hebrew text-gray-900">{call.from || 'מספר לא ידוע'}</span>
                            </div>
                            <span className="text-sm font-hebrew text-gray-600">
                              {call.timestamp || 'זמן לא ידוע'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500 font-hebrew">
                      אין שיחות רשומות עדיין
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'settings' && (
                <div>
                  <h3 className="text-lg font-bold text-gray-900 font-hebrew mb-4">הגדרות עסק</h3>
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield className="w-5 h-5 text-yellow-600" />
                      <span className="font-medium text-yellow-800 font-hebrew">מצב מנהל</span>
                    </div>
                    <p className="text-yellow-700 font-hebrew text-sm">
                      אתה צופה בעסק זה במצב שליטת מנהל. לא ניתן לבצע שינויים מהדף הזה.
                      לשינויים, חזור לדשבורד המנהל.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminBusinessControlPage;