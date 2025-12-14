import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, PlayCircle, Clock, User, MessageSquare, ExternalLink, Download, Trash2, Calendar, FileText, Volume2, AlertTriangle, Edit, Save, X } from 'lucide-react';
import { http } from '../../services/http';
import { formatDate as formatDateUtil, formatDuration } from '../../shared/utils/format';

// Debounce hook for search optimization
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// Temporary UI components - optimized with React.memo
const Card = React.memo(({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
));

const Button = React.memo(({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
});

const Badge = React.memo(({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive";
}) => {
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
});

// Interface definitions
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
  recording_url?: string;
  transcription?: string;
  hasRecording?: boolean;
  hasTranscript?: boolean;
  expiresAt?: string; // Auto-delete date
}

interface CallDetails {
  call: Call;
  transcript: string;
  summary?: string;
  sentiment?: string;
}

export function CallsPage() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [directionFilter, setDirectionFilter] = useState('all');
  const [callDetails, setCallDetails] = useState<CallDetails | null>(null);
  const [downloadingRecording, setDownloadingRecording] = useState<string | null>(null);
  const [playingRecording, setPlayingRecording] = useState<string | null>(null);
  const [editingTranscript, setEditingTranscript] = useState(false);
  const [editedTranscript, setEditedTranscript] = useState('');
  const [deletingCall, setDeletingCall] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [deletingOldRecordings, setDeletingOldRecordings] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCalls, setTotalCalls] = useState(0);
  const PAGE_SIZE = 25;

  // Debounce search query to prevent excessive API calls
  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  
  // Track initial load vs subsequent searches
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchQuery, statusFilter, directionFilter]);

  // Open lead in CRM - navigate to lead detail page
  const openInCRM = async (call: Call) => {
    // If call already has a lead_id, navigate directly
    if (call.lead_id) {
      navigate(`/app/leads/${call.lead_id}`);
      return;
    }
    
    // Otherwise, try to find lead by phone number
    // Extract last 8 digits for flexible matching (handles +972, 0, etc)
    const phoneNumber = call.from_e164 || '';
    const phoneDigits = phoneNumber.replace(/\D/g, '');
    const searchTerm = phoneDigits.length >= 8 ? phoneDigits.slice(-8) : phoneDigits;
    
    if (searchTerm) {
      try {
        // Search for lead with this phone number (last 8 digits match)
        const response = await http.get(`/api/leads?search=${encodeURIComponent(searchTerm)}`);
        if (response && (response as any).leads && (response as any).leads.length > 0) {
          const lead = (response as any).leads[0];
          navigate(`/app/leads/${lead.id}`);
          return;
        }
      } catch (error) {
        console.error('Error searching for lead:', error);
      }
      // No lead found - navigate to leads page with search
      navigate(`/app/leads?search=${encodeURIComponent(searchTerm)}`);
    } else {
      // No phone number - just go to leads page
      navigate('/app/leads');
    }
  };

  useEffect(() => {
    loadCalls();
  }, [debouncedSearchQuery, statusFilter, directionFilter, currentPage]);

  const loadCalls = useCallback(async () => {
    try {
      // Only show full loading spinner for initial load
      if (!initialLoadComplete) {
        setLoading(true);
      }
      
      const offset = (currentPage - 1) * PAGE_SIZE;
      const response = await http.get('/api/calls?search=' + encodeURIComponent(debouncedSearchQuery) + '&status=' + statusFilter + '&direction=' + directionFilter + '&limit=' + PAGE_SIZE + '&offset=' + offset);
      
      if (response && typeof response === 'object' && 'success' in response && response.success) {
        setCalls((response as any).calls || []);
        setTotalCalls((response as any).total || (response as any).calls?.length || 0);
      } else {
        console.error('Error loading calls:', response);
        setCalls([]);
        setTotalCalls(0);
      }
    } catch (error) {
      console.error('Error loading calls:', error);
      setCalls([]);
      setTotalCalls(0);
    } finally {
      setLoading(false);
      if (!initialLoadComplete) {
        setInitialLoadComplete(true);
      }
    }
  }, [debouncedSearchQuery, statusFilter, directionFilter, currentPage, initialLoadComplete]);

  const loadCallDetails = async (call: Call) => {
    try {
      setSelectedCall(call);
      setShowDetails(true);
      
      const response = await http.get(`/api/calls/${call.sid}/details`);
      
      if (response && typeof response === 'object' && 'success' in response && (response as any).success) {
        // Use response.data or response.details if available, otherwise fall back to basic structure
        const responseData = (response as any).data || (response as any).details || response;
        setCallDetails({
          call,
          transcript: responseData.transcript || call.transcription || 'אין תמליל זמין',
          summary: responseData.summary,
          sentiment: responseData.sentiment
        });
      } else {
        // Fallback to basic details without hardcoded content
        const fallbackDetails: CallDetails = {
          call,
          transcript: call.transcription || 'אין תמליל זמין'
        };
        setCallDetails(fallbackDetails);
      }
    } catch (error) {
      console.error('Error loading call details:', error);
      // Fallback to basic details on error without hardcoded content
      const fallbackDetails: CallDetails = {
        call,
        transcript: call.transcription || 'אין תמליל זמין'
      };
      setCallDetails(fallbackDetails);
    }
  };

  const downloadRecording = async (call: Call) => {
    if (!call.recording_url) return;
    
    try {
      setDownloadingRecording(call.sid);
      
      // Use secure download endpoint
      const response = await fetch(`/api/calls/${call.sid}/download`, {
        method: 'GET',
        credentials: 'include' // Include session cookies
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'שגיאה בהורדת ההקלטה');
      }
      
      // Get the file blob
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `recording-${call.sid}.mp3`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      console.log('Recording downloaded:', call.sid);
    } catch (error) {
      console.error('Error downloading recording:', error);
      alert('שגיאה בהורדת ההקלטה: ' + (error as Error).message);
    } finally {
      setDownloadingRecording(null);
    }
  };

  const playRecording = async (call: Call) => {
    if (!call.recording_url) return;
    
    try {
      setPlayingRecording(call.sid);
      
      // TODO: Replace with real audio player implementation
      // For now, just simulate playing
      await new Promise(resolve => setTimeout(resolve, 2000));
      console.log('Playing recording:', call.sid);
    } catch (error) {
      console.error('Error playing recording:', error);
    } finally {
      setPlayingRecording(null);
    }
  };

  // 🎯 REMOVED: Use centralized formatDuration from utils
  // const formatDuration = (seconds: number) => { ... }

  // 🎯 REMOVED: Use centralized formatDate from utils with timezone fix
  // const formatDate = (dateString: string) => { ... }

  const getDaysUntilExpiry = (expiresAt?: string) => {
    if (!expiresAt) return null;
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diffTime = expiry.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const handleEditTranscript = () => {
    if (!callDetails) return;
    setEditedTranscript(callDetails.transcript);
    setEditingTranscript(true);
  };

  const handleSaveTranscript = async () => {
    if (!selectedCall) return;
    
    try {
      await http.put(`/api/calls/${selectedCall.sid}/transcript`, {
        transcript: editedTranscript
      });
      
      // Update local state
      if (callDetails) {
        setCallDetails({
          ...callDetails,
          transcript: editedTranscript
        });
      }
      
      // Update in calls list
      setCalls(calls.map(c => 
        c.sid === selectedCall.sid 
          ? { ...c, transcription: editedTranscript, hasTranscript: true }
          : c
      ));
      
      setEditingTranscript(false);
      alert('התמליל עודכן בהצלחה');
    } catch (error) {
      console.error('Error updating transcript:', error);
      alert('שגיאה בעדכון התמליל');
    }
  };

  const handleCancelEdit = () => {
    setEditingTranscript(false);
    setEditedTranscript('');
  };

  // Delete a single call
  const deleteCall = async (call: Call) => {
    try {
      setDeletingCall(call.sid);
      
      const response = await http.delete(`/api/calls/${call.sid}`);
      
      if (response && typeof response === 'object' && 'success' in response && (response as any).success) {
        // Remove from local state
        setCalls(calls.filter(c => c.sid !== call.sid));
        setShowDeleteConfirm(null);
      } else {
        alert('שגיאה במחיקת השיחה');
      }
    } catch (error) {
      console.error('Error deleting call:', error);
      alert('שגיאה במחיקת השיחה');
    } finally {
      setDeletingCall(null);
    }
  };

  // Delete old recordings (older than 7 days)
  const deleteOldRecordings = async () => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את כל ההקלטות הישנות מעל 7 ימים?')) {
      return;
    }
    
    try {
      setDeletingOldRecordings(true);
      
      const response = await http.post('/api/calls/cleanup-recordings', {});
      
      if (response && typeof response === 'object' && 'success' in response && (response as any).success) {
        const deleted = (response as any).deleted_count || 0;
        alert(`נמחקו ${deleted} הקלטות ישנות בהצלחה`);
        loadCalls(); // Refresh the list
      } else {
        alert('שגיאה במחיקת הקלטות ישנות');
      }
    } catch (error) {
      console.error('Error deleting old recordings:', error);
      alert('שגיאה במחיקת הקלטות ישנות');
    } finally {
      setDeletingOldRecordings(false);
    }
  };

  // Memoize filtered calls to avoid recalculating on every render
  const filteredCalls = useMemo(() => {
    return calls.filter(call => {
      const matchesSearch = !searchQuery || 
        call.lead_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        call.from_e164.includes(searchQuery) ||
        call.transcription?.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesStatus = statusFilter === 'all' || call.status === statusFilter;
      const matchesDirection = directionFilter === 'all' || call.direction === directionFilter;
      
      return matchesSearch && matchesStatus && matchesDirection;
    });
  }, [calls, searchQuery, statusFilter, directionFilter]);

  // Only show skeleton loader for initial load
  if (loading && !initialLoadComplete) {
    return (
      <div className="space-y-6" dir="rtl">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">שיחות טלפון</h1>
            <p className="text-slate-600 mt-1">צפה בכל השיחות, הקלטות ותמלילים</p>
          </div>
        </div>
        <Card className="p-4">
          <div className="space-y-4 animate-pulse">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-3 border-b border-slate-100 last:border-0">
                <div className="w-10 h-10 bg-slate-200 rounded-full"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-1/3"></div>
                  <div className="h-3 bg-slate-100 rounded w-1/4"></div>
                </div>
                <div className="h-6 bg-slate-200 rounded-full w-16"></div>
                <div className="h-4 bg-slate-100 rounded w-20"></div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">שיחות טלפון</h1>
          <p className="text-slate-600 mt-1">צפה בכל השיחות, הקלטות ותמלילים</p>
        </div>
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={deleteOldRecordings} 
            disabled={deletingOldRecordings}
            data-testid="button-delete-old"
          >
            {deletingOldRecordings ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current ml-2" />
            ) : (
              <Trash2 className="h-4 w-4 ml-2" />
            )}
            {deletingOldRecordings ? 'מוחק...' : 'מחק הקלטות ישנות'}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">חיפוש</label>
            <input
              type="search"
              inputMode="search"
              autoComplete="off"
              placeholder="חפש לפי שם, טלפון או תוכן..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                }
              }}
              className="w-full px-3 py-2 border border-slate-300 rounded-md"
              data-testid="input-search"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">סטטוס</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md"
              data-testid="select-status"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="completed">הושלמה</option>
              <option value="busy">תפוס</option>
              <option value="no-answer">לא נענה</option>
              <option value="canceled">בוטלה</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">כיוון</label>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md"
              data-testid="select-direction"
            >
              <option value="all">כל הכיוונים</option>
              <option value="inbound">נכנסת</option>
              <option value="outbound">יוצאת</option>
            </select>
          </div>
          
          <div className="flex items-end">
            <Button onClick={loadCalls} className="w-full">
              <Phone className="h-4 w-4 ml-2" />
              רענן
            </Button>
          </div>
        </div>
      </Card>

      {/* Auto-delete warning */}
      <Card className="p-4 bg-yellow-50 border-yellow-200">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <div>
            <p className="text-sm font-medium text-yellow-800">מחיקה אוטומטית של הקלטות</p>
            <p className="text-sm text-yellow-700">הקלטות נמחקות אוטומטית אחרי 7 ימים לחיסכון במקום. הורד הקלטות חשובות לפני המחיקה.</p>
          </div>
        </div>
      </Card>

      {/* Calls List */}
      <Card className="p-0">
        {/* Desktop Table View */}
        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">שיחה</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">מש/ךילוח</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">סטטוס</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">הקלטה</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">תמליל</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">פעולות</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {filteredCalls.map((call) => {
                const daysLeft = getDaysUntilExpiry(call.expiresAt);
                return (
                  <tr key={call.sid} className="hover:bg-slate-50" data-testid={`call-row-${call.sid}`}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-full ${call.direction === 'inbound' ? 'bg-green-100' : 'bg-blue-100'}`}>
                          <Phone className={`h-4 w-4 ${call.direction === 'inbound' ? 'text-green-600' : 'text-blue-600'}`} />
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">{call.lead_name || 'לקוח אלמוני'}</p>
                          <p className="text-sm text-slate-500">{call.from_e164}</p>
                          <p className="text-xs text-slate-400">{formatDateUtil(call.at)}</p>
                        </div>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-slate-400" />
                        <span className="text-sm text-slate-600">{formatDuration(call.duration)}</span>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <Badge variant={
                        call.status === 'completed' ? 'success' :
                        call.status === 'no-answer' ? 'warning' : 'default'
                      }>
                        {call.status === 'completed' ? 'הושלמה' :
                         call.status === 'no-answer' ? 'לא נענה' :
                         call.status === 'busy' ? 'תפוס' : call.status}
                      </Badge>
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        {call.hasRecording ? (
                          <div className="flex items-center gap-2">
                            <Volume2 className="h-4 w-4 text-green-600" />
                            {daysLeft !== null && daysLeft <= 2 && (
                              <Badge variant="warning" className="text-xs">
                                {daysLeft} ימים
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">אין הקלטה</span>
                        )}
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      {call.hasTranscript ? (
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-blue-600" />
                          <span className="text-xs text-slate-600 truncate max-w-32">
                            {call.transcription?.substring(0, 30)}...
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">אין תמליל</span>
                      )}
                    </td>
                    
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadCallDetails(call)}
                          data-testid={`button-details-${call.sid}`}
                        >
                          <MessageSquare className="h-4 w-4" />
                        </Button>
                        
                        {call.hasRecording && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => playRecording(call)}
                              disabled={playingRecording === call.sid}
                              data-testid={`button-play-${call.sid}`}
                            >
                              <PlayCircle className={`h-4 w-4 ${playingRecording === call.sid ? 'animate-spin' : ''}`} />
                            </Button>
                            
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => downloadRecording(call)}
                              disabled={downloadingRecording === call.sid}
                              data-testid={`button-download-${call.sid}`}
                            >
                              <Download className={`h-4 w-4 ${downloadingRecording === call.sid ? 'animate-bounce' : ''}`} />
                            </Button>
                          </>
                        )}
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowDeleteConfirm(call.sid)}
                          disabled={deletingCall === call.sid}
                          data-testid={`button-delete-desktop-${call.sid}`}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className={`h-4 w-4 ${deletingCall === call.sid ? 'animate-pulse' : ''}`} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View */}
        <div className="lg:hidden">
          <div className="space-y-4 p-4">
            {filteredCalls.map((call) => {
              const daysLeft = getDaysUntilExpiry(call.expiresAt);
              return (
                <Card key={call.sid} className="p-4 border border-slate-200" data-testid={`call-card-${call.sid}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`p-3 rounded-full ${call.direction === 'inbound' ? 'bg-green-100' : 'bg-blue-100'}`}>
                        <Phone className={`h-5 w-5 ${call.direction === 'inbound' ? 'text-green-600' : 'text-blue-600'}`} />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{call.lead_name || 'לקוח אלמוני'}</p>
                        <p className="text-sm text-slate-500">{call.from_e164}</p>
                        <p className="text-xs text-slate-400">{formatDateUtil(call.at)}</p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Badge variant={
                        call.status === 'completed' ? 'success' :
                        call.status === 'no-answer' ? 'warning' : 'default'
                      }>
                        {call.status === 'completed' ? 'הושלמה' :
                         call.status === 'no-answer' ? 'לא נענה' :
                         call.status === 'busy' ? 'תפוס' : call.status}
                      </Badge>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-slate-400" />
                      <span className="text-sm text-slate-600">{formatDuration(call.duration)}</span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {call.hasRecording ? (
                        <div className="flex items-center gap-2">
                          <Volume2 className="h-4 w-4 text-green-600" />
                          <span className="text-xs text-slate-600">יש הקלטה</span>
                          {daysLeft !== null && daysLeft <= 2 && (
                            <Badge variant="warning" className="text-xs">
                              {daysLeft} ימים
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">אין הקלטה</span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2 col-span-2">
                      {call.hasTranscript ? (
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-blue-600" />
                          <span className="text-xs text-slate-600 truncate">
                            {call.transcription?.substring(0, 50)}...
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">אין תמליל</span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 pt-3 border-t border-slate-100">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => loadCallDetails(call)}
                      data-testid={`button-details-${call.sid}`}
                      className="flex-1"
                    >
                      <MessageSquare className="h-4 w-4 mr-1" />
                      פרטים
                    </Button>
                    
                    {call.hasRecording && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => playRecording(call)}
                          disabled={playingRecording === call.sid}
                          data-testid={`button-play-${call.sid}`}
                          className="flex-1"
                        >
                          <PlayCircle className={`h-4 w-4 mr-1 ${playingRecording === call.sid ? 'animate-spin' : ''}`} />
                          השמע
                        </Button>
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => downloadRecording(call)}
                          disabled={downloadingRecording === call.sid}
                          data-testid={`button-download-${call.sid}`}
                          className="flex-1"
                        >
                          <Download className={`h-4 w-4 mr-1 ${downloadingRecording === call.sid ? 'animate-bounce' : ''}`} />
                          הורד
                        </Button>
                      </>
                    )}
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(call.sid)}
                      disabled={deletingCall === call.sid}
                      data-testid={`button-delete-${call.sid}`}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className={`h-4 w-4 ${deletingCall === call.sid ? 'animate-pulse' : ''}`} />
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
        
        {filteredCalls.length === 0 && (
          <div className="text-center py-12">
            <Phone className="h-12 w-12 mx-auto mb-4 text-slate-400" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">אין שיחות</h3>
            <p className="text-slate-600">
              {searchQuery || statusFilter !== 'all' || directionFilter !== 'all'
                ? 'לא נמצאו שיחות התואמות למסננים'
                : 'עדיין לא היו שיחות במערכת'}
            </p>
          </div>
        )}
      </Card>

      {/* Call Details Modal */}
      {showDetails && selectedCall && callDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="modal-call-details">
          <Card className="p-6 max-w-2xl mx-4 max-h-[80vh] overflow-y-auto">
            <div className="space-y-6">
              {/* Header */}
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">פרטי שיחה</h2>
                  <p className="text-sm text-slate-500">{selectedCall.sid}</p>
                </div>
                <Button variant="ghost" onClick={() => setShowDetails(false)} data-testid="button-close-details">
                  ✕
                </Button>
              </div>

              {/* Call Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-700">לקוח</p>
                  <p className="text-slate-900">{selectedCall.lead_name || 'לקוח אלמוני'}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">מספר טלפון</p>
                  <p className="text-slate-900">{selectedCall.from_e164}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">משך השיחה</p>
                  <p className="text-slate-900">{formatDuration(selectedCall.duration)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">תאריך</p>
                  <p className="text-slate-900">{formatDateUtil(selectedCall.at)}</p>
                </div>
              </div>

              {/* Summary */}
              {callDetails.summary && (
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">סיכום השיחה</h3>
                  <p className="text-slate-700 bg-slate-50 p-3 rounded-lg">{callDetails.summary}</p>
                </div>
              )}

              {/* Transcript */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-lg font-semibold text-slate-900">תמליל מלא</h3>
                  {!editingTranscript ? (
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={handleEditTranscript}
                      data-testid="button-edit-transcript"
                    >
                      <Edit className="h-4 w-4 ml-2" />
                      ערוך תמליל
                    </Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button 
                        variant="default" 
                        size="sm" 
                        onClick={handleSaveTranscript}
                        data-testid="button-save-transcript"
                      >
                        <Save className="h-4 w-4 ml-2" />
                        שמור
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={handleCancelEdit}
                        data-testid="button-cancel-edit"
                      >
                        <X className="h-4 w-4 ml-2" />
                        ביטול
                      </Button>
                    </div>
                  )}
                </div>
                {editingTranscript ? (
                  <textarea
                    value={editedTranscript}
                    onChange={(e) => setEditedTranscript(e.target.value)}
                    className="w-full bg-white border border-slate-300 p-4 rounded-lg min-h-64 text-slate-700 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="textarea-transcript"
                  />
                ) : (
                  <div className="bg-slate-50 p-4 rounded-lg max-h-64 overflow-y-auto">
                    <p className="text-slate-700 whitespace-pre-wrap">{callDetails.transcript}</p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                {selectedCall.hasRecording && (
                  <>
                    <Button variant="outline" onClick={() => playRecording(selectedCall)}>
                      <PlayCircle className="h-4 w-4 ml-2" />
                      נגן הקלטה
                    </Button>
                    <Button variant="outline" onClick={() => downloadRecording(selectedCall)}>
                      <Download className="h-4 w-4 ml-2" />
                      הורד הקלטה
                    </Button>
                  </>
                )}
                <Button variant="outline" onClick={() => selectedCall && openInCRM(selectedCall)} data-testid="button-open-crm">
                  <ExternalLink className="h-4 w-4 ml-2" />
                  פתח בCRM
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Pagination */}
      {Math.ceil(totalCalls / PAGE_SIZE) > 1 && (
        <div className="flex items-center justify-center gap-4 mt-6 pb-4" data-testid="pagination-controls">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1 || loading}
            data-testid="button-prev-page"
          >
            הקודם
          </Button>
          
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span>עמוד</span>
            <span className="font-medium text-slate-900">{currentPage}</span>
            <span>מתוך</span>
            <span className="font-medium text-slate-900">{Math.ceil(totalCalls / PAGE_SIZE)}</span>
            <span className="text-slate-400">({totalCalls} שיחות)</span>
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(Math.ceil(totalCalls / PAGE_SIZE), p + 1))}
            disabled={currentPage === Math.ceil(totalCalls / PAGE_SIZE) || loading}
            data-testid="button-next-page"
          >
            הבא
          </Button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-full ml-3">
              <Phone className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">סה״כ שיחות</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-total-calls">{totalCalls}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-full ml-3">
              <Volume2 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">עם הקלטה</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-with-recording">
                {calls.filter(c => c.hasRecording).length}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-full ml-3">
              <FileText className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">עם תמליל</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-with-transcript">
                {calls.filter(c => c.hasTranscript).length}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-yellow-100 rounded-full ml-3">
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">תפוגה בקרוב</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-expiring">
                {calls.filter(c => {
                  const days = getDaysUntilExpiry(c.expiresAt);
                  return days !== null && days <= 2;
                }).length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="modal-delete-confirm">
          <Card className="p-6 max-w-sm mx-4">
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-medium text-slate-900 mb-2">מחיקת שיחה</h3>
              <p className="text-sm text-slate-600 mb-4">
                האם אתה בטוח שברצונך למחוק את השיחה? פעולה זו לא ניתנת לביטול.
              </p>
              <div className="flex gap-3 justify-center">
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(null)}
                  disabled={deletingCall !== null}
                >
                  ביטול
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    const callToDelete = calls.find(c => c.sid === showDeleteConfirm);
                    if (callToDelete) deleteCall(callToDelete);
                  }}
                  disabled={deletingCall !== null}
                >
                  {deletingCall ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white ml-2" />
                      מוחק...
                    </>
                  ) : (
                    'מחק'
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}