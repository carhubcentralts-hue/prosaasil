import React, { useState, useEffect } from 'react';
import { Phone, ArrowLeft, Play, Pause, Download, Calendar, Clock, User } from 'lucide-react';

const CallsPage = () => {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);

  useEffect(() => {
    // טוען רשימת שיחות
    const fetchCalls = () => {
      // נתונים לדוגמה
      const demoCallsData = [
        {
          id: 1,
          caller: '+972-50-123-4567',
          customerName: 'יוסי כהן',
          duration: '2:45',
          date: '2025-08-02',
          time: '14:30',
          status: 'completed',
          transcript: 'שלום, אני מתקשר בקשר לשירותי הטכנולוגיה שלכם...',
          aiResponse: 'שלום יוסי, אני שמח לעזור לך עם שירותי הטכנולוגיה שלנו...',
          recordingUrl: '/recordings/call_1.mp3'
        },
        {
          id: 2,
          caller: '+972-54-987-6543',
          customerName: 'שרה לוי',
          duration: '4:12',
          date: '2025-08-02',
          time: '13:15',
          status: 'completed',
          transcript: 'היי, שמעתי שאתם מציעים פתרונות AI...',
          aiResponse: 'שלום שרה, בהחלט! אנחנו מתמחים בפתרונות AI מתקדמים...',
          recordingUrl: '/recordings/call_2.mp3'
        },
        {
          id: 3,
          caller: '+972-52-111-2222',
          customerName: 'דוד ישראלי',
          duration: '1:30',
          date: '2025-08-02',
          time: '12:00',
          status: 'missed',
          transcript: null,
          aiResponse: null,
          recordingUrl: null
        }
      ];
      
      setCalls(demoCallsData);
      setLoading(false);
    };

    fetchCalls();
  }, []);

  const handleBackToDashboard = () => {
    window.location.href = '/business/dashboard';
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'missed': return 'text-red-600 bg-red-100';
      case 'ongoing': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'completed': return 'הושלמה';
      case 'missed': return 'החמיצה';
      case 'ongoing': return 'בהמתנה';
      default: return 'לא ידוע';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Phone className="w-8 h-8 text-blue-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-600">טוען שיחות...</p>
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
              <h1 className="text-3xl font-bold text-gray-900">מערכת שיחות AI</h1>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
                {calls.length} שיחות היום
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{calls.length}</p>
                <p className="text-gray-600">סה"כ שיחות היום</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Play className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{calls.filter(c => c.status === 'completed').length}</p>
                <p className="text-gray-600">שיחות שהושלמו</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Clock className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">
                  {calls.filter(c => c.duration).reduce((acc, call) => {
                    const [min, sec] = call.duration.split(':').map(Number);
                    return acc + min + (sec / 60);
                  }, 0).toFixed(1)}
                </p>
                <p className="text-gray-600">דקות שיחה</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <User className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{calls.filter(c => c.status === 'missed').length}</p>
                <p className="text-gray-600">שיחות שהוחמצו</p>
              </div>
            </div>
          </div>
        </div>

        {/* Calls List */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-xl font-bold text-gray-900">רשימת שיחות</h2>
          </div>
          <div className="p-6">
            {calls.length === 0 ? (
              <div className="text-center py-8">
                <Phone className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">אין שיחות להצגה</p>
              </div>
            ) : (
              <div className="space-y-4">
                {calls.map((call) => (
                  <div key={call.id} className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4 space-x-reverse">
                        <div className="flex-1">
                          <div className="flex items-center">
                            <h3 className="text-lg font-bold text-gray-900 ml-3">{call.customerName}</h3>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(call.status)}`}>
                              {getStatusText(call.status)}
                            </span>
                          </div>
                          <p className="text-gray-600">{call.caller}</p>
                          
                          <div className="flex items-center mt-2 space-x-4 space-x-reverse text-sm text-gray-500">
                            <div className="flex items-center">
                              <Calendar className="w-4 h-4 ml-1" />
                              <span>{call.date}</span>
                            </div>
                            <div className="flex items-center">
                              <Clock className="w-4 h-4 ml-1" />
                              <span>{call.time}</span>
                            </div>
                            {call.duration && (
                              <div className="flex items-center">
                                <Phone className="w-4 h-4 ml-1" />
                                <span>{call.duration}</span>
                              </div>
                            )}
                          </div>
                          
                          {call.transcript && (
                            <div className="mt-3 p-3 bg-gray-100 rounded-lg">
                              <p className="text-sm text-gray-700 line-clamp-2">
                                <strong>לקוח:</strong> {call.transcript}
                              </p>
                              {call.aiResponse && (
                                <p className="text-sm text-blue-700 mt-2 line-clamp-2">
                                  <strong>AI:</strong> {call.aiResponse}
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2 space-x-reverse">
                        {call.recordingUrl && (
                          <button
                            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            title="השמע הקלטה"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                        {call.recordingUrl && (
                          <button
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                            title="הורד הקלטה"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CallsPage;