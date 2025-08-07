import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Phone, Play, Pause, Download, FileText, Clock, 
  Mic, User, Calendar, MessageSquare, Star,
  Volume2, PhoneCall, Activity, TrendingUp,
  ArrowUpRight, CheckCircle, AlertCircle
} from 'lucide-react';

export default function ModernCalls() {
  const [userRole, setUserRole] = useState('business');
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingCall, setPlayingCall] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadCalls(role);
  }, []);

  const loadCalls = async (role) => {
    try {
      // Demo call data
      const demoCalls = [
        {
          id: 1,
          customer_name: 'יוסי כהן',
          customer_phone: '050-1234567',
          duration: '2:34',
          status: 'completed',
          ai_response: 'שיחה הושלמה בהצלחה, הלקוח מעוניין בפגישה',
          transcription: 'שלום, אני מעוניין לקבל מידע על השירותים שלכם...',
          recording_url: '/audio/demo_call_1.mp3',
          created_at: '2025-08-07 14:30:00',
          sentiment: 'positive',
          summary: 'לקוח מעוניין בשירותי ייעוץ, נקבעה פגישה לשבוע הבא'
        },
        {
          id: 2,
          customer_name: 'רחל לוי',
          customer_phone: '052-9876543',
          duration: '1:45',
          status: 'completed',
          ai_response: 'הלקוח ביקש מידע נוסף, נשלח מייל עם פרטים',
          transcription: 'היי, שמעתי עליכם המלצות טובות...',
          recording_url: '/audio/demo_call_2.mp3',
          created_at: '2025-08-07 13:15:00',
          sentiment: 'neutral',
          summary: 'בירור ראשוני על השירותים, הלקוח רוצה לחזור אלינו'
        },
        {
          id: 3,
          customer_name: 'דני אברהם',
          customer_phone: '053-5555555',
          duration: '0:23',
          status: 'failed',
          ai_response: 'שיחה קצרה מדי, לא ניתן היה להבין את הבקשה',
          transcription: 'לא זמין כרגע...',
          recording_url: '/audio/demo_call_3.mp3',
          created_at: '2025-08-07 12:45:00',
          sentiment: 'neutral',
          summary: 'שיחה קצרה, הלקוח לא היה זמין'
        }
      ];
      
      setCalls(demoCalls);
      setLoading(false);
    } catch (error) {
      console.error('Error loading calls:', error);
      setLoading(false);
    }
  };

  const filteredCalls = calls.filter(call =>
    call.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    call.customer_phone?.includes(searchTerm)
  );

  const handlePlayPause = (callId) => {
    if (playingCall === callId) {
      setPlayingCall(null);
    } else {
      setPlayingCall(callId);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'in_progress': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'failed': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed': return 'הושלמה';
      case 'in_progress': return 'בתהליך';
      case 'failed': return 'נכשלה';
      default: return 'לא ידוע';
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive': return 'text-green-600';
      case 'negative': return 'text-red-600';
      case 'neutral': return 'text-yellow-600';
      default: return 'text-gray-600';
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'positive': return CheckCircle;
      case 'negative': return AlertCircle;
      case 'neutral': return Clock;
      default: return Clock;
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען רשימת שיחות...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-green-600 to-blue-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Phone className="w-10 h-10" />
                📞 מערכת שיחות AI
              </h1>
              <p className="text-green-100 text-lg">
                ניתוח ותמלול שיחות אוטומטי עם בינה מלאכותית
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{calls.length}</div>
              <div className="text-green-100">שיחות היום</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">שיחות מוצלחות</p>
                <p className="text-3xl font-bold text-green-600">
                  {calls.filter(c => c.status === 'completed').length}
                </p>
                <p className="text-green-500 text-sm flex items-center gap-1">
                  <ArrowUpRight className="w-4 h-4" />
                  +23% השבוע
                </p>
              </div>
              <CheckCircle className="w-12 h-12 text-green-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">זמן ממוצע</p>
                <p className="text-3xl font-bold text-blue-600">2:15</p>
                <p className="text-blue-500 text-sm flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  דקות
                </p>
              </div>
              <Activity className="w-12 h-12 text-blue-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">שביעות רצון</p>
                <p className="text-3xl font-bold text-purple-600">94%</p>
                <p className="text-purple-500 text-sm flex items-center gap-1">
                  <Star className="w-4 h-4" />
                  חיובי
                </p>
              </div>
              <TrendingUp className="w-12 h-12 text-purple-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">המרה ללידים</p>
                <p className="text-3xl font-bold text-orange-600">78%</p>
                <p className="text-orange-500 text-sm flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" />
                  מעולה
                </p>
              </div>
              <PhoneCall className="w-12 h-12 text-orange-500" />
            </div>
          </div>
        </div>

        {/* Search Bar */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="relative max-w-md">
            <Phone className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              placeholder="חיפוש לפי שם לקוח או מספר טלפון..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Calls List */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center">
                <Mic className="w-4 h-4 text-white" />
              </div>
              שיחות אחרונות ({filteredCalls.length})
            </h2>
          </div>

          <div className="space-y-4 p-6">
            {filteredCalls.map((call) => {
              const SentimentIcon = getSentimentIcon(call.sentiment);
              return (
                <div key={call.id} className="bg-gray-50 rounded-2xl p-6 hover:bg-gray-100 transition-all duration-200 border border-gray-100">
                  <div className="flex items-start gap-4">
                    {/* Avatar */}
                    <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                      {call.customer_name?.charAt(0) || 'L'}
                    </div>

                    {/* Call Info */}
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-bold text-gray-900">{call.customer_name}</h3>
                          <p className="text-sm text-gray-600 flex items-center gap-2">
                            <Phone className="w-4 h-4" />
                            {call.customer_phone}
                            <span className="mx-2">•</span>
                            <Clock className="w-4 h-4" />
                            {call.duration}
                            <span className="mx-2">•</span>
                            {new Date(call.created_at).toLocaleString('he-IL')}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(call.status)}`}>
                            {getStatusText(call.status)}
                          </span>
                          <SentimentIcon className={`w-5 h-5 ${getSentimentColor(call.sentiment)}`} />
                        </div>
                      </div>

                      {/* Summary */}
                      <div className="bg-white rounded-xl p-4 mb-4 border border-gray-200">
                        <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                          <MessageSquare className="w-4 h-4 text-blue-500" />
                          סיכום שיחה
                        </h4>
                        <p className="text-gray-700 text-sm">{call.summary}</p>
                      </div>

                      {/* AI Response */}
                      <div className="bg-blue-50 rounded-xl p-4 mb-4 border border-blue-200">
                        <h4 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                          <Star className="w-4 h-4 text-blue-600" />
                          תגובת AI
                        </h4>
                        <p className="text-blue-800 text-sm">{call.ai_response}</p>
                      </div>

                      {/* Transcription */}
                      {call.transcription && (
                        <div className="bg-gray-100 rounded-xl p-4 mb-4">
                          <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-600" />
                            תמלול
                          </h4>
                          <p className="text-gray-700 text-sm italic">"{call.transcription}"</p>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handlePlayPause(call.id)}
                          className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-200 ${
                            playingCall === call.id
                              ? 'bg-red-500 text-white hover:bg-red-600'
                              : 'bg-green-500 text-white hover:bg-green-600'
                          }`}
                        >
                          {playingCall === call.id ? (
                            <>
                              <Pause className="w-4 h-4" />
                              עצור
                            </>
                          ) : (
                            <>
                              <Play className="w-4 h-4" />
                              השמע
                            </>
                          )}
                        </button>

                        <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-all duration-200">
                          <Download className="w-4 h-4" />
                          הורד
                        </button>

                        <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600 transition-all duration-200">
                          <MessageSquare className="w-4 h-4" />
                          שלח WhatsApp
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}

            {filteredCalls.length === 0 && (
              <div className="text-center py-16">
                <div className="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <Phone className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">אין שיחות</h3>
                <p className="text-gray-500 mb-6">לא נמצאו שיחות התואמות את החיפוש</p>
                <div className="text-sm text-gray-400">
                  השיחות יופיעו כאן אוטומטית כשמישהו יתקשר למספר העסק
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}