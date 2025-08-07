import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  Phone, 
  PhoneCall, 
  Clock, 
  ArrowLeft,
  PlayCircle,
  PauseCircle,
  Download,
  User,
  Calendar,
  MessageSquare
} from 'lucide-react';

const CallSystemPage = () => {
  const navigate = useNavigate();
  const [callLogs, setCallLogs] = useState([]);
  const [selectedCall, setSelectedCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [playingCall, setPlayingCall] = useState(null);

  useEffect(() => {
    loadCallLogs();
  }, []);

  const loadCallLogs = async () => {
    try {
      // נתוני דוגמה לשיחות
      const mockCallLogs = [
        {
          id: 1,
          caller_name: 'ישראל ישראלי',
          caller_number: '+972-50-1234567',
          call_time: '2025-08-06T14:30:00Z',
          duration: '3:45',
          status: 'completed',
          transcription: 'שלום, אני מעונין לקבל מידע על השירותים שלכם. האם אפשר לקבוע פגישה?',
          ai_response: 'שלום ישראל! בהחלט, אשמח לעזור לך. אנחנו מציעים שירותי ייעוץ עסקי מתקדמים. אפשר לקבוע פגישה למחר בשעה 10:00?',
          recording_url: '/recordings/call_001.mp3'
        },
        {
          id: 2,
          caller_name: 'שרה כהן',
          caller_number: '+972-52-9876543',
          call_time: '2025-08-06T13:15:00Z',
          duration: '2:20',
          status: 'missed',
          transcription: null,
          ai_response: null,
          recording_url: null
        },
        {
          id: 3,
          caller_name: 'דוד לוי',
          caller_number: '+972-53-5555555',
          call_time: '2025-08-06T11:45:00Z',
          duration: '5:12',
          status: 'completed',
          transcription: 'היי, רציתי לבדוק מה המחירים שלכם לשירות ניהול הרשתות החברתיות',
          ai_response: 'שלום דוד! המחירים שלנו מתחילים מ-2000 שקל לחודש לניהול בסיסי. אפשר לשלוח לך הצעת מחיר מפורטת?',
          recording_url: '/recordings/call_003.mp3'
        }
      ];

      setCallLogs(mockCallLogs);
    } catch (error) {
      console.error('Error loading call logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'missed': return 'text-red-600 bg-red-100';
      case 'in-progress': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed': return 'הושלמה';
      case 'missed': return 'לא נענתה';
      case 'in-progress': return 'בתהליך';
      default: return 'לא ידוע';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100 flex items-center justify-center" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
        <div className="text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          </div>
          <h3 className="text-3xl font-bold text-gray-900 mb-2">📞 מערכת שיחות AI</h3>
          <p className="text-gray-600 text-lg">טוען נתוני שיחות ומוקד...</p>
          <div className="mt-4 flex justify-center">
            <div className="bg-white rounded-full px-4 py-2 shadow-md">
              <span className="text-sm text-purple-600 font-medium">מערכת מוקד חכמה עם AI</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
      <div className="max-w-6xl mx-auto px-4 py-6">
        
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">
                📞 מערכת שיחות AI
              </h1>
              <p className="text-gray-600 text-lg mt-2">
                מוקד חכם עם בינה מלאכותית וניתוח שיחות מתקדם
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/admin/dashboard')}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-gray-500 to-gray-600 text-white rounded-xl hover:from-gray-600 hover:to-gray-700 shadow-lg transition-all"
                data-testid="button-back-dashboard"
              >
                <ArrowLeft className="w-5 h-5" />
                חזרה לדשבורד
              </button>
            </div>
          </div>
        </div>

        {/* Call Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center">
                <PhoneCall className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">שיחות שהושלמו</h3>
            </div>
            <p className="text-3xl font-bold text-green-600" data-testid="stat-completed-calls">
              {callLogs.filter(call => call.status === 'completed').length}
            </p>
          </div>
          
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 rounded-xl flex items-center justify-center">
                <Phone className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">שיחות שהוחמצו</h3>
            </div>
            <p className="text-3xl font-bold text-red-600" data-testid="stat-missed-calls">
              {callLogs.filter(call => call.status === 'missed').length}
            </p>
          </div>
          
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Clock className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">סך כל השיחות</h3>
            </div>
            <p className="text-3xl font-bold text-purple-600" data-testid="stat-total-calls">
              {callLogs.length}
            </p>
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Call Logs */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-indigo-50">
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-3">
                  <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center">
                    <Phone className="w-4 h-4 text-white" />
                  </div>
                  📋 יומן שיחות ({callLogs.length})
                </h2>
              </div>
              
              <div className="max-h-96 overflow-y-auto">
                {callLogs.map((call) => (
                  <div
                    key={call.id}
                    onClick={() => setSelectedCall(call)}
                    className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-purple-50 transition-all ${
                      selectedCall?.id === call.id ? 'bg-purple-100 border-r-4 border-r-purple-500 shadow-inner' : ''
                    }`}
                    data-testid={`call-${call.id}`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                        {call.caller_name?.charAt(0) || 'C'}
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900">
                          {call.caller_name}
                        </h4>
                        <p className="text-sm text-gray-600">
                          {call.caller_number}
                        </p>
                      </div>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(call.status)}`}>
                        {getStatusText(call.status)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded-full">
                        <Clock className="w-3 h-3" />
                        {call.duration || 'לא זמין'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(call.call_time).toLocaleDateString('he-IL')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* פרטי שיחה */}
          <div className="lg:col-span-2">
            {selectedCall ? (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200">
                <div className="p-6 border-b border-gray-200 bg-purple-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 font-hebrew mb-1">
                        {selectedCall.caller_name}
                      </h3>
                      <p className="text-gray-600 font-hebrew mb-2">
                        {selectedCall.caller_number}
                      </p>
                      <p className="text-sm text-gray-500 font-hebrew">
                        {new Date(selectedCall.call_time).toLocaleString('he-IL')}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {selectedCall.recording_url && (
                        <button 
                          onClick={() => setPlayingCall(playingCall === selectedCall.id ? null : selectedCall.id)}
                          className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 font-hebrew"
                        >
                          {playingCall === selectedCall.id ? <PauseCircle className="w-4 h-4" /> : <PlayCircle className="w-4 h-4" />}
                          {playingCall === selectedCall.id ? 'עצור' : 'השמע'}
                        </button>
                      )}
                      <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 font-hebrew">
                        <PhoneCall className="w-4 h-4" />
                        התקשר חזרה
                      </button>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-5 h-5 text-purple-600" />
                        <h4 className="font-medium text-gray-900 font-hebrew">משך שיחה</h4>
                      </div>
                      <p className="text-2xl font-bold text-purple-600">
                        {selectedCall.duration || 'לא זמין'}
                      </p>
                    </div>

                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <User className="w-5 h-5 text-green-600" />
                        <h4 className="font-medium text-gray-900 font-hebrew">סטטוס</h4>
                      </div>
                      <span className={`px-3 py-1 rounded-full text-sm font-hebrew ${getStatusColor(selectedCall.status)}`}>
                        {getStatusText(selectedCall.status)}
                      </span>
                    </div>

                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <Download className="w-5 h-5 text-blue-600" />
                        <h4 className="font-medium text-gray-900 font-hebrew">הקלטה</h4>
                      </div>
                      <p className="text-sm font-medium font-hebrew">
                        {selectedCall.recording_url ? 'זמינה' : 'לא זמינה'}
                      </p>
                    </div>
                  </div>

                  {selectedCall.transcription && (
                    <div className="mb-6">
                      <h4 className="font-bold text-gray-900 font-hebrew mb-3 flex items-center gap-2">
                        <MessageSquare className="w-5 h-5" />
                        תמליל השיחה:
                      </h4>
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <p className="text-gray-800 font-hebrew leading-relaxed">
                          "{selectedCall.transcription}"
                        </p>
                      </div>
                    </div>
                  )}

                  {selectedCall.ai_response && (
                    <div>
                      <h4 className="font-bold text-gray-900 font-hebrew mb-3 flex items-center gap-2">
                        <PhoneCall className="w-5 h-5 text-purple-600" />
                        תגובת AI:
                      </h4>
                      <div className="bg-purple-50 p-4 rounded-lg">
                        <p className="text-gray-800 font-hebrew leading-relaxed">
                          "{selectedCall.ai_response}"
                        </p>
                      </div>
                    </div>
                  )}

                  {!selectedCall.transcription && !selectedCall.ai_response && selectedCall.status === 'missed' && (
                    <div className="text-center py-8">
                      <Phone className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                      <h3 className="text-lg font-medium text-gray-500 font-hebrew mb-2">שיחה לא נענתה</h3>
                      <p className="text-sm text-gray-400 font-hebrew">אין תמליל או תגובה זמינים עבור שיחה זו</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 flex items-center justify-center h-96">
                <div className="text-center text-gray-500 font-hebrew">
                  <Phone className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <h3 className="text-lg font-medium mb-2">בחר שיחה לצפייה</h3>
                  <p className="text-sm">לחץ על שיחה מהרשימה כדי לראות פרטים</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CallSystemPage;