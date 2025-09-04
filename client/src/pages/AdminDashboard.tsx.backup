import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Users, 
  Settings, 
  Eye, 
  Edit,
  Plus,
  Phone,
  MessageCircle,
  UserCheck,
  TrendingUp,
  Activity
} from 'lucide-react';

function AdminDashboard({ user }: { user: any }) {
  const [businesses, setBusinesses] = useState<any[]>([]);
  const [systemStats, setSystemStats] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [editingBusiness, setEditingBusiness] = useState<any>(null);

  useEffect(() => {
    fetchAdminData();
  }, []);

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      const [businessesRes, statsRes] = await Promise.all([
        fetch('/api/admin/businesses'),
        fetch('/api/admin/stats')
      ]);

      if (businessesRes.ok) {
        const businessesData = await businessesRes.json();
        setBusinesses(businessesData.items || businessesData.businesses || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setSystemStats(statsData);
      }
    } catch (error) {
      console.error('Failed to fetch admin data:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateBusinessPermissions = async (businessId: any, permissions: any) => {
    try {
      const response = await fetch(`/api/admin/businesses/${businessId}/permissions`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(permissions),
      });

      if (response.ok) {
        // עדכן את הרשימה המקומית
        setBusinesses(businesses.map((business: any) => 
          business.id === businessId 
            ? { ...business, ...permissions }
            : business
        ));
        setEditingBusiness(null);
      }
    } catch (error) {
      console.error('Failed to update permissions:', error);
    }
  };

  const loginAsBusiness = async (businessId: any) => {
    try {
      const response = await fetch(`/api/admin/impersonate/${businessId}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // הפנה לדשבורד של העסק
        window.location.href = '/dashboard';
      }
    } catch (error) {
      console.error('Failed to login as business:', error);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const adminStats = [
    {
      title: 'סה"כ עסקים',
      value: systemStats.total_businesses || 0,
      icon: Building2,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      title: 'משתמשים פעילים',
      value: systemStats.active_users || 0,
      icon: Users,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'שיחות היום',
      value: systemStats.calls_today || 0,
      icon: Phone,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50'
    },
    {
      title: 'הודעות וואטסאפ',
      value: systemStats.whatsapp_messages_today || 0,
      icon: MessageCircle,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          ניהול מערכת
        </h1>
        <p className="text-gray-600 mt-1">
          ניהול עסקים, משתמשים והרשאות במערכת
        </p>
      </div>

      {/* System Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {adminStats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 mb-1">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">
                    {stat.value}
                  </p>
                </div>
                <div className={`${stat.bgColor} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Businesses Management */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900">
            ניהול עסקים
          </h3>
          <button className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center">
            <Plus className="w-4 h-4 ml-2" />
            הוסף עסק חדש
          </button>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  עסק
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  הרשאות
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  פעילות
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  פעולות
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {businesses.map((business) => (
                <tr key={business.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                        <Building2 className="w-5 h-5 text-blue-600" />
                      </div>
                      <div className="mr-4">
                        <div className="text-sm font-medium text-gray-900">
                          {business.name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {business.phone_number}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex space-x-2 space-x-reverse">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        business.calls_enabled 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        שיחות
                      </span>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        business.whatsapp_enabled 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        וואטסאפ
                      </span>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        business.crm_enabled 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        CRM
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="flex items-center space-x-4 space-x-reverse">
                      <span>{business.stats?.customers || 0} לקוחות</span>
                      <span>{business.stats?.calls_today || 0} שיחות היום</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-left text-sm font-medium">
                    <div className="flex space-x-2 space-x-reverse">
                      <button
                        onClick={() => loginAsBusiness(business.id)}
                        className="text-blue-600 hover:text-blue-900 flex items-center"
                      >
                        <Eye className="w-4 h-4 ml-1" />
                        כניסה כעסק
                      </button>
                      <button
                        onClick={() => setEditingBusiness(business)}
                        className="text-indigo-600 hover:text-indigo-900 flex items-center"
                      >
                        <Edit className="w-4 h-4 ml-1" />
                        עריכה
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Business Modal */}
      {editingBusiness && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 text-center mb-4">
                עריכת הרשאות - {editingBusiness.name}
              </h3>
              
              <div className="space-y-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={editingBusiness.calls_enabled}
                    onChange={(e) => setEditingBusiness({
                      ...editingBusiness,
                      calls_enabled: e.target.checked
                    })}
                    className="ml-2 h-4 w-4 text-blue-600 rounded"
                  />
                  <span className="text-sm text-gray-700">מוקד שיחות</span>
                </label>
                
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={editingBusiness.whatsapp_enabled}
                    onChange={(e) => setEditingBusiness({
                      ...editingBusiness,
                      whatsapp_enabled: e.target.checked
                    })}
                    className="ml-2 h-4 w-4 text-blue-600 rounded"
                  />
                  <span className="text-sm text-gray-700">וואטסאפ</span>
                </label>
                
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={editingBusiness.crm_enabled}
                    onChange={(e) => setEditingBusiness({
                      ...editingBusiness,
                      crm_enabled: e.target.checked
                    })}
                    className="ml-2 h-4 w-4 text-blue-600 rounded"
                  />
                  <span className="text-sm text-gray-700">ניהול לקוחות (CRM)</span>
                </label>
              </div>
              
              <div className="flex justify-end space-x-3 space-x-reverse mt-6">
                <button
                  onClick={() => setEditingBusiness(null)}
                  className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400"
                >
                  ביטול
                </button>
                <button
                  onClick={() => updateBusinessPermissions(editingBusiness.id, {
                    calls_enabled: editingBusiness.calls_enabled,
                    whatsapp_enabled: editingBusiness.whatsapp_enabled,
                    crm_enabled: editingBusiness.crm_enabled
                  })}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  שמור
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminDashboard;