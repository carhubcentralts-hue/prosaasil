import React, { useState, useEffect } from 'react';

interface CallData {
  id: number;
  call_sid: string;
  from_number: string;
  to_number: string;
  call_status: string;
  call_duration: number;
  transcription: string;
  ai_response: string;
  recording_url: string;
  created_at: string;
  business_id: number;
}

export default function AdminCallAnalysis() {
  const [calls, setCalls] = useState<CallData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<CallData | null>(null);

  useEffect(() => {
    fetchCalls();
  }, []);

  const fetchCalls = async () => {
    try {
      const response = await fetch('/api/admin/calls');
      if (response.ok) {
        const data = await response.json();
        setCalls(data);
      }
    } catch (error) {
      console.error('Error fetching calls:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'in-progress': return 'bg-blue-100 text-blue-800';
      case 'failed': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">ניתוח שיחות טלפון</h1>
        </div>
        <div className="text-center py-8">
          <div className="animate-spin w-8 h-8 border-b-2 border-blue-600 rounded-full mx-auto"></div>
          <p className="mt-4 text-gray-600">טוען נתוני שיחות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
      {/* Header Section */}
      <div className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">🎧 ניתוח תמלולי שיחות</h1>
              <p className="text-gray-600 text-lg">ניהול וניתוח מתקדם של שיחות טלפון ותמלולים</p>
            </div>
            <button 
              onClick={fetchCalls} 
              className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-6 py-3 rounded-xl font-medium transition-all duration-200 shadow-lg hover:shadow-xl flex items-center gap-2"
            >
              <span className="text-lg">🔄</span>
              רענן נתונים
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* Analytics Dashboard */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-2xl shadow-lg p-6 border border-blue-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-700 font-medium mb-1">סה"כ שיחות</p>
                <p className="text-3xl font-bold text-blue-900">{calls.length}</p>
                <p className="text-sm text-blue-600 mt-1">כל הזמנים</p>
              </div>
              <div className="w-12 h-12 bg-blue-500 rounded-xl flex items-center justify-center text-white text-2xl">
                📞
              </div>
            </div>
          </div>
          
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-2xl shadow-lg p-6 border border-green-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-700 font-medium mb-1">עם תמלולים</p>
                <p className="text-3xl font-bold text-green-900">{calls.filter(c => c.transcription).length}</p>
                <p className="text-sm text-green-600 mt-1">תמלול מוצלח</p>
              </div>
              <div className="w-12 h-12 bg-green-500 rounded-xl flex items-center justify-center text-white text-2xl">
                💬
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-2xl shadow-lg p-6 border border-purple-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-700 font-medium mb-1">תגובות AI</p>
                <p className="text-3xl font-bold text-purple-900">{calls.filter(c => c.ai_response).length}</p>
                <p className="text-sm text-purple-600 mt-1">AI פעיל</p>
              </div>
              <div className="w-12 h-12 bg-purple-500 rounded-xl flex items-center justify-center text-white text-2xl">
                🤖
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-2xl shadow-lg p-6 border border-orange-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-orange-700 font-medium mb-1">הקלטות</p>
                <p className="text-3xl font-bold text-orange-900">{calls.filter(c => c.recording_url).length}</p>
                <p className="text-sm text-orange-600 mt-1">קבצי אודיו</p>
              </div>
              <div className="w-12 h-12 bg-orange-500 rounded-xl flex items-center justify-center text-white text-2xl">
                🎵
              </div>
            </div>
          </div>
        </div>

        {/* רשימת שיחות */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200">
          <div className="px-8 py-6 border-b border-gray-200">
            <h3 className="text-2xl font-bold text-gray-900">📋 שיחות אחרונות</h3>
            <p className="text-gray-600 mt-1">רשימת כל השיחות עם תמלולים ותגובות AI</p>
          </div>
          <div className="p-8">
            <div className="space-y-6">
              {calls.length === 0 ? (
                <div className="text-center py-16">
                  <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-3xl">📞</span>
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">אין שיחות להצגה</h3>
                  <p className="text-gray-600">לא נמצאו שיחות במערכת כרגע</p>
                </div>
              ) : (
                calls.map((call) => (
                  <div
                    key={call.id}
                    className="bg-gradient-to-r from-white to-gray-50 border border-gray-200 rounded-2xl p-6 hover:shadow-xl cursor-pointer transition-all duration-300 hover:border-blue-300"
                    onClick={() => setSelectedCall(call)}
                    data-testid={`call-row-${call.id}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-reverse space-x-6">
                        <div className="flex-shrink-0">
                          <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                            <span className="text-xl">📞</span>
                          </div>
                        </div>
                        <div>
                          <p className="text-lg font-bold text-gray-900">{call.from_number}</p>
                          <p className="text-sm text-gray-600 font-medium">
                            {formatDate(call.created_at)}
                          </p>
                          {call.call_duration && (
                            <p className="text-xs text-blue-600">משך: {call.call_duration} שניות</p>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-reverse space-x-3">
                        <span className={`px-4 py-2 rounded-xl text-sm font-medium shadow-sm ${getStatusColor(call.call_status)}`}>
                          {call.call_status}
                        </span>
                        
                        {call.transcription && (
                          <span className="px-3 py-2 rounded-xl text-xs bg-green-100 text-green-800 border border-green-200 font-medium">
                            💬 תמלול
                          </span>
                        )}
                        
                        {call.ai_response && (
                          <span className="px-3 py-2 rounded-xl text-xs bg-purple-100 text-purple-800 border border-purple-200 font-medium">
                            🤖 AI
                          </span>
                        )}
                        
                        {call.recording_url && (
                          <span className="px-3 py-2 rounded-xl text-xs bg-orange-100 text-orange-800 border border-orange-200 font-medium">
                            🎵 הקלטה
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {call.transcription && (
                      <div className="mt-6 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                        <h4 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                          💬 תמלול השיחה
                        </h4>
                        <p className="text-sm text-gray-800 leading-relaxed">
                          {call.transcription}
                        </p>
                      </div>
                    )}
                    
                    {call.ai_response && (
                      <div className="mt-4 p-4 bg-gradient-to-r from-purple-50 to-purple-100 rounded-xl border border-purple-200">
                        <h4 className="text-sm font-bold text-purple-700 mb-2 flex items-center gap-2">
                          🤖 תגובת המערכת
                        </h4>
                        <p className="text-sm text-purple-800 leading-relaxed">
                          {call.ai_response}
                        </p>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        {/* פרטי שיחה נבחרת */}
      {selectedCall && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-lg font-medium">פרטי שיחה - {selectedCall.from_number}</h3>
            <button 
              onClick={() => setSelectedCall(null)}
              className="text-gray-400 hover:text-gray-600 text-xl"
            >
              ✕
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">מספר מתקשר</p>
                <p className="font-medium">{selectedCall.from_number}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">תאריך ושעה</p>
                <p className="font-medium">{formatDate(selectedCall.created_at)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">משך שיחה</p>
                <p className="font-medium">{selectedCall.call_duration || 'לא זמין'} שניות</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">סטטוס</p>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(selectedCall.call_status)}`}>
                  {selectedCall.call_status}
                </span>
              </div>
            </div>
            
            {selectedCall.transcription && (
              <div>
                <p className="text-sm text-gray-600 mb-2">תמלול השיחה</p>
                <div className="p-4 bg-gray-50 rounded-md">
                  <p className="text-gray-800">{selectedCall.transcription}</p>
                </div>
              </div>
            )}
            
            {selectedCall.ai_response && (
              <div>
                <p className="text-sm text-gray-600 mb-2">תגובת המערכת</p>
                <div className="p-4 bg-blue-50 rounded-md">
                  <p className="text-blue-800">{selectedCall.ai_response}</p>
                </div>
              </div>
            )}
            
            {selectedCall.recording_url && (
              <div>
                <p className="text-sm text-gray-600 mb-2">הקלטה</p>
                <div className="flex space-x-reverse space-x-2">
                  <button className="bg-white border border-gray-300 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-50">
                    ▶️ השמע
                  </button>
                  <button className="bg-white border border-gray-300 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-50">
                    ⬇️ הורד
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}