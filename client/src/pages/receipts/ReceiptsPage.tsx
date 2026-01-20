import React, { useState, useEffect, useCallback } from 'react';
import { 
  Receipt, 
  RefreshCw, 
  Search, 
  Filter, 
  Download, 
  ExternalLink,
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Clock,
  X,
  Mail,
  Link2,
  Unlink,
  Eye,
  ChevronDown,
  ChevronUp,
  Calendar,
  DollarSign,
  Building2
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import axios from 'axios';

// Receipt interface
interface ReceiptItem {
  id: number;
  source: string;
  gmail_message_id: string | null;
  from_email: string | null;
  subject: string | null;
  received_at: string | null;
  vendor_name: string | null;
  amount: number | null;
  currency: string;
  invoice_number: string | null;
  invoice_date: string | null;
  confidence: number | null;
  status: 'pending_review' | 'approved' | 'rejected' | 'not_receipt';
  attachment_id: number | null;
  attachment?: {
    id: number;
    filename: string;
    mime_type: string;
    size: number;
    signed_url?: string;
  };
  created_at: string | null;
}

interface GmailStatus {
  connected: boolean;
  status: string;
  email: string | null;
  last_sync_at: string | null;
  error_message: string | null;
}

interface ReceiptStats {
  total: number;
  total_amount: number;
  by_status: {
    pending_review: number;
    approved: number;
    rejected: number;
    not_receipt: number;
  };
}

// Status badge component
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    pending_review: { icon: Clock, color: 'bg-amber-100 text-amber-800', label: 'לבדיקה' },
    approved: { icon: CheckCircle, color: 'bg-green-100 text-green-800', label: 'מאושר' },
    rejected: { icon: XCircle, color: 'bg-red-100 text-red-800', label: 'נדחה' },
    not_receipt: { icon: AlertCircle, color: 'bg-gray-100 text-gray-600', label: 'לא קבלה' },
  };
  
  const config = statusConfig[status] || statusConfig.pending_review;
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      <Icon className="w-3 h-3 ml-1" />
      {config.label}
    </span>
  );
};

// Format currency
const formatCurrency = (amount: number | null, currency: string = 'ILS') => {
  if (amount === null) return '—';
  
  const symbols: Record<string, string> = {
    'ILS': '₪',
    'USD': '$',
    'EUR': '€',
    'GBP': '£'
  };
  
  const symbol = symbols[currency] || currency;
  // Use 'he' as primary locale with fallback to 'en-US'
  try {
    return `${symbol}${amount.toLocaleString('he', { minimumFractionDigits: 2 })}`;
  } catch {
    return `${symbol}${amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  }
};

// Format date in Hebrew locale
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '—';
  
  try {
    const date = new Date(dateStr);
    // Use 'he' as primary locale with fallback
    try {
      return date.toLocaleDateString('he', { 
        day: 'numeric', 
        month: 'short',
        year: 'numeric' 
      });
    } catch {
      return date.toLocaleDateString('en-US', { 
        day: 'numeric', 
        month: 'short', 
        year: 'numeric' 
      });
    }
  } catch {
    return dateStr;
  }
};

// Format relative time
const formatRelativeTime = (dateStr: string | null) => {
  if (!dateStr) return 'לא סונכרן';
  
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'עכשיו';
    if (minutes < 60) return `לפני ${minutes} דקות`;
    if (hours < 24) return `לפני ${hours} שעות`;
    return `לפני ${days} ימים`;
  } catch {
    return dateStr;
  }
};

// Receipt Card for mobile view
const ReceiptCard: React.FC<{
  receipt: ReceiptItem;
  onView: () => void;
  onMark: (status: string) => void;
}> = ({ receipt, onView, onMark }) => {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
      {/* Header row: Vendor + Amount */}
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">
            {receipt.vendor_name || 'ספק לא ידוע'}
          </h3>
          <p className="text-xs text-gray-500 truncate">{receipt.from_email || ''}</p>
        </div>
        <div className="text-left mr-3">
          <p className="font-bold text-lg text-gray-900">
            {formatCurrency(receipt.amount, receipt.currency)}
          </p>
        </div>
      </div>
      
      {/* Subject line */}
      {receipt.subject && (
        <p className="text-sm text-gray-600 truncate mb-2" title={receipt.subject}>
          {receipt.subject}
        </p>
      )}
      
      {/* Date + Status row */}
      <div className="flex justify-between items-center mb-3">
        <span className="text-xs text-gray-500 flex items-center">
          <Calendar className="w-3 h-3 ml-1" />
          {formatDate(receipt.received_at)}
        </span>
        <StatusBadge status={receipt.status} />
      </div>
      
      {/* Confidence indicator */}
      {receipt.confidence !== null && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>ביטחון זיהוי</span>
            <span>{receipt.confidence}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div 
              className={`h-1.5 rounded-full ${
                receipt.confidence >= 80 ? 'bg-green-500' : 
                receipt.confidence >= 60 ? 'bg-amber-500' : 
                'bg-red-500'
              }`}
              style={{ width: `${receipt.confidence}%` }}
            />
          </div>
        </div>
      )}
      
      {/* Action buttons - 44px minimum touch target */}
      <div className="flex gap-2">
        <button
          onClick={onView}
          className="flex-1 flex items-center justify-center px-4 py-3 bg-blue-50 text-blue-700 rounded-lg font-medium text-sm hover:bg-blue-100 transition-colors min-h-[44px]"
        >
          <Eye className="w-4 h-4 ml-2" />
          צפייה
        </button>
        
        {receipt.status === 'pending_review' && (
          <button
            onClick={() => onMark('approved')}
            className="flex-1 flex items-center justify-center px-4 py-3 bg-green-50 text-green-700 rounded-lg font-medium text-sm hover:bg-green-100 transition-colors min-h-[44px]"
          >
            <CheckCircle className="w-4 h-4 ml-2" />
            אישור
          </button>
        )}
        
        {receipt.attachment?.signed_url && (
          <a
            href={receipt.attachment.signed_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center px-4 py-3 bg-gray-50 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-100 transition-colors min-h-[44px]"
          >
            <Download className="w-4 h-4" />
          </a>
        )}
      </div>
    </div>
  );
};

// Receipt Detail Drawer
const ReceiptDrawer: React.FC<{
  receipt: ReceiptItem | null;
  onClose: () => void;
  onMark: (status: string) => void;
}> = ({ receipt, onClose, onMark }) => {
  if (!receipt) return null;
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed inset-y-0 left-0 w-full sm:w-96 bg-white shadow-xl z-50 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <h2 className="font-semibold text-lg">פרטי קבלה</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-4">
          {/* Attachment preview */}
          {receipt.attachment?.signed_url && (
            <div className="mb-4 bg-gray-100 rounded-lg overflow-hidden">
              {receipt.attachment.mime_type === 'application/pdf' ? (
                <div className="aspect-[3/4] relative">
                  <iframe
                    src={`${receipt.attachment.signed_url}#view=FitH`}
                    className="w-full h-full border-0"
                    title="Receipt PDF"
                  />
                </div>
              ) : receipt.attachment.mime_type.startsWith('image/') ? (
                <img
                  src={receipt.attachment.signed_url}
                  alt="Receipt"
                  className="w-full h-auto"
                />
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Receipt className="w-12 h-12 mx-auto mb-2" />
                  <p>{receipt.attachment.filename}</p>
                </div>
              )}
            </div>
          )}
          
          {/* Details */}
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">סטטוס</span>
              <StatusBadge status={receipt.status} />
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">ספק</span>
              <span className="font-medium">{receipt.vendor_name || '—'}</span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">סכום</span>
              <span className="font-bold text-lg">
                {formatCurrency(receipt.amount, receipt.currency)}
              </span>
            </div>
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">תאריך קבלה</span>
              <span>{formatDate(receipt.received_at)}</span>
            </div>
            
            {receipt.invoice_number && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600">מספר חשבונית</span>
                <span>{receipt.invoice_number}</span>
              </div>
            )}
            
            {receipt.invoice_date && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600">תאריך חשבונית</span>
                <span>{formatDate(receipt.invoice_date)}</span>
              </div>
            )}
            
            <div className="flex justify-between items-center">
              <span className="text-gray-600">מקור</span>
              <span className="flex items-center">
                <Mail className="w-4 h-4 ml-1 text-gray-400" />
                {receipt.source === 'gmail' ? 'Gmail' : receipt.source}
              </span>
            </div>
            
            {receipt.confidence !== null && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600">ביטחון זיהוי</span>
                <span className={`font-medium ${
                  receipt.confidence >= 80 ? 'text-green-600' : 
                  receipt.confidence >= 60 ? 'text-amber-600' : 
                  'text-red-600'
                }`}>{receipt.confidence}%</span>
              </div>
            )}
            
            {receipt.from_email && (
              <div>
                <span className="text-gray-600 text-sm">שולח</span>
                <p className="text-sm mt-1 break-all">{receipt.from_email}</p>
              </div>
            )}
            
            {receipt.subject && (
              <div>
                <span className="text-gray-600 text-sm">נושא</span>
                <p className="text-sm mt-1">{receipt.subject}</p>
              </div>
            )}
          </div>
          
          {/* Actions */}
          <div className="mt-6 space-y-3">
            {receipt.attachment?.signed_url && (
              <a
                href={receipt.attachment.signed_url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                <Download className="w-4 h-4 ml-2" />
                הורד קובץ
              </a>
            )}
            
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => onMark('approved')}
                disabled={receipt.status === 'approved'}
                className="flex items-center justify-center px-4 py-3 bg-green-100 text-green-700 rounded-lg font-medium hover:bg-green-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <CheckCircle className="w-4 h-4 ml-2" />
                אשר
              </button>
              
              <button
                onClick={() => onMark('rejected')}
                disabled={receipt.status === 'rejected'}
                className="flex items-center justify-center px-4 py-3 bg-red-100 text-red-700 rounded-lg font-medium hover:bg-red-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <XCircle className="w-4 h-4 ml-2" />
                דחה
              </button>
            </div>
            
            <button
              onClick={() => onMark('not_receipt')}
              disabled={receipt.status === 'not_receipt'}
              className="w-full flex items-center justify-center px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              <AlertCircle className="w-4 h-4 ml-2" />
              לא קבלה
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

// Main component
export function ReceiptsPage() {
  const { user } = useAuth();
  const [receipts, setReceipts] = useState<ReceiptItem[]>([]);
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [stats, setStats] = useState<ReceiptStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReceipt, setSelectedReceipt] = useState<ReceiptItem | null>(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  
  // Sync date range (separate from filter date range)
  const [syncFromDate, setSyncFromDate] = useState<string>('');
  const [syncToDate, setSyncToDate] = useState<string>('');
  const [showSyncOptions, setShowSyncOptions] = useState(false);
  
  // Sync progress tracking
  const [activeSyncRunId, setActiveSyncRunId] = useState<number | null>(null);
  const [syncProgress, setSyncProgress] = useState<{
    messages_scanned: number;
    saved_receipts: number;
    pages_scanned: number;
  } | null>(null);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Fetch Gmail status
  const fetchGmailStatus = useCallback(async () => {
    try {
      const res = await axios.get('/api/gmail/oauth/status');
      setGmailStatus(res.data);
    } catch (err) {
      console.error('Failed to fetch Gmail status:', err);
    }
  }, []);
  
  // Fetch receipts
  const fetchReceipts = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string | number> = {
        page,
        per_page: 20
      };
      
      if (statusFilter) params.status = statusFilter;
      if (searchQuery) params.vendor = searchQuery;
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      
      const res = await axios.get('/api/receipts', { params });
      
      setReceipts(res.data.items || []);
      setTotalPages(res.data.total_pages || 1);
      setError(null);
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to load receipts';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, searchQuery, fromDate, toDate]);
  
  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get('/api/receipts/stats');
      setStats(res.data.stats);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);
  
  // Initial load
  useEffect(() => {
    fetchGmailStatus();
    fetchReceipts();
    fetchStats();
  }, [fetchGmailStatus, fetchReceipts, fetchStats]);
  
  // Poll sync progress while sync is running
  useEffect(() => {
    if (!activeSyncRunId || !syncing) {
      return;
    }
    
    const pollProgress = async () => {
      try {
        const res = await axios.get(`/api/receipts/sync/status?run_id=${activeSyncRunId}`);
        if (res.data.success && res.data.sync_run) {
          const run = res.data.sync_run;
          setSyncProgress(run.progress);
          
          // If sync completed, cancelled, or failed, stop polling
          if (run.status !== 'running') {
            setActiveSyncRunId(null);
            setSyncing(false);
            setSyncProgress(null);
            
            // Refresh data
            await fetchReceipts();
            await fetchStats();
            await fetchGmailStatus();
            
            // Show completion message
            if (run.status === 'completed') {
              const successMsg = `✅ הסנכרון הושלם - ${run.progress.saved_receipts} קבלות נשמרו מתוך ${run.progress.messages_scanned} הודעות`;
              setError(successMsg);
              setTimeout(() => setError(null), 10000);
            } else if (run.status === 'cancelled') {
              const cancelMsg = `⚠️ הסנכרון בוטל - ${run.progress.saved_receipts} קבלות נשמרו עד כה`;
              setError(cancelMsg);
              setTimeout(() => setError(null), 10000);
            } else if (run.status === 'failed') {
              setError(`❌ שגיאה בסנכרון: ${run.error_message || 'Unknown error'}`);
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch sync progress:', err);
      }
    };
    
    // Poll every 2 seconds
    const interval = setInterval(pollProgress, 2000);
    pollProgress(); // Initial poll
    
    return () => clearInterval(interval);
  }, [activeSyncRunId, syncing, fetchReceipts, fetchStats, fetchGmailStatus]);
  
  // Handle Gmail connect
  const handleConnect = async () => {
    try {
      const res = await axios.get('/api/gmail/oauth/start');
      if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to start OAuth';
      setError(errorMsg);
    }
  };
  
  // Handle Gmail disconnect
  const handleDisconnect = async () => {
    if (!confirm('האם אתה בטוח שברצונך לנתק את Gmail? הקבלות הקיימות יישמרו.')) {
      return;
    }
    
    try {
      await axios.delete('/api/gmail/oauth/disconnect');
      await fetchGmailStatus();
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to disconnect';
      setError(errorMsg);
    }
  };
  
  // Handle sync
  const handleSync = useCallback(async () => {
    try {
      setSyncing(true);
      setError(null); // Clear any previous errors
      setSyncProgress(null); // Reset progress
      
      // Build sync request body with date range if specified
      const syncParams: {
        from_date?: string;
        to_date?: string;
      } = {};
      
      if (syncFromDate) {
        syncParams.from_date = syncFromDate;
      }
      if (syncToDate) {
        syncParams.to_date = syncToDate;
      }
      
      // Start the sync - this returns immediately with sync_run_id
      const res = await axios.post('/api/receipts/sync', syncParams, {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 300000 // 5 minute timeout
      });
      
      if (res.data.success && res.data.sync_run_id) {
        // Store sync run ID to start polling
        setActiveSyncRunId(res.data.sync_run_id);
        
        // Show starting message
        let dateRangeMsg = '';
        if (syncFromDate || syncToDate) {
          if (syncFromDate && syncToDate) {
            dateRangeMsg = ` (${syncFromDate} עד ${syncToDate})`;
          } else if (syncFromDate) {
            dateRangeMsg = ` (מ-${syncFromDate})`;
          } else {
            dateRangeMsg = ` (עד ${syncToDate})`;
          }
        }
        setError(`🔄 מסנכרן קבלות${dateRangeMsg}...`);
      }
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Sync failed';
      setError(errorMsg);
      setSyncing(false);
      setActiveSyncRunId(null);
      setSyncProgress(null);
    }
  }, [syncFromDate, syncToDate]);
  
  // Handle cancel sync
  const handleCancelSync = useCallback(async () => {
    if (!activeSyncRunId) return;
    
    try {
      await axios.post(`/api/receipts/sync/${activeSyncRunId}/cancel`);
      setError('⏸️ מבטל סנכרון...');
      // The polling will detect the cancelled status and update UI
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to cancel sync';
      setError(errorMsg);
    }
  }, [activeSyncRunId]);
  
  // Handle mark receipt
  const handleMark = async (receiptId: number, status: string) => {
    try {
      await axios.patch(`/api/receipts/${receiptId}/mark`, { status });
      
      // Update local state
      setReceipts(prev => prev.map(r => 
        r.id === receiptId ? { ...r, status: status as ReceiptItem['status'] } : r
      ));
      
      if (selectedReceipt?.id === receiptId) {
        setSelectedReceipt({ ...selectedReceipt, status: status as ReceiptItem['status'] });
      }
      
      await fetchStats();
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to update status';
      setError(errorMsg);
    }
  };
  
  // Handle view receipt with signed URL
  const handleViewReceipt = async (receipt: ReceiptItem) => {
    try {
      const res = await axios.get(`/api/receipts/${receipt.id}`);
      setSelectedReceipt(res.data.receipt);
    } catch (err) {
      console.error('Failed to fetch receipt details:', err);
      setSelectedReceipt(receipt);
    }
  };
  
  // Check for URL params (after OAuth redirect)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    
    if (params.get('connected') === 'true') {
      fetchGmailStatus();
      // Auto-trigger sync after successful connection
      handleSync();
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }
    
    const errorParam = params.get('error');
    if (errorParam) {
      // Map error codes to user-friendly Hebrew messages
      const errorMessages: Record<string, string> = {
        'encryption_not_configured': 'שגיאת הגדרה: מפתח ההצפנה לא מוגדר. אנא פנה למנהל המערכת להגדרת ENCRYPTION_KEY.',
        'token_exchange_failed': 'שגיאה בקבלת הרשאה מ-Google. אנא נסה שוב.',
        'no_refresh_token': 'לא התקבל טוקן מ-Google. ייתכן שכבר אישרת את החיבור. נתק ונסה שוב.',
        'userinfo_failed': 'שגיאה בקבלת מידע משתמש מ-Google. אנא נסה שוב.',
        'invalid_state': 'שגיאת אבטחה: מצב לא תקין. ייתכן שניסיון תקיפה. נסה שוב.',
        'session_expired': 'תוקף ההפעלה פג. אנא נסה שוב.',
        'no_code': 'לא התקבל קוד אישור מ-Google. אנא נסה שוב.',
        'server_error': 'שגיאת שרת. אנא נסה שוב מאוחר יותר.',
      };
      
      const friendlyMessage = errorMessages[errorParam] || `שגיאה בחיבור Gmail: ${errorParam}`;
      setError(friendlyMessage);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [fetchGmailStatus, handleSync]);
  
  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center">
              <Receipt className="w-6 h-6 text-blue-600 ml-2" />
              <h1 className="text-xl font-bold text-gray-900">קבלות</h1>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Gmail connection status */}
              {gmailStatus?.connected ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600 hidden sm:inline">
                    {gmailStatus.email}
                  </span>
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  <button
                    onClick={handleDisconnect}
                    className="text-sm text-gray-500 hover:text-gray-700 flex items-center"
                  >
                    <Unlink className="w-4 h-4 ml-1" />
                    <span className="hidden sm:inline">נתק</span>
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleConnect}
                  className="flex items-center px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
                >
                  <Mail className="w-4 h-4 ml-2" />
                  חבר Gmail
                </button>
              )}
              
              {/* Sync button */}
              {gmailStatus?.connected && (
                <>
                  <button
                    onClick={() => setShowSyncOptions(!showSyncOptions)}
                    className="flex items-center px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    title="אפשרויות סנכרון"
                  >
                    <Calendar className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ml-2 ${syncing ? 'animate-spin' : ''}`} />
                    {syncing ? 'מסנכרן...' : 'סנכרן'}
                  </button>
                </>
              )}
            </div>
          </div>
          
          {/* Sync options panel */}
          {gmailStatus?.connected && showSyncOptions && (
            <div className="mt-4 bg-blue-50 rounded-lg border border-blue-200 p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-3">בחר טווח תאריכים לסנכרון</h3>
              <p className="text-xs text-gray-600 mb-3">
                השאר ריק לסנכרון רגיל (חודש אחרון). מלא תאריכים לייצוא קבלות מטווח ספציפי.
              </p>
              
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">מתאריך</label>
                  <input
                    type="date"
                    value={syncFromDate}
                    onChange={(e) => setSyncFromDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">עד תאריך</label>
                  <input
                    type="date"
                    value={syncToDate}
                    onChange={(e) => setSyncToDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={() => {
                      setSyncFromDate('');
                      setSyncToDate('');
                    }}
                    className="w-full px-3 py-2 border border-gray-300 bg-white rounded-lg hover:bg-gray-50 transition-colors text-sm"
                  >
                    נקה
                  </button>
                </div>
              </div>
              
              {/* Quick preset buttons */}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => {
                    const now = new Date();
                    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
                    setSyncFromDate(lastMonth.toISOString().split('T')[0]);
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs hover:bg-gray-50 transition-colors"
                >
                  חודש אחרון
                </button>
                <button
                  onClick={() => {
                    const now = new Date();
                    const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
                    setSyncFromDate(threeMonthsAgo.toISOString().split('T')[0]);
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs hover:bg-gray-50 transition-colors"
                >
                  3 חודשים
                </button>
                <button
                  onClick={() => {
                    const now = new Date();
                    const sixMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
                    setSyncFromDate(sixMonthsAgo.toISOString().split('T')[0]);
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs hover:bg-gray-50 transition-colors"
                >
                  6 חודשים
                </button>
                <button
                  onClick={() => {
                    const now = new Date();
                    const oneYearAgo = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
                    setSyncFromDate(oneYearAgo.toISOString().split('T')[0]);
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs hover:bg-gray-50 transition-colors"
                >
                  שנה שלמה
                </button>
                <button
                  onClick={() => {
                    const now = new Date();
                    const threeYearsAgo = new Date(now.getFullYear() - 3, now.getMonth(), now.getDate());
                    setSyncFromDate(threeYearsAgo.toISOString().split('T')[0]);
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs hover:bg-gray-50 transition-colors"
                >
                  3 שנים
                </button>
                <button
                  onClick={() => {
                    // All time - leave from_date empty, set to_date to today
                    setSyncFromDate('');
                    const now = new Date();
                    setSyncToDate(now.toISOString().split('T')[0]);
                  }}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors font-medium"
                >
                  כל התקופה
                </button>
              </div>
              
              {(syncFromDate || syncToDate) && (
                <div className="mt-3 p-2 bg-blue-100 border border-blue-300 rounded text-xs text-blue-800">
                  ⚠️ סנכרון עם טווח תאריכים יכול לקחת מספר דקות. המערכת תעבוד על כל ההודעות בטווח שבחרת.
                </div>
              )}
            </div>
          )}
          
          {/* Sync progress bar */}
          {syncing && syncProgress && (
            <div className="mt-4 bg-white rounded-lg border border-blue-300 shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <RefreshCw className="w-5 h-5 text-blue-600 animate-spin" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">מסנכרן קבלות...</p>
                    <p className="text-xs text-gray-600">
                      {syncProgress.messages_scanned} הודעות נסרקו · {syncProgress.saved_receipts} קבלות נמצאו
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleCancelSync}
                  className="flex items-center px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors font-medium text-sm min-h-[44px] touch-manipulation"
                  title="עצור סנכרון"
                >
                  <X className="w-4 h-4 ml-1" />
                  <span className="hidden sm:inline">ביטול</span>
                </button>
              </div>
              
              {/* Progress bar - indeterminate animation */}
              <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-blue-600 animate-pulse" style={{ width: '70%' }}></div>
              </div>
              
              <p className="text-xs text-gray-500 mt-2 text-center">
                תהליך זה עשוי לקחת מספר דקות עבור סנכרון של תקופה ארוכה
              </p>
            </div>
          )}
          
          {/* Last sync time */}
          {gmailStatus?.last_sync_at && !syncing && (
            <p className="text-xs text-gray-500 mt-2">
              סונכרן לאחרונה: {formatRelativeTime(gmailStatus.last_sync_at)}
            </p>
          )}
        </div>
      </div>
      
      {/* Stats cards */}
      {stats && (
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white rounded-lg border border-gray-200 p-3">
              <p className="text-xs text-gray-500 mb-1">סה״כ מאושרות</p>
              <p className="text-lg font-bold text-gray-900">{stats.by_status.approved}</p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-3">
              <p className="text-xs text-gray-500 mb-1">לבדיקה</p>
              <p className="text-lg font-bold text-amber-600">{stats.by_status.pending_review}</p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-3">
              <p className="text-xs text-gray-500 mb-1">סה״כ סכום</p>
              <p className="text-lg font-bold text-green-600">
                {formatCurrency(stats.total_amount, 'ILS')}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-3">
              <p className="text-xs text-gray-500 mb-1">סה״כ קבלות</p>
              <p className="text-lg font-bold text-gray-900">{stats.total}</p>
            </div>
          </div>
        </div>
      )}
      
      {/* Filters */}
      <div className="max-w-7xl mx-auto px-4 py-2">
        <div className="flex items-center gap-2 mb-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="חפש לפי ספק..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="w-full pr-10 pl-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          
          {/* Filter toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center px-3 py-2 border rounded-lg transition-colors ${
              showFilters || statusFilter || fromDate || toDate ? 'bg-blue-50 border-blue-200 text-blue-700' : 'border-gray-200 text-gray-600'
            }`}
          >
            <Filter className="w-4 h-4 ml-1" />
            סינון
            {showFilters ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
          </button>
        </div>
        
        {/* Filter panel */}
        {showFilters && (
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4 space-y-4">
            {/* Status filters */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">סינון לפי סטטוס</label>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => { setStatusFilter(''); setPage(1); }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    !statusFilter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  הכל
                </button>
                <button
                  onClick={() => { setStatusFilter('pending_review'); setPage(1); }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    statusFilter === 'pending_review' ? 'bg-amber-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  לבדיקה
                </button>
                <button
                  onClick={() => { setStatusFilter('approved'); setPage(1); }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    statusFilter === 'approved' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  מאושרות
                </button>
                <button
                  onClick={() => { setStatusFilter('rejected'); setPage(1); }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    statusFilter === 'rejected' ? 'bg-red-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  נדחו
                </button>
              </div>
            </div>
            
            {/* Date filters */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">סינון לפי תאריך</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">מתאריך</label>
                  <input
                    type="date"
                    value={fromDate}
                    onChange={(e) => { setFromDate(e.target.value); setPage(1); }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">עד תאריך</label>
                  <input
                    type="date"
                    value={toDate}
                    onChange={(e) => { setToDate(e.target.value); setPage(1); }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                </div>
              </div>
              {(fromDate || toDate) && (
                <button
                  onClick={() => { setFromDate(''); setToDate(''); setPage(1); }}
                  className="mt-2 text-sm text-blue-600 hover:text-blue-700 flex items-center"
                >
                  <X className="w-3 h-3 ml-1" />
                  נקה תאריכים
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      
      {/* Error/Success message */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 mb-4">
          <div className={`border px-4 py-3 rounded-lg flex items-start ${
            error.startsWith('✅') 
              ? 'bg-green-50 border-green-200 text-green-700' 
              : 'bg-red-50 border-red-200 text-red-700'
          }`}>
            {error.startsWith('✅') ? (
              <CheckCircle className="w-5 h-5 ml-2 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 ml-2 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-medium">
                {error.startsWith('✅') ? 'הצלחה' : 'שגיאה'}
              </p>
              <p className="text-sm">{error}</p>
            </div>
            <button 
              onClick={() => setError(null)}
              className={error.startsWith('✅') ? 'text-green-500 hover:text-green-700' : 'text-red-500 hover:text-red-700'}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
      
      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 pb-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
          </div>
        ) : receipts.length === 0 ? (
          <div className="text-center py-16">
            <Receipt className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {gmailStatus?.connected ? 'אין קבלות' : 'חבר את Gmail כדי להתחיל'}
            </h3>
            <p className="text-gray-500 mb-6">
              {gmailStatus?.connected 
                ? 'לחץ על "סנכרן" כדי לייבא קבלות מהמייל שלך'
                : 'חבר את חשבון Gmail שלך כדי לייבא קבלות אוטומטית'
              }
            </p>
            {!gmailStatus?.connected && (
              <button
                onClick={handleConnect}
                className="inline-flex items-center px-6 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
              >
                <Mail className="w-5 h-5 ml-2" />
                חבר Gmail
              </button>
            )}
          </div>
        ) : (
          <>
            {/* Mobile: Cards */}
            <div className="md:hidden space-y-3">
              {receipts.map((receipt) => (
                <ReceiptCard
                  key={receipt.id}
                  receipt={receipt}
                  onView={() => handleViewReceipt(receipt)}
                  onMark={(status) => handleMark(receipt.id, status)}
                />
              ))}
            </div>
            
            {/* Desktop: Table */}
            <div className="hidden md:block bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">תאריך</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">ספק</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">סכום</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">סטטוס</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">ביטחון</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">פעולות</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {receipts.map((receipt) => (
                    <tr key={receipt.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        {formatDate(receipt.received_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-gray-900">
                          {receipt.vendor_name || '—'}
                        </div>
                        <div className="text-xs text-gray-500 truncate max-w-xs">
                          {receipt.from_email}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">
                        {formatCurrency(receipt.amount, receipt.currency)}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={receipt.status} />
                      </td>
                      <td className="px-4 py-3">
                        {receipt.confidence !== null && (
                          <div className="flex items-center">
                            <div className="w-16 bg-gray-200 rounded-full h-1.5 ml-2">
                              <div 
                                className={`h-1.5 rounded-full ${
                                  receipt.confidence >= 80 ? 'bg-green-500' : 
                                  receipt.confidence >= 60 ? 'bg-amber-500' : 
                                  'bg-red-500'
                                }`}
                                style={{ width: `${receipt.confidence}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500">{receipt.confidence}%</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleViewReceipt(receipt)}
                            className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="צפייה"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          {receipt.status === 'pending_review' && (
                            <>
                              <button
                                onClick={() => handleMark(receipt.id, 'approved')}
                                className="p-1.5 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded"
                                title="אשר"
                              >
                                <CheckCircle className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleMark(receipt.id, 'rejected')}
                                className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                                title="דחה"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center items-center gap-2 mt-6">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  הקודם
                </button>
                <span className="text-sm text-gray-600">
                  עמוד {page} מתוך {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  הבא
                </button>
              </div>
            )}
          </>
        )}
      </div>
      
      {/* Receipt detail drawer */}
      <ReceiptDrawer
        receipt={selectedReceipt}
        onClose={() => setSelectedReceipt(null)}
        onMark={(status) => {
          if (selectedReceipt) {
            handleMark(selectedReceipt.id, status);
          }
        }}
      />
    </div>
  );
}

export default ReceiptsPage;
