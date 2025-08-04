import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Phone, 
  PhoneCall, 
  PhoneIncoming, 
  PhoneOutgoing,
  Play,
  Pause,
  Download,
  MessageSquare,
  Clock,
  User,
  Calendar,
  Filter,
  Search,
  Volume2,
  FileText,
  Mic,
  MicOff,
  CheckCircle,
  AlertCircle,
  MoreHorizontal
} from 'lucide-react';

const CallsManagement = ({ businessId, isAdmin = false }) => {
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [selectedCall, setSelectedCall] = useState(null);
  const [playingCall, setPlayingCall] = useState(null);
  const [showTranscriptionModal, setShowTranscriptionModal] = useState(false);

  useEffect(() => {
    fetchCallsData();
  }, [businessId, searchTerm, statusFilter, dateFilter]);

  const fetchCallsData = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter) params.append('status', statusFilter);
      if (dateFilter) params.append('date', dateFilter);
      
      const [callsRes, statsRes] = await Promise.all([
        axios.get(`/api/calls/list?business_id=${businessId}&${params}`),
        axios.get(`/api/calls/stats?business_id=${businessId}`)
      ]);

      setCalls(callsRes.data.calls || []);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Error fetching calls data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getCallStatusColor = (status) => {
    const colors = {
      'completed': 'bg-green-100 text-green-800',
      'in-progress': 'bg-blue-100 text-blue-800',
      'missed': 'bg-red-100 text-red-800',
      'busy': 'bg-yellow-100 text-yellow-800',
      'no-answer': 'bg-gray-100 text-gray-800',
      'voicemail': 'bg-purple-100 text-purple-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getCallTypeIcon = (direction) => {
    return direction === 'inbound' ? PhoneIncoming : PhoneOutgoing;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color = "blue" }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 font-hebrew">{title}</p>
          <p className={`text-3xl font-bold text-${color}-600 font-hebrew`}>{value}</p>
          {subtitle && <p className="text-sm text-gray-500 font-hebrew">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 bg-${color}-100 rounded-lg flex items-center justify-center`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
    </div>
  );

  const CallRow = ({ call }) => {
    const CallTypeIcon = getCallTypeIcon(call.direction);
    
    return (
      <tr className="hover:bg-gray-50">
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="flex items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              call.direction === 'inbound' ? 'bg-green-100' : 'bg-blue-100'
            }`}>
              <CallTypeIcon className={`w-4 h-4 ${
                call.direction === 'inbound' ? 'text-green-600' : 'text-blue-600'
              }`} />
            </div>
            <div className="mr-3">
              <div className="text-sm font-medium text-gray-900 font-hebrew">{call.from_number}</div>
              <div className="text-sm text-gray-500 font-hebrew">{call.customer_name || 'לא ידוע'}</div>
            </div>
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="text-sm text-gray-900 font-hebrew">{call.to_number}</div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium font-hebrew ${getCallStatusColor(call.status)}`}>
            {call.status === 'completed' && <CheckCircle className="w-3 h-3 ml-1" />}
            {call.status === 'missed' && <AlertCircle className="w-3 h-3 ml-1" />}
            {call.status_hebrew || call.status}
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-hebrew">
          {formatDuration(call.duration)}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-hebrew">
          {new Date(call.created_at).toLocaleString('he-IL')}
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            {call.recording_url && (
              <button 
                onClick={() => setPlayingCall(call.id === playingCall ? null : call.id)}
                className="text-blue-600 hover:text-blue-900"
                title="השמע הקלטה"
              >
                {playingCall === call.id ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
            )}
            {call.transcription && (
              <button 
                onClick={() => {
                  setSelectedCall(call);
                  setShowTranscriptionModal(true);
                }}
                className="text-green-600 hover:text-green-900"
                title="צפה בתמלול"
              >
                <FileText className="w-4 h-4" />
              </button>
            )}
            {call.ai_response && (
              <button 
                onClick={() => {}}
                className="text-purple-600 hover:text-purple-900"
                title="תגובת AI"
              >
                <MessageSquare className="w-4 h-4" />
              </button>
            )}
            <button 
              onClick={() => {}}
              className="text-gray-600 hover:text-gray-900"
              title="פעולות נוספות"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>
        </td>
      </tr>
    );
  };

  const TranscriptionModal = ({ call, isOpen, onClose }) => {
    if (!isOpen || !call) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 font-hebrew">תמלול שיחה</h3>
                <p className="text-sm text-gray-500 font-hebrew">
                  {call.from_number} • {new Date(call.created_at).toLocaleString('he-IL')}
                </p>
              </div>
              <button 
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
          
          <div className="p-6">
            <div className="space-y-4">
              {call.transcription_segments ? (
                call.transcription_segments.map((segment, index) => (
                  <div key={index} className={`p-4 rounded-lg ${
                    segment.speaker === 'customer' ? 'bg-blue-50 border-r-4 border-blue-400' : 'bg-green-50 border-r-4 border-green-400'
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-sm font-medium font-hebrew ${
                        segment.speaker === 'customer' ? 'text-blue-600' : 'text-green-600'
                      }`}>
                        {segment.speaker === 'customer' ? 'לקוח' : 'מערכת AI'}
                      </span>
                      <span className="text-xs text-gray-500 font-hebrew">
                        {formatDuration(segment.timestamp)}
                      </span>
                    </div>
                    <p className="text-gray-800 font-hebrew leading-relaxed">
                      {segment.text}
                    </p>
                    {segment.confidence && (
                      <div className="mt-2 text-xs text-gray-500 font-hebrew">
                        רמת ביטחון: {(segment.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-800 font-hebrew leading-relaxed">
                    {call.transcription}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="p-6 bg-gray-50 border-t border-gray-200">
            <div className="flex justify-between items-center">
              <div className="text-sm text-gray-600 font-hebrew">
                משך השיחה: {formatDuration(call.duration)}
              </div>
              <div className="flex gap-3">
                <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-hebrew">
                  יצא קשר
                </button>
                <button className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 font-hebrew">
                  הורד תמלול
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני שיחות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 font-hebrew">ניהול שיחות</h1>
            <p className="text-gray-600 font-hebrew">מעקב וניתוח שיחות עם תמלול בעברית</p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-hebrew">
              <PhoneCall className="w-4 h-4" />
              בצע שיחה
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard 
            title="סך הכל שיחות" 
            value={stats.total_calls || 0}
            subtitle="כל השיחות"
            icon={Phone} 
            color="blue" 
          />
          <StatCard 
            title="שיחות היום" 
            value={stats.today_calls || 0}
            subtitle="שיחות היום"
            icon={PhoneCall} 
            color="green" 
          />
          <StatCard 
            title="משך ממוצע" 
            value={formatDuration(stats.avg_duration || 0)}
            subtitle="משך שיחה ממוצע"
            icon={Clock} 
            color="yellow" 
          />
          <StatCard 
            title="שיעור מענה" 
            value={`${stats.answer_rate || 0}%`}
            subtitle="השבוע האחרון"
            icon={CheckCircle} 
            color="purple" 
          />
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-1">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="חיפוש לפי מספר טלפון..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-64 font-hebrew"
                />
              </div>
              
              <select 
                value={statusFilter} 
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל הסטטוסים</option>
                <option value="completed">הושלמה</option>
                <option value="missed">לא נענתה</option>
                <option value="busy">תפוס</option>
                <option value="voicemail">תא קולי</option>
              </select>

              <select 
                value={dateFilter} 
                onChange={(e) => setDateFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל התאריכים</option>
                <option value="today">היום</option>
                <option value="yesterday">אתמול</option>
                <option value="week">השבוע</option>
                <option value="month">החודש</option>
              </select>
            </div>
          </div>
        </div>

        {/* Calls Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    מתקשר
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    מספר יעד
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    משך
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    תאריך ושעה
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {calls.map((call) => (
                  <CallRow key={call.id} call={call} />
                ))}
              </tbody>
            </table>
          </div>

          {calls.length === 0 && (
            <div className="text-center py-12">
              <Phone className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 font-hebrew">אין שיחות</h3>
              <p className="text-gray-500 font-hebrew">השיחות שלך יופיעו כאן</p>
            </div>
          )}
        </div>
      </div>

      {/* Transcription Modal */}
      <TranscriptionModal 
        call={selectedCall}
        isOpen={showTranscriptionModal}
        onClose={() => {
          setShowTranscriptionModal(false);
          setSelectedCall(null);
        }}
      />
    </div>
  );
};

export default CallsManagement;