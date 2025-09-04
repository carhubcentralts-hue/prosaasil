import React, { useState, useEffect } from 'react';
import { 
  Phone, 
  PhoneCall, 
  PhoneIncoming, 
  PhoneOutgoing,
  Play,
  Pause,
  Download,
  Clock,
  User,
  Calendar,
  Search,
  Filter
} from 'lucide-react';

function CallsPage({ business }) {
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [playingCall, setPlayingCall] = useState(null);
  const [filters, setFilters] = useState({
    period: 'today',
    direction: 'all',
    status: 'all'
  });

  useEffect(() => {
    fetchCallsData();
  }, [business?.id, filters]);

  const fetchCallsData = async () => {
    try {
      setLoading(true);
      const [callsRes, statsRes] = await Promise.all([
        fetch(`/api/calls?business_id=${business?.id}&period=${filters.period}&direction=${filters.direction}&status=${filters.status}`),
        fetch(`/api/calls/stats?business_id=${business?.id}&period=${filters.period}`)
      ]);

      if (callsRes.ok) {
        const callsData = await callsRes.json();
        setCalls(callsData.calls || []);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error('Failed to fetch calls data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePlayRecording = (call) => {
    if (playingCall === call.id) {
      setPlayingCall(null);
    } else {
      setPlayingCall(call.id);
      // כאן נגן את ההקלטה
    }
  };

  const downloadRecording = async (call) => {
    try {
      const response = await fetch(`/api/calls/${call.id}/recording`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `call_${call.id}_${new Date(call.created_at).toLocaleDateString('he-IL')}.mp3`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to download recording:', error);
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getCallIcon = (direction, status) => {
    if (direction === 'inbound') {
      return <PhoneIncoming className="w-4 h-4 text-green-600" />;
    } else if (direction === 'outbound') {
      return <PhoneOutgoing className="w-4 h-4 text-blue-600" />;
    }
    return <Phone className="w-4 h-4 text-gray-600" />;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'missed':
        return 'bg-red-100 text-red-800';
      case 'busy':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
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

  const callStats = [
    {
      title: 'שיחות היום',
      value: stats.calls_today || 0,
      icon: Phone,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      title: 'שיחות שהתקבלו',
      value: stats.inbound_calls || 0,
      icon: PhoneIncoming,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'שיחות יוצאות',
      value: stats.outbound_calls || 0,
      icon: PhoneOutgoing,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50'
    },
    {
      title: 'זמן שיחה ממוצע',
      value: `${Math.floor((stats.avg_duration || 0) / 60)} דק'`,
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          מוקד שיחות
        </h1>
        <p className="text-gray-600 mt-1">
          ניהול וניטור שיחות נכנסות ויוצאות
        </p>
      </div>

      {/* Call Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {callStats.map((stat, index) => {
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

      {/* Filters */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                תקופה
              </label>
              <select
                value={filters.period}
                onChange={(e) => setFilters({ ...filters, period: e.target.value })}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="today">היום</option>
                <option value="week">השבוע</option>
                <option value="month">החודש</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                כיוון שיחה
              </label>
              <select
                value={filters.direction}
                onChange={(e) => setFilters({ ...filters, direction: e.target.value })}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="all">הכל</option>
                <option value="inbound">נכנסות</option>
                <option value="outbound">יוצאות</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                סטטוס
              </label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="all">הכל</option>
                <option value="completed">הושלמה</option>
                <option value="missed">לא נענתה</option>
                <option value="busy">תפוס</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Calls List */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            רשימת שיחות
          </h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  שיחה
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  לקוח
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  תאריך ושעה
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  משך
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  סטטוס
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  הקלטה
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {calls.map((call) => (
                <tr key={call.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      {getCallIcon(call.direction, call.status)}
                      <span className="mr-2 text-sm font-medium text-gray-900">
                        {call.phone_number}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <User className="w-4 h-4 text-gray-400 ml-2" />
                      <span className="text-sm text-gray-900">
                        {call.customer_name || 'לא ידוע'}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="flex items-center">
                      <Calendar className="w-4 h-4 text-gray-400 ml-2" />
                      {new Date(call.created_at).toLocaleString('he-IL')}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="flex items-center">
                      <Clock className="w-4 h-4 text-gray-400 ml-2" />
                      {formatDuration(call.duration || 0)}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(call.status)}`}>
                      {call.status === 'completed' && 'הושלמה'}
                      {call.status === 'missed' && 'לא נענתה'}
                      {call.status === 'busy' && 'תפוס'}
                      {call.status === 'failed' && 'נכשלה'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {call.recording_url && (
                      <div className="flex space-x-2 space-x-reverse">
                        <button
                          onClick={() => handlePlayRecording(call)}
                          className="text-blue-600 hover:text-blue-900"
                          title={playingCall === call.id ? 'עצור' : 'נגן'}
                        >
                          {playingCall === call.id ? (
                            <Pause className="w-4 h-4" />
                          ) : (
                            <Play className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => downloadRecording(call)}
                          className="text-green-600 hover:text-green-900"
                          title="הורד הקלטה"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {calls.length === 0 && !loading && (
          <div className="text-center py-12">
            <Phone className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              אין שיחות
            </h3>
            <p className="text-gray-500">
              לא נמצאו שיחות בתקופה הנבחרת
            </p>
          </div>
        )}
      </div>

      {/* AI Summary */}
      {calls.length > 0 && (
        <div className="mt-6 bg-blue-50 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            סיכום AI של השיחות
          </h3>
          <p className="text-blue-800">
            ב{filters.period === 'today' ? 'יום' : filters.period === 'week' ? 'שבוע' : 'חודש'} האחרון 
            התקבלו {stats.inbound_calls || 0} שיחות נכנסות ובוצעו {stats.outbound_calls || 0} שיחות יוצאות.
            זמן השיחה הממוצע הוא {Math.floor((stats.avg_duration || 0) / 60)} דקות.
            {stats.satisfaction_rate && ` שביעות הרצון של הלקוחות עומדת על ${stats.satisfaction_rate}%.`}
          </p>
        </div>
      )}
    </div>
  );
}

export default CallsPage;