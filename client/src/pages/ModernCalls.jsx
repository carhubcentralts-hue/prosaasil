import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Phone, Search, FileText, Clock, Mic, User, Calendar, 
  MessageSquare, Star, Activity, TrendingUp, ArrowUpRight, 
  CheckCircle, AlertCircle, Filter, Eye, EyeOff, UserCheck, 
  Building2, Settings, BarChart3, Copy, Share2, Edit,
  PhoneIncoming, PhoneOutgoing, Volume2, ChevronDown, MoreVertical
} from 'lucide-react';

export default function ModernCalls() {
  const [userRole, setUserRole] = useState('business');
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
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
      await checkCallPermissions(role);
      
      if (role === 'admin') {
        await loadBusinesses();
      }
      
      // Enhanced demo call data with full transcriptions and chat-like format
      const demoCalls = [
        {
          id: 1,
          customer_name: 'יוסי כהן',
          customer_phone: '050-1234567',
          business_name: 'עסק ABC - ייעוץ',
          business_id: 1,
          call_time: '2025-08-07 14:30:15',
          duration: '00:02:45',
          status: 'completed',
          transcription: 'שלום, אני מחפש שירותי ייעוץ עסקי',
          summary: 'לקוח מעוניין בשירותי ייעוץ עסקי, ביקש פרטים נוספים על החבילות הזמינות',
          sentiment: 'positive',
          action_items: ['שליחת הצעת מחיר', 'קביעת פגישת המשך'],
          conversation_turns: [
            { speaker: 'system', text: 'שלום! תודה שהתקשרת. איך אני יכול לעזור לך היום?' },
            { speaker: 'customer', text: 'שלום, אני מחפש שירותי ייעוץ עסקי' },
            { speaker: 'system', text: 'נהדר! אנחנו מציעים מגוון שירותי ייעוץ. איזה תחום מעניין אותך במיוחד?' },
            { speaker: 'customer', text: 'אני צריך עזרה עם תכנון אסטרטגי לעסק שלי' },
            { speaker: 'system', text: 'מצוין! תכנון אסטרטגי הוא אחד מתחומי ההתמחות שלנו. אשלח לך הצעת מחיר מפורטת' },
            { speaker: 'customer', text: 'נשמע טוב, תודה רבה!' }
          ],
          next_actions: ['שלח הצעת מחיר', 'קבע פגישת המשך'],
          lead_score: 85
        },
        {
          id: 2,
          customer_name: 'שרה לוי',
          customer_phone: '052-9876543',
          business_name: 'עסק XYZ - מכירות',
          business_id: 2,
          call_time: '2025-08-07 16:20:30',
          duration: '00:01:30',
          status: 'completed',
          transcription: 'אני רוצה לבטל את השירות',
          summary: 'לקוח ביקש לבטל שירות, נדרש מעקב צוות שירות לקוחות',
          sentiment: 'negative',
          action_items: ['העברה למוקד שירות לקוחות', 'בדיקת סיבת הביטול'],
          conversation_turns: [
            { speaker: 'system', text: 'שלום! איך אני יכול לעזור?' },
            { speaker: 'customer', text: 'אני רוצה לבטל את השירות' },
            { speaker: 'system', text: 'אני מצטער לשמוע. אוכל לעזור לך עם הביטול. האם יש בעיה ספציפית?' },
            { speaker: 'customer', text: 'לא מרוצה מהשירות' },
            { speaker: 'system', text: 'אני מבין. אעביר אותך למחלקת שירות לקוחות שיטפלו בבקשה' }
          ],
          next_actions: ['העבר לשירות לקוחות', 'בדוק סיבת חוסר שביעות רצון'],
          lead_score: 20
        },
        {
          id: 3,
          customer_name: 'דני אברהם',
          customer_phone: '053-5555555',
          business_name: 'עסק 123 - טכנולוגיה',
          business_id: 3,
          call_time: '2025-08-07 18:45:00',
          duration: '00:03:20',
          status: 'completed',
          transcription: 'מעוניין בפתרונות טכנולוגיים מתקדמים',
          summary: 'לקוח חדש מעוניין בפתרונות טכנולוגיים, פוטנציאל גבוה',
          sentiment: 'positive',
          action_items: ['הכנת הצגה טכנית', 'קביעת פגישת הדגמה'],
          conversation_turns: [
            { speaker: 'system', text: 'שלום! תודה שהתקשרת לעסק 123' },
            { speaker: 'customer', text: 'שלום, מעוניין בפתרונות טכנולוגיים מתקדמים' },
            { speaker: 'system', text: 'מעולה! אנחנו מתמחים בפתרונות טכנולוגיים מתקדמים. איזה סוג פתרון מעניין אותך?' },
            { speaker: 'customer', text: 'אני צריך מערכת ניהול מתקדמת לחברה שלי' },
            { speaker: 'system', text: 'נשמע מושלם! אשמח לקבוע פגישת הדגמה כדי להראות לך את המערכות שלנו' },
            { speaker: 'customer', text: 'כן, זה יהיה נהדר' },
            { speaker: 'system', text: 'מצוין! אתאם איתך פגישה בהקדם האפשרי' }
          ],
          next_actions: ['קבע פגישת הדגמה', 'הכן הצגה טכנית'],
          lead_score: 90
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
    // Simulate business permission check
    if (role === 'business') {
      // Check if business has calls feature enabled
      const businessData = { calls_enabled: true }; // This would come from API
      setHasCallPermissions(businessData.calls_enabled);
    } else {
      setHasCallPermissions(true); // Admin always has access
    }
  };

  const loadBusinesses = async () => {
    const demoBusinesses = [
      { id: 1, name: 'עסק ABC - ייעוץ', calls_enabled: true },
      { id: 2, name: 'עסק XYZ - מכירות', calls_enabled: true },
      { id: 3, name: 'עסק 123 - טכנולוגיה', calls_enabled: true }
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

  const copyTranscription = async (transcription) => {
    try {
      await navigator.clipboard.writeText(transcription);
      ;
    } catch (error) {
      console.error('שגיאה בהעתקת התמלול:', error);
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

  const getLeadScoreColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  if (!hasCallPermissions) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center bg-red-50 p-8 rounded-2xl border border-red-200 max-w-md">
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
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Phone className="w-10 h-10" />
                📞 מערכת שיחות AI
              </h1>
              <p className="text-blue-100 text-lg">
                תמלולים מלאים ומעקב שיחות עם בינה מלאכותית
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{calls.length}</div>
              <div className="text-blue-100">שיחות השבוע</div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">שיחות הושלמו</p>
                <p className="text-3xl font-bold text-green-600">
                  {calls.filter(c => c.status === 'completed').length}
                </p>
              </div>
              <CheckCircle className="w-12 h-12 text-green-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">ליידים איכותיים</p>
                <p className="text-3xl font-bold text-purple-600">
                  {calls.filter(c => c.lead_score >= 80).length}
                </p>
              </div>
              <Star className="w-12 h-12 text-purple-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">רגש חיובי</p>
                <p className="text-3xl font-bold text-blue-600">
                  {calls.filter(c => c.sentiment === 'positive').length}
                </p>
              </div>
              <TrendingUp className="w-12 h-12 text-blue-500" />
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">זמן ממוצע</p>
                <p className="text-3xl font-bold text-orange-600">2:32</p>
              </div>
              <Clock className="w-12 h-12 text-orange-500" />
            </div>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
          <div className="flex flex-wrap gap-4 items-center justify-between">
            <div className="relative flex-1 min-w-[300px]">
              <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
              <input
                type="text"
                placeholder="חיפוש שיחות (שם, טלפון, תמלול, סיכום)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            
            <div className="flex gap-4">
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">כל הסטטוסים</option>
                <option value="completed">הושלמו</option>
                <option value="in_progress">בתהליך</option>
                <option value="failed">נכשלו</option>
              </select>

              {userRole === 'admin' && (
                <select
                  value={selectedBusiness}
                  onChange={(e) => setSelectedBusiness(e.target.value)}
                  className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
        </div>

        {/* Calls List */}
        <div className="space-y-6">
          {filteredCalls.map((call) => {
            const SentimentIcon = getSentimentIcon(call.sentiment);
            return (
              <div key={call.id} className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
                <div className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                        {call.customer_name.charAt(0)}
                      </div>
                      
                      <div>
                        <h3 className="text-lg font-bold text-gray-900 mb-1">{call.customer_name}</h3>
                        <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
                          <span className="flex items-center gap-1">
                            <Phone className="w-4 h-4" />
                            {call.customer_phone}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {new Date(call.call_time).toLocaleString('he-IL')}
                          </span>
                          <span className="flex items-center gap-1">
                            <Volume2 className="w-4 h-4" />
                            {call.duration}
                          </span>
                        </div>
                        {userRole === 'admin' && call.business_name && (
                          <div className="flex items-center gap-1 text-sm text-purple-600">
                            <Building2 className="w-4 h-4" />
                            {call.business_name}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(call.status)}`}>
                        {getStatusText(call.status)}
                      </span>
                      
                      <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getLeadScoreColor(call.lead_score)}`}>
                        <Star className="w-4 h-4 mr-1" />
                        {call.lead_score}%
                      </div>
                    </div>
                  </div>

                  {/* Summary */}
                  <div className="bg-gray-50 rounded-xl p-4 mb-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-gray-900">סיכום השיחה</h4>
                      <div className="flex items-center gap-2">
                        <SentimentIcon className={`w-5 h-5 ${getSentimentColor(call.sentiment)}`} />
                        <span className={`text-sm font-medium ${getSentimentColor(call.sentiment)}`}>
                          {call.sentiment === 'positive' ? 'חיובי' : 
                           call.sentiment === 'negative' ? 'שלילי' : 'נייטרלי'}
                        </span>
                      </div>
                    </div>
                    <p className="text-gray-700">{call.summary}</p>
                  </div>

                  {/* Action Items */}
                  {call.action_items && call.action_items.length > 0 && (
                    <div className="mb-4">
                      <h4 className="font-medium text-gray-900 mb-2">פעולות נדרשות</h4>
                      <div className="flex flex-wrap gap-2">
                        {call.action_items.map((item, index) => (
                          <span key={index} className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-yellow-100 text-yellow-800 border border-yellow-200">
                            <ArrowUpRight className="w-4 h-4 mr-1" />
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Transcription Toggle */}
                  <div className="flex items-center gap-3 mb-4">
                    <button
                      onClick={() => toggleTranscription(call.id)}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600"
                    >
                      {showTranscription[call.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      {showTranscription[call.id] ? 'הסתר תמלול' : 'הצג תמלול מלא'}
                    </button>

                    <button
                      onClick={() => copyTranscription(call.conversation_turns?.map(turn => 
                        `${turn.speaker === 'system' ? 'מערכת' : 'לקוח'}: ${turn.text}`
                      ).join('\n') || call.transcription)}
                      className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-xl hover:bg-green-600"
                    >
                      <Copy className="w-4 h-4" />
                      העתק תמלול
                    </button>

                    <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-xl hover:bg-purple-600">
                      <MessageSquare className="w-4 h-4" />
                      יצירת ליד
                    </button>
                  </div>

                  {/* Full Conversation */}
                  {showTranscription[call.id] && (
                    <div className="border-t border-gray-200 pt-4">
                      <h4 className="font-medium text-gray-900 mb-4">תמלול מלא - שיחה</h4>
                      <div className="bg-gray-50 rounded-xl p-4 max-h-96 overflow-y-auto">
                        <div className="space-y-3">
                          {call.conversation_turns ? (
                            call.conversation_turns.map((turn, index) => (
                              <div 
                                key={index} 
                                className={`flex ${turn.speaker === 'system' ? 'justify-start' : 'justify-end'}`}
                              >
                                <div className={`max-w-[70%] rounded-2xl p-3 ${
                                  turn.speaker === 'system' 
                                    ? 'bg-blue-500 text-white' 
                                    : 'bg-white text-gray-900 border border-gray-200'
                                }`}>
                                  <div className="text-xs opacity-75 mb-1">
                                    {turn.speaker === 'system' ? 'מערכת AI' : call.customer_name}
                                  </div>
                                  <div className="text-sm">{turn.text}</div>
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="text-gray-700">{call.transcription}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {filteredCalls.length === 0 && (
          <div className="text-center py-12">
            <Phone className="w-24 h-24 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-gray-900 mb-2">אין שיחות להצגה</h3>
            <p className="text-gray-500">
              {searchTerm ? 'לא נמצאו שיחות התואמות לחיפוש' : 'עדיין לא התקבלו שיחות במערכת'}
            </p>
          </div>
        )}
      </div>
    </ModernLayout>
  );
}