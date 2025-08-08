import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Phone, Play, Pause, Download, FileText, Clock, 
  Mic, User, Calendar, MessageSquare, Star,
  Volume2, PhoneCall, Activity, TrendingUp,
  ArrowUpRight, CheckCircle, AlertCircle,
  Search, Filter, Eye, EyeOff, Headphones,
  Volume1, MoreVertical, UserCheck, Building2,
  PhoneIncoming, PhoneOutgoing, Settings,
  BarChart3, Zap, Copy, Share2, Edit
} from 'lucide-react';

export default function ModernCalls() {
  const [userRole, setUserRole] = useState('business');
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingCall, setPlayingCall] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCall, setSelectedCall] = useState(null);
  const [showTranscription, setShowTranscription] = useState({});
  const [filterStatus, setFilterStatus] = useState('all');
  const [hasCallPermissions, setHasCallPermissions] = useState(true);
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState('all');

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadCalls(role);
  }, []);

  const loadCalls = async (role) => {
    try {
      // Check permissions based on business features
      await checkCallPermissions(role);
      
      // Load businesses for admin
      if (role === 'admin') {
        await loadBusinesses();
      }
      
      // Enhanced demo call data with full transcriptions
      const demoCalls = [
        {
          id: 1,
          customer_name: 'יוסי כהן',
          customer_phone: '050-1234567',
          duration: '2:34',
          status: 'completed',
          business_name: 'עסק ABC - ייעוץ',
          business_id: 1,
          direction: 'incoming',
          ai_response: 'שיחה הושלמה בהצלחה, הלקוח מעוניין בפגישה',
          transcription: `מערכת: שלום, הגעת לעסק ABC. איך אני יכול לעזור לך היום?

יוסי: שלום, אני יוסי כהן. שמעתי עליכם המלצות מצוינות ואני מעוניין לקבל מידע על השירותים שלכם.

מערכת: נהדר יוסי! אני שמח לשמוע שהגעת אלינו דרך המלצה. אנחנו מתמחים בשירותי ייעוץ עסקי ואסטרטגי. באיזה תחום אתה מעוניין בדיוק?

יוסי: אני מנהל חברת טכנולוגיה קטנה ואני מחפש ייעוץ בתחום השיווק הדיגיטלי. יש לנו מוצר טוב אבל אנחנו לא מצליחים להגיע ללקוחות.

מערכת: מבין לחלוטין. זה אתגר נפוץ בחברות טכנולוגיה. אנחנו עוזרים לחברות כמו שלך לבנות אסטרטגית שיווק יעילה. האם תרצה לקבוע פגישת ייעוץ ראשונית?

יוסי: כן, זה נשמע מעולה. מתי אפשר לקבוע?

מערכת: אני יכול לקבוע לך פגישה לשבוע הבא. האם יום שלישי בשעה 10:00 מתאים לך?

יוסי: מושלם! אני אשמח. איך אנחנו מתקדמים?

מערכת: נפלא! אני רושם אותך לפגישה ביום שלישי הקרוב בשעה 10:00. תקבל SMS אישור עם כל הפרטים. תודה רבה יוסי!`,
          recording_url: '/audio/demo_call_1.mp3',
          created_at: '2025-08-07 14:30:00',
          sentiment: 'positive',
          confidence_score: 0.87,
          tags: ['ייעוץ', 'טכנולוגיה', 'שיווק דיגיטלי', 'פגישה'],
          follow_up_required: true,
          appointment_scheduled: true,
          summary: 'לקוח מעוניין בשירותי ייעוץ שיווק דיגיטלי, נקבעה פגישה לשלישי 10:00'
        },
        {
          id: 2,
          customer_name: 'רחל לוי',
          customer_phone: '052-9876543',
          duration: '1:45',
          status: 'completed',
          business_name: 'עסק XYZ - מכירות',
          business_id: 2,
          direction: 'incoming',
          ai_response: 'הלקוח ביקש מידע נוסף, נשלח מייל עם פרטים',
          transcription: `מערכת: שלום וברוכה הבאה לעסק XYZ. איך אני יכול לעזור לך?

רחל: היי, אני רחל. שמעתי שיש לכם מוצרים מעניינים ואני רוצה לשמוע עוד.

מערכת: נהדר רחל! אני שמח שהתעניינת במוצרים שלנו. אנחנו מתמחים במכירת פתרונות טכנולוגיים לעסקים. איזה סוג של פתרון מחפשת?

רחל: אני מחפשת משהו לניהול לקוחות. יש לי עסק קטן ואני רוצה לארגן את כל המידע על הלקוחות שלי.

מערכת: מצוין! יש לנו פתרון CRM שמתאים בדיוק לעסקים כמו שלך. האם תרצי שאני אשלח לך מידע מפורט על המערכת?

רחל: כן, זה יהיה נהדר. ואם אפשר גם מחירים.

מערכת: בוודאי. אני אשלח לך מייל עם כל המידע הרלוונטי. תודה רחל!`,
          recording_url: '/audio/demo_call_2.mp3',
          created_at: '2025-08-07 13:15:00',
          sentiment: 'positive',
          confidence_score: 0.73,
          tags: ['CRM', 'טכנולוגיה', 'ניהול לקוחות'],
          follow_up_required: true,
          appointment_scheduled: false,
          summary: 'בירור על פתרונות CRM, הלקוח מעוניין לקבל מידע נוסף במייל'
        },
        {
          id: 3,
          customer_name: 'דני אברהם',
          customer_phone: '053-5555555',
          duration: '0:23',
          status: 'failed',
          business_name: 'עסק ABC - ייעוץ',
          business_id: 1,
          direction: 'incoming',
          ai_response: 'שיחה קצרה מדי, הלקוח התנתק מהר',
          transcription: `מערכת: שלום, הגעת לעסק ABC. איך אני יכול לעזור לך היום?

דני: לא זמין כרגע... [השיחה הסתיימה]`,
          recording_url: '/audio/demo_call_3.mp3',
          created_at: '2025-08-07 12:45:00',
          sentiment: 'neutral',
          confidence_score: 0.21,
          tags: ['שיחה קצרה', 'התנתקות'],
          follow_up_required: false,
          appointment_scheduled: false,
          summary: 'שיחה קצרה, הלקוח התנתק מיד - אין מידע משמעותי'
        }
      ];
      
      setCalls(demoCalls);
      setLoading(false);
    } catch (error) {
      console.error('Error loading calls:', error);
      setLoading(false);
    }
  };

  const checkCallPermissions = async (role) => {
    // In real implementation, check if business has call features enabled
    if (role === 'business') {
      try {
        const response = await fetch('/api/business/features');
        const features = await response.json();
        setHasCallPermissions(features.calls_enabled || false);
      } catch (error) {
        setHasCallPermissions(false);
      }
    } else {
      setHasCallPermissions(true); // Admin always has access
    }
  };

  const loadBusinesses = async () => {
    // Demo businesses data
    const demoBusinesses = [
      { id: 1, name: 'עסק ABC - ייעוץ', calls_enabled: true },
      { id: 2, name: 'עסק XYZ - מכירות', calls_enabled: true },
      { id: 3, name: 'עסק 123 - שירותים', calls_enabled: false }
    ];
    setBusinesses(demoBusinesses);
  };

  const toggleTranscription = (callId) => {
    setShowTranscription(prev => ({
      ...prev,
      [callId]: !prev[callId]
    }));
  };

  const filteredCalls = calls.filter(call => {
    const matchesSearch = call.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         call.customer_phone?.includes(searchTerm) ||
                         call.transcription?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         call.summary?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = filterStatus === 'all' || call.status === filterStatus;
    
    const matchesBusiness = userRole === 'admin' 
      ? (selectedBusiness === 'all' || call.business_id?.toString() === selectedBusiness)
      : true;
    
    return matchesSearch && matchesStatus && matchesBusiness;
  });

  const copyTranscription = (transcription) => {
    navigator.clipboard.writeText(transcription);
  };

  const downloadRecording = (recordingUrl, customerName) => {
    const link = document.createElement('a');
    link.href = recordingUrl;
    link.download = `recording_${customerName}.mp3`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

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

  if (!hasCallPermissions) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center bg-red-50 p-8 rounded-2xl border border-red-200">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-red-800 mb-2">אין הרשאה למערכת שיחות</h3>
            <p className="text-red-600">העסק שלך לא כולל תכונת מערכת שיחות AI. צור קשר לשדרוג החבילה.</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

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

        {/* Advanced Search and Filters */}
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex flex-wrap gap-4 items-center justify-between">
            {/* Search Bar */}
            <div className="relative flex-1 min-w-[300px]">
              <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
              <input
                type="text"
                placeholder="חיפוש בשם לקוח, טלפון, תמלול או סיכום..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              />
            </div>
            
            {/* Status Filter */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="completed">הושלמו</option>
              <option value="failed">נכשלו</option>
              <option value="in_progress">בתהליך</option>
            </select>

            {/* Business Filter (Admin only) */}
            {userRole === 'admin' && (
              <select
                value={selectedBusiness}
                onChange={(e) => setSelectedBusiness(e.target.value)}
                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              >
                <option value="all">כל העסקים</option>
                {businesses.map(business => (
                  <option key={business.id} value={business.id.toString()}>
                    {business.name}
                  </option>
                ))}
              </select>
            )}
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

                        <button 
                          onClick={() => downloadRecording(call.recording_url, call.customer_name)}
                          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-all duration-200"
                        >
                          <Download className="w-4 h-4" />
                          הורד הקלטה
                        </button>

                        <button 
                          onClick={() => copyTranscription(call.transcription)}
                          className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-xl hover:bg-gray-600 transition-all duration-200"
                        >
                          <Copy className="w-4 h-4" />
                          העתק תמלול
                        </button>

                        <button 
                          onClick={() => toggleTranscription(call.id)}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-xl hover:bg-indigo-600 transition-all duration-200"
                        >
                          {showTranscription[call.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          {showTranscription[call.id] ? 'הסתר תמלול' : 'הצג תמלול מלא'}
                        </button>

                        <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600 transition-all duration-200">
                          <MessageSquare className="w-4 h-4" />
                          שלח WhatsApp
                        </button>
                      </div>

                      {/* Full Transcription Expandable */}
                      {showTranscription[call.id] && call.transcription && (
                        <div className="mt-4 bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
                          <div className="flex items-center justify-between mb-4">
                            <h4 className="font-bold text-gray-900 flex items-center gap-2">
                              <Headphones className="w-5 h-5 text-green-500" />
                              תמלול מלא של השיחה
                            </h4>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => copyTranscription(call.transcription)}
                                className="text-blue-500 hover:text-blue-700"
                              >
                                <Copy className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => downloadRecording(call.recording_url, call.customer_name)}
                                className="text-green-500 hover:text-green-700"
                              >
                                <Download className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                            <div className="space-y-3">
                              {call.transcription.split('\n').map((line, index) => {
                                if (!line.trim()) return null;
                                const isSystem = line.includes('מערכת:');
                                const isCustomer = !isSystem && line.includes(':');
                                
                                return (
                                  <div key={index} className={`flex gap-3 ${isSystem ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-[80%] p-3 rounded-2xl ${
                                      isSystem 
                                        ? 'bg-blue-500 text-white ml-4' 
                                        : 'bg-white text-gray-900 border border-gray-200 mr-4'
                                    }`}>
                                      <div className="text-sm font-medium mb-1">
                                        {isSystem ? '🤖 מערכת AI' : '👤 לקוח'}
                                      </div>
                                      <div className="text-sm leading-relaxed">
                                        {line.replace(/^[^:]+:\s*/, '')}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      )}
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