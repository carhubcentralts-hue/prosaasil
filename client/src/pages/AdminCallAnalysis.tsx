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
    <div className="p-6 space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">ניתוח שיחות טלפון</h1>
        <button 
          onClick={fetchCalls} 
          className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-50 transition-colors"
        >
          🔄 רענן נתונים
        </button>
      </div>

      {/* סטטיסטיקות מהירות */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">סה"כ שיחות</p>
              <p className="text-2xl font-bold">{calls.length}</p>
            </div>
            <div className="w-8 h-8 text-blue-600">📞</div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">עם תמלולים</p>
              <p className="text-2xl font-bold">{calls.filter(c => c.transcription).length}</p>
            </div>
            <div className="w-8 h-8 text-green-600">💬</div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">עם תגובות AI</p>
              <p className="text-2xl font-bold">{calls.filter(c => c.ai_response).length}</p>
            </div>
            <div className="w-8 h-8 text-purple-600">🤖</div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">הושלמו בהצלחה</p>
              <p className="text-2xl font-bold">{calls.filter(c => c.call_status === 'completed').length}</p>
            </div>
            <div className="w-8 h-8 text-orange-600">⏰</div>
          </div>
        </div>
      </div>

      {/* רשימת שיחות */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium">שיחות אחרונות</h3>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {calls.length === 0 ? (
              <p className="text-center text-gray-500 py-8">אין שיחות להצגה</p>
            ) : (
              calls.map((call) => (
                <div
                  key={call.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedCall(call)}
                  data-testid={`call-row-${call.id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-reverse space-x-4">
                      <div className="flex-shrink-0">
                        📞
                      </div>
                      <div>
                        <p className="font-medium">{call.from_number}</p>
                        <p className="text-sm text-gray-600">
                          {formatDate(call.created_at)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-reverse space-x-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(call.call_status)}`}>
                        {call.call_status}
                      </span>
                      
                      {call.transcription && (
                        <span className="px-2 py-1 rounded-full text-xs bg-green-50 text-green-800 border border-green-200">
                          תמלול ✓
                        </span>
                      )}
                      
                      {call.ai_response && (
                        <span className="px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-800 border border-blue-200">
                          AI תגובה ✓
                        </span>
                      )}
                      
                      {call.recording_url && (
                        <span className="px-2 py-1 rounded-full text-xs bg-purple-50 text-purple-800 border border-purple-200">
                          הקלטה ✓
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {call.transcription && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-md">
                      <p className="text-sm text-gray-800 line-clamp-2">
                        <strong>תמלול:</strong> {call.transcription}
                      </p>
                    </div>
                  )}
                  
                  {call.ai_response && (
                    <div className="mt-2 p-3 bg-blue-50 rounded-md">
                      <p className="text-sm text-blue-800 line-clamp-2">
                        <strong>תגובת AI:</strong> {call.ai_response}
                      </p>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
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