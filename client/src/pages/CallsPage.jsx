import React from 'react';
import { ArrowLeft, Phone, Play, Download, Clock } from 'lucide-react';

const CallsPage = () => {
  const calls = [
    {
      id: 1,
      customerName: 'דוד כהן',
      phone: '+972-50-123-4567',
      duration: '5:23',
      timestamp: '2025-08-03 14:15',
      status: 'completed',
      recording: true,
      summary: 'לקוח מעוניין בהצעת מחיר לשירותי עיצוב'
    },
    {
      id: 2,
      customerName: 'שרה לוי',
      phone: '+972-54-987-6543',
      duration: '2:45',
      timestamp: '2025-08-03 13:30',
      status: 'missed',
      recording: false,
      summary: 'שיחה שלא נענתה'
    },
    {
      id: 3,
      customerName: 'מיכאל אברהם',
      phone: '+972-52-555-1234',
      duration: '8:12',
      timestamp: '2025-08-03 12:45',
      status: 'completed',
      recording: true,
      summary: 'מעקב אחר פרויקט קיים ותיאום פגישה'
    }
  ];

  const goBack = () => {
    window.location.href = '/admin/dashboard';
  };

  const handlePlayRecording = (callId) => {
    alert(`נגינת הקלטה ${callId} - יושם בעתיד`);
  };

  const handleDownloadRecording = (callId) => {
    alert(`הורדת הקלטה ${callId} - יושם בעתיד`);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'missed':
        return 'bg-red-100 text-red-800';
      case 'ongoing':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
        return 'הושלמה';
      case 'missed':
        return 'נפספסה';
      case 'ongoing':
        return 'בשיחה';
      default:
        return 'לא ידוע';
    }
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
                <h1 className="text-3xl font-bold text-gray-900">📞 כל השיחות - מערכת כללית</h1>
                <p className="text-gray-600 mt-1">מעקב אחר כל השיחות במערכת</p>
              </div>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">{calls.filter(c => c.status === 'completed').length}</p>
                <p className="text-sm text-gray-600">הושלמו</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-600">{calls.filter(c => c.status === 'missed').length}</p>
                <p className="text-sm text-gray-600">נפספסו</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* סיכום שיחות */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{calls.length}</p>
                <p className="text-gray-600">סה"כ שיחות היום</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Clock className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">16:20</p>
                <p className="text-gray-600">זמן שיחה כולל</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Play className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{calls.filter(c => c.recording).length}</p>
                <p className="text-gray-600">הקלטות זמינות</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">5:23</p>
                <p className="text-gray-600">ממוצע שיחה</p>
              </div>
            </div>
          </div>
        </div>

        {/* רשימת שיחות */}
        <div className="bg-white rounded-xl shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">רשימת שיחות אחרונות</h2>
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
                      זמן השיחה
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      משך
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      סטטוס
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      תקציר
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      הקלטה
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {calls.map((call) => (
                    <tr key={call.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{call.customerName}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600" dir="ltr">{call.phone}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{call.timestamp}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{call.duration}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(call.status)}`}>
                          {getStatusText(call.status)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-600 max-w-xs truncate">{call.summary}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {call.recording ? (
                          <div className="flex space-x-2 space-x-reverse">
                            <button
                              onClick={() => handlePlayRecording(call.id)}
                              className="text-blue-600 hover:text-blue-900 p-1 rounded"
                              title="נגן הקלטה"
                            >
                              <Play className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDownloadRecording(call.id)}
                              className="text-green-600 hover:text-green-900 p-1 rounded"
                              title="הורד הקלטה"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-sm">אין הקלטה</span>
                        )}
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

export default CallsPage;