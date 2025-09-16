import React, { useState, useEffect } from 'react';
import { Phone, PlayCircle, Clock, User, MessageSquare, ExternalLink } from 'lucide-react';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: any) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: any) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Mock data interface
interface Call {
  sid: string;
  lead_id?: number;
  lead_name?: string;
  from_e164: string;
  to_e164: string;
  duration: number;
  status: string;
  direction: 'inbound' | 'outbound';
  at: string;
  hasRecording?: boolean;
  hasTranscript?: boolean;
}

export function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [directionFilter, setDirectionFilter] = useState('all');

  useEffect(() => {
    loadCalls();
  }, [searchQuery, statusFilter, directionFilter]);

  const loadCalls = async () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      const mockCalls: Call[] = [
        {
          sid: 'CA123456789',
          lead_id: 1,
          lead_name: 'יוסי כהן',
          from_e164: '+972501234567',
          to_e164: '+972587654321',
          duration: 120,
          status: 'completed',
          direction: 'inbound',
          at: '2025-09-16T10:30:00Z',
          hasRecording: true,
          hasTranscript: true
        },
        {
          sid: 'CA987654321',
          lead_id: 2,
          lead_name: 'רחל לוי',
          from_e164: '+972507654321',
          to_e164: '+972587654321',
          duration: 45,
          status: 'completed',
          direction: 'outbound',
          at: '2025-09-16T09:15:00Z',
          hasRecording: true,
          hasTranscript: false
        },
        {
          sid: 'CA555444333',
          from_e164: '+972509876543',
          to_e164: '+972587654321',
          duration: 0,
          status: 'no-answer',
          direction: 'inbound',
          at: '2025-09-16T08:45:00Z',
          hasRecording: false,
          hasTranscript: false
        }
      ];
      
      setCalls(mockCalls);
      setLoading(false);
    }, 500);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'no-answer': return 'warning';
      case 'busy': return 'warning';
      case 'failed': return 'destructive';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed': return 'הושלם';
      case 'no-answer': return 'לא נענה';
      case 'busy': return 'תפוס';
      case 'failed': return 'נכשל';
      default: return status;
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds === 0) return '0:00';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const handleCallClick = (call: Call) => {
    setSelectedCall(call);
    setShowDetails(true);
  };

  const filteredCalls = calls.filter(call => {
    const matchesSearch = searchQuery === '' || 
      call.lead_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      call.from_e164.includes(searchQuery) ||
      call.to_e164.includes(searchQuery);
    
    const matchesStatus = statusFilter === 'all' || call.status === statusFilter;
    const matchesDirection = directionFilter === 'all' || call.direction === directionFilter;
    
    return matchesSearch && matchesStatus && matchesDirection;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען שיחות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Phone className="w-6 h-6 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">שיחות</h1>
            <Badge>{calls.length} שיחות</Badge>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <ExternalLink className="w-4 h-4 mr-2" />
              ייצא נתונים
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="חיפוש לפי שם, טלפון..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="completed">הושלם</option>
              <option value="no-answer">לא נענה</option>
              <option value="busy">תפוס</option>
              <option value="failed">נכשל</option>
            </select>
            
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל הכיוונים</option>
              <option value="inbound">נכנס</option>
              <option value="outbound">יוצא</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Calls List */}
        <div className={`${
          showDetails ? 'hidden lg:flex' : 'flex'
        } w-full lg:w-1/2 xl:w-2/3 flex-col bg-white`}>
          
          <div className="flex-1 overflow-y-auto">
            {filteredCalls.length === 0 ? (
              <div className="text-center py-12">
                <Phone className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">אין שיחות</h3>
                <p className="text-gray-500">אין שיחות שמתאימות לחיפוש</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {filteredCalls.map((call) => (
                  <div
                    key={call.sid}
                    className={`p-4 cursor-pointer hover:bg-gray-50 ${
                      selectedCall?.sid === call.sid ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => handleCallClick(call)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-full ${
                          call.direction === 'inbound' ? 'bg-green-100' : 'bg-blue-100'
                        }`}>
                          <Phone className={`w-4 h-4 ${
                            call.direction === 'inbound' ? 'text-green-600' : 'text-blue-600'
                          }`} />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            {call.lead_name || 'לא ידוע'}
                          </h3>
                          <p className="text-sm text-gray-600" dir="ltr">
                            {call.direction === 'inbound' ? call.from_e164 : call.to_e164}
                          </p>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <Badge variant={getStatusColor(call.status)}>
                          {getStatusLabel(call.status)}
                        </Badge>
                        <p className="text-xs text-gray-500 mt-1">
                          {new Date(call.at).toLocaleString('he-IL')}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between text-sm text-gray-500">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          {formatDuration(call.duration)}
                        </div>
                        {call.hasRecording && (
                          <div className="flex items-center gap-1 text-blue-600">
                            <PlayCircle className="w-4 h-4" />
                            הקלטה
                          </div>
                        )}
                        {call.hasTranscript && (
                          <div className="flex items-center gap-1 text-green-600">
                            <MessageSquare className="w-4 h-4" />
                            תמליל
                          </div>
                        )}
                      </div>
                      <span className="text-xs">
                        {call.direction === 'inbound' ? 'נכנס' : 'יוצא'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Call Details Panel */}
        {showDetails && selectedCall && (
          <div className={`${
            showDetails ? 'flex' : 'hidden lg:flex'
          } w-full lg:w-1/2 xl:w-1/3 flex-col bg-white border-l border-gray-200`}>
            
            {/* Details Header */}
            <div className="border-b border-gray-200 px-6 py-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">פרטי שיחה</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  className="lg:hidden"
                  onClick={() => setShowDetails(false)}
                >
                  ←
                </Button>
              </div>
            </div>

            {/* Details Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Call Info */}
              <div>
                <h3 className="font-medium text-gray-900 mb-3">מידע כללי</h3>
                <div className="space-y-3">
                  <div>
                    <label className="text-sm font-medium text-gray-700">שם</label>
                    <p className="text-sm text-gray-900">{selectedCall.lead_name || 'לא ידוע'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">מספר טלפון</label>
                    <p className="text-sm text-gray-900" dir="ltr">
                      {selectedCall.direction === 'inbound' ? selectedCall.from_e164 : selectedCall.to_e164}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">משך השיחה</label>
                    <p className="text-sm text-gray-900">{formatDuration(selectedCall.duration)}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">סטטוס</label>
                    <Badge variant={getStatusColor(selectedCall.status)}>
                      {getStatusLabel(selectedCall.status)}
                    </Badge>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">זמן</label>
                    <p className="text-sm text-gray-900">
                      {new Date(selectedCall.at).toLocaleString('he-IL')}
                    </p>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div>
                <h3 className="font-medium text-gray-900 mb-3">פעולות</h3>
                <div className="space-y-2">
                  {selectedCall.hasRecording && (
                    <Button variant="outline" className="w-full justify-center">
                      <PlayCircle className="w-4 h-4 mr-2" />
                      השמע הקלטה
                    </Button>
                  )}
                  
                  {selectedCall.hasTranscript && (
                    <Button variant="outline" className="w-full justify-center">
                      <MessageSquare className="w-4 h-4 mr-2" />
                      הצג תמליל
                    </Button>
                  )}
                  
                  <Button variant="outline" className="w-full justify-center">
                    <Phone className="w-4 h-4 mr-2" />
                    התקשר שוב
                  </Button>
                  
                  {selectedCall.lead_id && (
                    <Button variant="outline" className="w-full justify-center">
                      <User className="w-4 h-4 mr-2" />
                      פתח ליד
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}