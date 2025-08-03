import React from 'react';
import { ArrowLeft, Users, Plus, Search, Filter } from 'lucide-react';

const CRMPage = () => {
  const customers = [
    {
      id: 1,
      name: 'דוד כהן',
      phone: '+972-50-123-4567',
      email: 'david.cohen@example.com',
      company: 'חברת טכנולוגיות',
      status: 'פעיל',
      lastContact: '2025-08-03'
    },
    {
      id: 2,
      name: 'שרה לוי',
      phone: '+972-54-987-6543',
      email: 'sarah.levy@example.com',
      company: 'סטודיו עיצוב',
      status: 'פוטנציאלי',
      lastContact: '2025-08-02'
    },
    {
      id: 3,
      name: 'מיכאל אברהם',
      phone: '+972-52-555-1234',
      email: 'michael.abraham@example.com',
      company: 'חברת ייעוץ',
      status: 'פעיל',
      lastContact: '2025-08-01'
    }
  ];

  const goBack = () => {
    window.location.href = '/admin/dashboard';
  };

  const handleAddCustomer = () => {
    alert('הוספת לקוח חדש - יושם בעתיד');
  };

  const getStatusColor = (status) => {
    return status === 'פעיל' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800';
  };

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={goBack}
                className="ml-4 p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                title="חזרה לדשבורד"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">📋 CRM ראשי - כל העסקים</h1>
                <p className="text-gray-600 mt-1">ניהול לקוחות כלל-מערכתי</p>
              </div>
            </div>
            <button
              onClick={handleAddCustomer}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center transition-colors"
            >
              <Plus className="w-5 h-5 ml-2" />
              הוסף לקוח
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* סרגל חיפוש וסינון */}
        <div className="bg-white rounded-xl shadow mb-8">
          <div className="p-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="חיפוש לקוחות..."
                  className="w-full pr-10 pl-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <button className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 flex items-center transition-colors">
                <Filter className="w-5 h-5 ml-2" />
                סינון
              </button>
            </div>
          </div>
        </div>

        {/* רשימת לקוחות */}
        <div className="bg-white rounded-xl shadow">
          <div className="p-6 border-b">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">רשימת לקוחות</h2>
              <div className="flex items-center">
                <Users className="w-5 h-5 text-gray-500 ml-2" />
                <span className="text-gray-600">{customers.length} לקוחות</span>
              </div>
            </div>
          </div>
          <div className="p-6">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      שם הלקוח
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      טלפון
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      אימייל
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      חברה
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      סטטוס
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      פעילות אחרונה
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {customers.map((customer) => (
                    <tr key={customer.id} className="hover:bg-gray-50 cursor-pointer">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{customer.name}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600" dir="ltr">{customer.phone}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{customer.email}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{customer.company}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(customer.status)}`}>
                          {customer.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {customer.lastContact}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CRMPage;