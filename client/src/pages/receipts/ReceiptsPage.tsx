import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom';
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
  Building2,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import axios from 'axios';

// Constants
const SYNC_POLL_INTERVAL_MS = 2000; // Poll every 2 seconds
const SYNC_MAX_POLL_DURATION_MS = 10 * 60 * 1000; // Stop polling after 10 minutes
const FILTER_DEBOUNCE_MS = 300; // Debounce filter changes

// Preview status constants
const PREVIEW_STATUS = {
  PENDING: 'pending',
  GENERATED: 'generated',
  FAILED: 'failed',
  NOT_AVAILABLE: 'not_available',
  SKIPPED: 'skipped'
} as const;

type PreviewStatus = typeof PREVIEW_STATUS[keyof typeof PREVIEW_STATUS];

// =============================================
// Mobile Date Picker Modal Component
// Uses Portal for proper layering and scroll handling on iOS
// =============================================
interface MobileDatePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  fromDate: string;
  toDate: string;
  onFromDateChange: (date: string) => void;
  onToDateChange: (date: string) => void;
  onApply: () => void;
  onClear: () => void;
}

const MobileDatePickerModal: React.FC<MobileDatePickerModalProps> = ({
  isOpen,
  onClose,
  fromDate,
  toDate,
  onFromDateChange,
  onToDateChange,
  onApply,
  onClear
}) => {
  const scrollYRef = useRef<number>(0);
  const modalRef = useRef<HTMLDivElement>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  
  // Lock body scroll on iOS when modal is open
  useEffect(() => {
    if (isOpen) {
      // Save current scroll position
      scrollYRef.current = window.scrollY;
      
      // Lock body scroll with iOS-compatible method
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollYRef.current}px`;
      document.body.style.width = '100%';
      document.body.style.overflow = 'hidden';
    } else {
      // Restore scroll position
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflow = '';
      window.scrollTo(0, scrollYRef.current);
    }
    
    return () => {
      // Cleanup on unmount
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflow = '';
    };
  }, [isOpen]);
  
  // Hebrew month names
  const hebrewMonths = [
    'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
    'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'
  ];
  
  // Generate month options for the last 24 months
  const getMonthOptions = () => {
    const options: { value: string; label: string; fromDate: string; toDate: string }[] = [];
    const now = new Date();
    
    for (let i = 0; i < 24; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const year = date.getFullYear();
      const month = date.getMonth();
      
      // Calculate start of month
      const startOfMonth = new Date(year, month, 1);
      // Calculate end of month
      const endOfMonth = new Date(year, month + 1, 0);
      
      options.push({
        value: `${year}-${String(month + 1).padStart(2, '0')}`,
        label: `${hebrewMonths[month]} ${year}`,
        fromDate: startOfMonth.toISOString().split('T')[0],
        toDate: endOfMonth.toISOString().split('T')[0]
      });
    }
    
    return options;
  };
  
  const monthOptions = getMonthOptions();
  
  const handleMonthSelect = (monthValue: string) => {
    const option = monthOptions.find(m => m.value === monthValue);
    if (option) {
      setSelectedMonth(monthValue);
      onFromDateChange(option.fromDate);
      onToDateChange(option.toDate);
    }
  };
  
  const handleQuickSelect = (days: number) => {
    const now = new Date();
    const past = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    onFromDateChange(past.toISOString().split('T')[0]);
    onToDateChange(now.toISOString().split('T')[0]);
    setSelectedMonth('');
  };
  
  if (!isOpen) return null;
  
  // Render using Portal for proper z-index handling
  return ReactDOM.createPortal(
    <div 
      className="fixed inset-0 z-[9999] flex items-end justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      
      {/* Modal Content - Bottom Sheet Style */}
      <div 
        ref={modalRef}
        className="relative bg-white rounded-t-2xl w-full max-h-[80vh] overflow-hidden shadow-2xl"
        style={{
          overscrollBehavior: 'contain',
          WebkitOverflowScrolling: 'touch',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle bar for mobile */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>
        
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">סינון לפי תאריך</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Scrollable content */}
        <div 
          className="overflow-y-auto px-4 py-4 space-y-6"
          style={{
            maxHeight: 'calc(80vh - 140px)',
            overscrollBehavior: 'contain',
            WebkitOverflowScrolling: 'touch',
          }}
        >
          {/* Quick select buttons */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">בחירה מהירה</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => handleQuickSelect(7)}
                className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-200 transition-colors min-h-[44px]"
              >
                שבוע אחרון
              </button>
              <button
                onClick={() => handleQuickSelect(30)}
                className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-200 transition-colors min-h-[44px]"
              >
                חודש אחרון
              </button>
              <button
                onClick={() => handleQuickSelect(90)}
                className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-200 transition-colors min-h-[44px]"
              >
                3 חודשים
              </button>
              <button
                onClick={() => handleQuickSelect(365)}
                className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-200 transition-colors min-h-[44px]"
              >
                שנה אחרונה
              </button>
            </div>
          </div>
          
          {/* Month selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">בחירת חודש</label>
            <select
              value={selectedMonth}
              onChange={(e) => handleMonthSelect(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base min-h-[44px]"
            >
              <option value="">בחר חודש...</option>
              {monthOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          
          {/* Custom date range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">או בחר טווח תאריכים</label>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">מתאריך</label>
                <input
                  type="date"
                  value={fromDate}
                  onChange={(e) => {
                    onFromDateChange(e.target.value);
                    setSelectedMonth('');
                  }}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base min-h-[44px]"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">עד תאריך</label>
                <input
                  type="date"
                  value={toDate}
                  onChange={(e) => {
                    onToDateChange(e.target.value);
                    setSelectedMonth('');
                  }}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base min-h-[44px]"
                />
              </div>
            </div>
          </div>
          
          {/* Selected range display */}
          {(fromDate || toDate) && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-800">
                <strong>טווח נבחר:</strong>{' '}
                {fromDate ? new Date(fromDate).toLocaleDateString('he') : 'התחלה'} - {toDate ? new Date(toDate).toLocaleDateString('he') : 'סיום'}
              </p>
            </div>
          )}
        </div>
        
        {/* Footer buttons - fixed at bottom */}
        <div className="border-t border-gray-200 px-4 py-4 bg-white flex gap-3">
          <button
            onClick={() => {
              onClear();
              setSelectedMonth('');
            }}
            className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium text-sm hover:bg-gray-50 transition-colors min-h-[44px]"
          >
            נקה
          </button>
          <button
            onClick={() => {
              onApply();
              onClose();
            }}
            className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors min-h-[44px]"
          >
            החל סינון
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

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
  status: 'pending_review' | 'approved' | 'rejected' | 'not_receipt' | 'incomplete';
  attachment_id: number | null;
  preview_attachment_id: number | null;
  preview_status?: PreviewStatus;
  preview_failure_reason?: string | null;
  attachment?: {
    id: number;
    filename: string;
    mime_type: string;
    size: number;
    signed_url?: string;
  };
  preview_attachment?: {
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

interface SyncStatus {
  id: number;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'partial';
  mode: string;
  started_at: string;
  finished_at: string | null;
  pages_scanned: number;
  messages_scanned: number;
  candidate_receipts: number;
  saved_receipts: number;
  errors_count: number;
  error_message: string | null;
  progress_percentage: number;
}

// API Response interfaces
interface ApiError {
  code: string;
  message: string;
  hint?: string;
}

interface ApiResponse<T = any> {
  ok: boolean;
  data?: T;
  error?: ApiError;
}

// Axios error response interface
interface AxiosErrorResponse {
  response?: {
    data?: ApiResponse;
  };
}

// Status badge component
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    pending_review: { icon: Clock, color: 'bg-amber-100 text-amber-800', label: 'לבדיקה' },
    approved: { icon: CheckCircle, color: 'bg-green-100 text-green-800', label: 'מאושר' },
    rejected: { icon: XCircle, color: 'bg-red-100 text-red-800', label: 'נדחה' },
    not_receipt: { icon: AlertCircle, color: 'bg-gray-100 text-gray-600', label: 'לא קבלה' },
    incomplete: { icon: AlertCircle, color: 'bg-orange-100 text-orange-800', label: 'לא הושלם' },
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
  onDelete: () => void;
}> = ({ receipt, onView, onMark, onDelete }) => {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
      {/* Preview Image */}
      {receipt.preview_attachment?.signed_url && (
        <div className="mb-3 -mx-4 -mt-4">
          <img 
            src={receipt.preview_attachment.signed_url}
            alt={receipt.vendor_name || 'Receipt preview'}
            className="w-full h-48 object-contain bg-gray-50 rounded-t-xl"
            loading="lazy"
          />
        </div>
      )}
      
      {/* Header row: Vendor + Amount + Delete */}
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">
            {receipt.vendor_name || 'ספק לא ידוע'}
          </h3>
          <p className="text-xs text-gray-500 truncate">{receipt.from_email || ''}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-left mr-3">
            <p className="font-bold text-lg text-gray-900">
              {formatCurrency(receipt.amount, receipt.currency)}
            </p>
          </div>
          <button
            onClick={onDelete}
            className="p-2 hover:bg-red-50 rounded text-red-600 transition"
            title="מחק קבלה"
          >
            <X className="w-5 h-5" />
          </button>
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
      
      {/* Preview Status - Show if preview failed or not available */}
      {!receipt.preview_attachment?.signed_url && receipt.preview_status && (
        <div className="mb-3 p-2 rounded-lg bg-gray-50 border border-gray-200">
          <div className="flex items-center gap-2 text-xs">
            {receipt.preview_status === PREVIEW_STATUS.FAILED && (
              <>
                <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-amber-700 font-medium">תצוגה מקדימה נכשלה</span>
                  {receipt.preview_failure_reason && (
                    <p 
                      className="text-gray-600 mt-1 text-xs break-words"
                      title={receipt.preview_failure_reason}
                    >
                      {receipt.preview_failure_reason}
                    </p>
                  )}
                </div>
              </>
            )}
            {receipt.preview_status === PREVIEW_STATUS.PENDING && (
              <>
                <Clock className="w-4 h-4 text-blue-500 flex-shrink-0" />
                <span className="text-blue-700">ממתין לתצוגה מקדימה</span>
              </>
            )}
            {receipt.preview_status === PREVIEW_STATUS.NOT_AVAILABLE && (
              <>
                <XCircle className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <span className="text-gray-600">תצוגה מקדימה לא זמינה</span>
              </>
            )}
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
  
  // New state variables for sync progress
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  
  // Mobile date picker modal state
  const [showMobileDatePicker, setShowMobileDatePicker] = useState(false);
  
  // Sync date range (separate from filter date range)
  const [syncFromDate, setSyncFromDate] = useState<string>('');
  const [syncToDate, setSyncToDate] = useState<string>('');
  const [showSyncOptions, setShowSyncOptions] = useState(false);
  const [forceRescan, setForceRescan] = useState(false); // Force rescan with purge
  
  // Sync progress tracking
  const [activeSyncRunId, setActiveSyncRunId] = useState<number | null>(null);
  const [syncProgress, setSyncProgress] = useState<{
    messages_scanned: number;
    saved_receipts: number;
    pages_scanned: number;
    candidate_receipts?: number;
    errors_count?: number;
  } | null>(null);
  const [syncProgressPercentage, setSyncProgressPercentage] = useState<number>(0);
  const [cancelling, setCancelling] = useState(false);
  
  // Delete-all progress tracking
  const [deleteJobId, setDeleteJobId] = useState<number | null>(null);
  const [deleteProgress, setDeleteProgress] = useState<{
    status: string;
    total: number;
    processed: number;
    succeeded: number;
    failed_count: number;
    percent: number;
    last_error?: string;
  } | null>(null);
  const [showDeleteProgress, setShowDeleteProgress] = useState(false);
  const deleteProgressRef = useRef<{ active: boolean; jobId: number | null }>({ active: false, jobId: null });
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // AbortController for canceling pending fetch requests
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // Debounce timer ref
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Fetch Gmail status
  const fetchGmailStatus = useCallback(async () => {
    try {
      const res = await axios.get('/api/gmail/oauth/status');
      setGmailStatus(res.data);
    } catch (err) {
      console.error('Failed to fetch Gmail status:', err);
    }
  }, []);
  
  // Fetch receipts with AbortController support
  const fetchReceipts = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      const params: Record<string, string | number> = {
        page,
        per_page: 20
      };
      
      if (statusFilter) params.status = statusFilter;
      if (searchQuery) params.vendor = searchQuery;
      
      // Ensure dates are sent in proper ISO format (YYYY-MM-DD)
      if (fromDate) {
        // Ensure from_date is at start of day
        params.from_date = fromDate;
        console.log('[ReceiptsPage] Filtering from_date:', fromDate);
      }
      if (toDate) {
        // Ensure to_date is at end of day
        params.to_date = toDate;
        console.log('[ReceiptsPage] Filtering to_date:', toDate);
      }
      
      console.log('[ReceiptsPage] Fetching receipts with params:', params);
      
      const res = await axios.get('/api/receipts', { params, signal });
      
      // Replace list entirely (not append) to avoid duplicates
      setReceipts(res.data.items || []);
      setTotalPages(res.data.total_pages || 1);
      setError(null);
      
      console.log('[ReceiptsPage] Received', res.data.items?.length || 0, 'receipts, total:', res.data.total);
    } catch (err: unknown) {
      // Ignore abort errors
      if (axios.isCancel(err)) {
        console.log('[ReceiptsPage] Request was cancelled');
        return;
      }
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to load receipts';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, searchQuery, fromDate, toDate]);
  
  // Debounced fetch effect - cancels previous request and debounces
  useEffect(() => {
    // Cancel any pending debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    
    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Create new AbortController
    const controller = new AbortController();
    abortControllerRef.current = controller;
    
    // Debounce the fetch
    debounceTimerRef.current = setTimeout(() => {
      fetchReceipts(controller.signal);
    }, FILTER_DEBOUNCE_MS);
    
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      controller.abort();
    };
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
  
  // Initial fetch (without dependencies on filters since we handle that in the effect above)
  const doInitialFetch = useCallback(async () => {
    await fetchGmailStatus();
    await fetchStats();
  }, [fetchGmailStatus, fetchStats]);
  
  // Poll sync status for background sync
  const pollSyncStatus = useCallback(async () => {
    try {
      const response = await axios.get('/api/receipts/sync/status', {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      
      if (response.data.success && response.data.sync_run) {
        const status = response.data.sync_run;
        setSyncStatus(status);
        
        // CRITICAL: Update progress data too!
        setSyncProgress(status.progress);
        setSyncProgressPercentage(status.progress_percentage || 0);
        
        // Stop polling if sync is done
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
          setSyncInProgress(false);
          setCancelling(false);
          // Reload receipts - trigger via state change which will be caught by the debounced effect
          setPage(p => p); // This triggers a re-fetch via the effect
          await fetchStats();
        }
      }
    } catch (error) {
      console.error('Failed to fetch sync status:', error);
      // Show error to user
      const errorMsg = '⚠️ שגיאה בקבלת מצב הסנכרון';
      setError(errorMsg);
      setTimeout(() => setError(null), 5000);
    }
  }, [user?.token, fetchStats]);
  
  // Initial load - load status, stats, and check for active sync AND delete jobs
  useEffect(() => {
    const initializeAndCheckSync = async () => {
      await doInitialFetch();
      
      // Check if there's an active sync run on page load/refresh
      try {
        const latestSyncRes = await axios.get('/api/receipts/sync/latest');
        if (latestSyncRes.data.success && latestSyncRes.data.sync_run) {
          const run = latestSyncRes.data.sync_run;
          
          // If sync is still running, restore the UI state
          if (run.status === 'running' || run.status === 'paused') {
            console.log('📍 Found active sync on page load:', run);
            setActiveSyncRunId(run.id);
            setSyncing(true);
            setSyncInProgress(true);
            setSyncProgress(run.progress);
            setSyncProgressPercentage(run.progress_percentage || 0);
            
            // Restore from localStorage if available
            const storedSyncDates = localStorage.getItem('activeSyncDates');
            if (storedSyncDates) {
              try {
                const { from_date, to_date } = JSON.parse(storedSyncDates);
                if (from_date) setSyncFromDate(from_date);
                if (to_date) setSyncToDate(to_date);
              } catch (e) {
                console.error('Failed to parse stored sync dates:', e);
              }
            }
          } else {
            // Sync completed/failed - clear localStorage
            localStorage.removeItem('activeSyncDates');
          }
        }
      } catch (err) {
        console.error('Failed to check for active sync:', err);
      }
      
      // CRITICAL: Check for active delete job on page load/refresh
      try {
        // Check localStorage for active delete job
        const storedDeleteJobId = localStorage.getItem('activeDeleteJobId');
        if (storedDeleteJobId) {
          const jobId = parseInt(storedDeleteJobId, 10);
          console.log('📍 Found stored delete job ID on page load:', jobId);
          
          // Fetch current job status
          const jobRes = await axios.get(`/api/receipts/jobs/${jobId}`);
          if (jobRes.data.success) {
            const job = jobRes.data;
            
            // If job is still active, restore UI state
            if (job.status === 'running' || job.status === 'paused' || job.status === 'queued') {
              console.log('📍 Restoring active delete job:', job);
              setDeleteJobId(jobId);
              setShowDeleteProgress(true);
              setDeleteProgress({
                status: job.status,
                total: job.total,
                processed: job.processed,
                succeeded: job.succeeded,
                failed_count: job.failed_count,
                percent: job.percent,
                last_error: job.last_error
              });
              
              // Start polling
              deleteProgressRef.current = { active: true, jobId };
              pollDeleteProgress(jobId);
            } else {
              // Job completed/failed - clear localStorage
              localStorage.removeItem('activeDeleteJobId');
            }
          }
        }
      } catch (err) {
        console.error('Failed to check for active delete job:', err);
        // Clear localStorage if job fetch fails
        localStorage.removeItem('activeDeleteJobId');
      }
    };
    
    initializeAndCheckSync();
  }, [doInitialFetch]);
  
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
          setSyncProgressPercentage(run.progress_percentage || 0);
          
          // If sync completed, cancelled, or failed, stop polling
          if (run.status !== 'running') {
            setActiveSyncRunId(null);
            setSyncing(false);
            setSyncProgress(null);
            setSyncProgressPercentage(0);
            setCancelling(false);
            
            // Clear localStorage when sync completes
            localStorage.removeItem('activeSyncDates');
            
            // Refresh data - trigger via state change
            setPage(p => p); // This triggers a re-fetch via the effect
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
        // Show error to user if polling fails
        const errorMsg = '⚠️ שגיאה בקבלת מצב הסנכרון. הסנכרון ממשיך ברקע.';
        setError(errorMsg);
        setTimeout(() => setError(null), 5000);
      }
    };
    
    // Poll at regular interval
    const interval = setInterval(pollProgress, SYNC_POLL_INTERVAL_MS);
    pollProgress(); // Initial poll
    
    return () => clearInterval(interval);
  }, [activeSyncRunId, syncing, fetchStats, fetchGmailStatus]);
  
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
    console.log('🔔 Sync button clicked with dates:', { syncFromDate, syncToDate, forceRescan });
    
    if (syncInProgress) {
      alert('סנכרון כבר רץ ברקע. אנא המתן לסיום.');
      return;
    }

    // Safety confirmation for force rescan
    if (forceRescan) {
      const confirmed = window.confirm(
        '⚠️ אזהרה: סנכרון מאולץ ימחק את כל הקבלות הקיימות בטווח התאריכים שנבחר ויסנכרן אותן מחדש.\n\n' +
        'המשך רק אם אתה בטוח שברצונך לבצע פעולה זו.\n\n' +
        'האם להמשיך?'
      );
      
      if (!confirmed) {
        return;
      }
    }

    try {
      setSyncing(true);
      setError(null);
      setSyncError(null);
      setSyncInProgress(true);
      setSyncProgress(null);
      
      // Build sync request body with date range if specified
      const syncParams: {
        from_date?: string;
        to_date?: string;
        force?: boolean;
      } = {};
      
      if (syncFromDate) {
        syncParams.from_date = syncFromDate;
      }
      if (syncToDate) {
        syncParams.to_date = syncToDate;
      }
      if (forceRescan) {
        syncParams.force = true;
      }

      // Save sync dates to localStorage for persistence across refresh
      if (syncFromDate || syncToDate) {
        localStorage.setItem('activeSyncDates', JSON.stringify(syncParams));
      }

      console.log('🔔 Starting sync with params:', syncParams);
      const response = await axios.post('/api/receipts/sync', syncParams, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      console.log('🔔 Sync response:', response.status, response.data);

      // Backend now returns 202 Accepted immediately
      if (response.status === 202) {
        // Start polling for status
        const pollInterval = setInterval(async () => {
          await pollSyncStatus();
        }, SYNC_POLL_INTERVAL_MS);

        // Stop polling after max duration
        setTimeout(() => clearInterval(pollInterval), SYNC_MAX_POLL_DURATION_MS);

        // Initial status fetch
        await pollSyncStatus();
      } else if (response.status === 409) {
        // Sync already in progress
        alert('סנכרון כבר רץ. ממשיך לעקוב אחר ההתקדמות...');
        setSyncInProgress(true);
        // Start polling
        const pollInterval = setInterval(pollSyncStatus, SYNC_POLL_INTERVAL_MS);
        setTimeout(() => clearInterval(pollInterval), SYNC_MAX_POLL_DURATION_MS);
      }

    } catch (error: any) {
      console.error('Sync error:', error);
      
      // Check if this is a worker availability error (503 Service Unavailable)
      if (error.response?.status === 503) {
        const workerError = error.response?.data?.error || 'No workers available';
        const workerUnavailableMsg = '⚠️ המערכת כרגע ללא Worker פעיל - הסנכרון לא יכול להתחיל. אנא פנה לתמיכה הטכנית.';
        setSyncError(workerUnavailableMsg);
        setError(workerUnavailableMsg);
        console.error('Worker availability error:', workerError);
      } else {
        setSyncError(error.response?.data?.error || 'שגיאה בסנכרון');
      }
      setSyncInProgress(false);
    } finally {
      setSyncing(false);
    }
  }, [syncFromDate, syncToDate, forceRescan, user?.token, pollSyncStatus]);
  
  // Handle cancel sync
  const handleCancelSync = useCallback(async () => {
    if (!activeSyncRunId || cancelling) return;
    
    try {
      setCancelling(true);
      await axios.post(`/api/receipts/sync/${activeSyncRunId}/cancel`);
      setError('⏸️ מבטל סנכרון...');
      // The polling will detect the cancelled status and update UI
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to cancel sync';
      setError(errorMsg);
    } finally {
      // Keep cancelling state true until polling detects the cancelled status
      // This prevents multiple cancel requests
    }
  }, [activeSyncRunId, cancelling]);
  
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
  
  // Handle delete receipt
  const handleDeleteReceipt = async (receiptId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק קבלה זו?')) {
      return;
    }

    try {
      await axios.delete(`/api/receipts/${receiptId}`, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      
      // Reload receipts
      await fetchReceipts();
      await fetchStats();
      alert('הקבלה נמחקה בהצלחה');
    } catch (error: any) {
      console.error('Delete error:', error);
      alert(error.response?.data?.error || 'שגיאה במחיקת הקבלה');
    }
  };

  // Handle purge all receipts
  const handlePurgeAllReceipts = async () => {
    // Use window.confirm for better accessibility
    const firstConfirm = window.confirm(
      'פעולה זו תמחק את כל הקבלות! האם אתה בטוח?'
    );
    
    if (!firstConfirm) {
      return;
    }
    
    const confirmed = prompt(
      'אישור סופי: הקלד "DELETE" באנגלית:'
    );
    
    if (confirmed !== 'DELETE') {
      alert('האישור בוטל - לא הוקלד "DELETE"');
      return;
    }

    try {
      const response = await axios.delete('/api/receipts/purge', {
        headers: { Authorization: `Bearer ${user?.token}` },
        data: {
          confirm: true,
          typed: 'DELETE',
          delete_attachments: true  // CHANGED: Delete attachments to allow fresh rescan without duplicates
        }
      });
      
      if (response.data.success) {
        await fetchReceipts();
        await fetchStats();
        alert(`נמחקו ${response.data.deleted_receipts_count} קבלות בהצלחה`);
      }
    } catch (error: any) {
      console.error('Purge error:', error);
      alert(error.response?.data?.error || 'שגיאה במחיקת הקבלות');
    }
  };
  
  // =============================================
  // Handle Delete All Receipts with Progress Tracking
  // =============================================
  const handleDeleteAllReceipts = async () => {
    // Confirmation dialogs
    const firstConfirm = window.confirm(
      'פעולה זו תמחק את כל הקבלות באמצעות תהליך רקע יציב. האם אתה בטוח?'
    );
    
    if (!firstConfirm) {
      return;
    }
    
    const confirmed = prompt(
      'אישור סופי: הקלד "DELETE" באנגלית:'
    );
    
    if (confirmed !== 'DELETE') {
      alert('האישור בוטל - לא הוקלד "DELETE"');
      return;
    }

    try {
      // Start delete job
      const response = await axios.post('/api/receipts/delete_all', {}, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      
      if (response.data.success) {
        const jobId = response.data.job_id;
        setDeleteJobId(jobId);
        setShowDeleteProgress(true);
        setDeleteProgress({
          status: response.data.status,
          total: response.data.total,
          processed: 0,
          succeeded: 0,
          failed_count: 0,
          percent: 0
        });
        
        // CRITICAL: Store job ID in localStorage for persistence across refresh
        localStorage.setItem('activeDeleteJobId', jobId.toString());
        
        // Start polling for progress
        deleteProgressRef.current = { active: true, jobId };
        pollDeleteProgress(jobId);
      }
    } catch (error: any) {
      console.error('Delete all error:', error);
      alert(error.response?.data?.error || 'שגיאה בהפעלת מחיקת הקבלות');
    }
  };
  
  // Poll delete progress
  const pollDeleteProgress = async (jobId: number) => {
    if (!deleteProgressRef.current.active || deleteProgressRef.current.jobId !== jobId) {
      return;
    }
    
    try {
      const response = await axios.get(`/api/receipts/jobs/${jobId}`, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      
      if (response.data.success) {
        const progress = response.data;
        setDeleteProgress({
          status: progress.status,
          total: progress.total,
          processed: progress.processed,
          succeeded: progress.succeeded,
          failed_count: progress.failed_count,
          percent: progress.percent,
          last_error: progress.last_error
        });
        
        // Check if job is complete
        if (progress.status === 'completed') {
          deleteProgressRef.current.active = false;
          // CRITICAL: Clear localStorage when job completes
          localStorage.removeItem('activeDeleteJobId');
          // Wait a bit to show 100% before closing
          setTimeout(() => {
            setShowDeleteProgress(false);
            setDeleteJobId(null);
            fetchReceipts();
            fetchStats();
            alert(`מחיקה הושלמה בהצלחה! נמחקו ${progress.succeeded} קבלות.`);
          }, 2000);
          return;
        } else if (progress.status === 'failed') {
          deleteProgressRef.current.active = false;
          // CRITICAL: Clear localStorage when job fails
          localStorage.removeItem('activeDeleteJobId');
          alert(`מחיקה נכשלה: ${progress.last_error || 'שגיאה לא ידועה'}`);
          setShowDeleteProgress(false);
          return;
        } else if (progress.status === 'cancelled') {
          deleteProgressRef.current.active = false;
          // CRITICAL: Clear localStorage when job is cancelled
          localStorage.removeItem('activeDeleteJobId');
          alert('מחיקה בוטלה');
          setShowDeleteProgress(false);
          return;
        }
        
        // Continue polling (1.5 seconds)
        setTimeout(() => pollDeleteProgress(jobId), 1500);
      }
    } catch (error) {
      console.error('Error polling delete progress:', error);
      // Retry after a short delay
      setTimeout(() => pollDeleteProgress(jobId), 2000);
    }
  };
  
  // Cancel delete job
  const handleCancelDelete = async () => {
    if (!deleteJobId) return;
    
    try {
      await axios.post(`/api/receipts/jobs/${deleteJobId}/cancel`, {}, {
        headers: { Authorization: `Bearer ${user?.token}` }
      });
      
      deleteProgressRef.current.active = false;
      // CRITICAL: Clear localStorage when job is cancelled
      localStorage.removeItem('activeDeleteJobId');
      alert('מחיקה בוטלה');
      setShowDeleteProgress(false);
      fetchReceipts();
      fetchStats();
    } catch (error) {
      console.error('Cancel delete error:', error);
      alert('שגיאה בביטול המחיקה');
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
  
  // REMOVED: SyncProgressDisplay component - using only the card-based progress bar now
  // This eliminates the duplicate progress bar issue as per requirement
  
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
                  {/* Delete All Button (Stable with Progress) */}
                  <button
                    onClick={handleDeleteAllReceipts}
                    disabled={showDeleteProgress}
                    className="flex items-center px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium disabled:opacity-50"
                    title="מחק את כל הקבלות (יציב עם סרגל התקדמות)"
                  >
                    <X className="w-4 h-4 sm:ml-2" />
                    <span className="hidden sm:inline">מחק הכל</span>
                  </button>
                  
                  <button
                    onClick={() => setShowSyncOptions(!showSyncOptions)}
                    className="flex items-center px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                    title="אפשרויות סנכרון"
                  >
                    <Calendar className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleSync}
                    disabled={syncing || syncInProgress}
                    className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ml-2 ${(syncing || syncInProgress) ? 'animate-spin' : ''}`} />
                    {syncInProgress ? 'רץ...' : syncing ? 'מסנכרן...' : 'סנכרן'}
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
              
              {/* Force Rescan Option */}
              <div className="mt-4 pt-3 border-t border-blue-200">
                <label className="flex items-start gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={forceRescan}
                    onChange={(e) => setForceRescan(e.target.checked)}
                    className="mt-0.5 w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-2 focus:ring-red-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 group-hover:text-gray-700">
                        סנכרון מאולץ (Force Rescan)
                      </span>
                      <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded">
                        מתקדם
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">
                      מחיקת כל הקבלות בטווח התאריכים וסנכרון מחדש מ-Gmail. 
                      <span className="font-medium text-red-600"> שימו לב: פעולה זו תמחק קבלות קיימות!</span>
                    </p>
                    {forceRescan && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs">
                        <div className="flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                          <div className="text-red-800">
                            <p className="font-medium mb-1">⚠️ מצב מתקדם מופעל</p>
                            <ul className="list-disc list-inside space-y-0.5">
                              <li>כל הקבלות בטווח התאריכים ימחקו</li>
                              <li>קבצי מקור וקבצי תצוגה מקדימה של קבלות ימחקו</li>
                              <li>קבלות יסונכרנו מחדש מ-Gmail</li>
                              <li>תתבקש אישור סופי לפני תחילת הסנכרון</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </label>
              </div>
              
              {/* Sync button with selected dates */}
              <div className="mt-4 pt-3 border-t border-blue-200">
                <button
                  onClick={handleSync}
                  disabled={syncing || syncInProgress}
                  className={`w-full flex items-center justify-center px-4 py-3 rounded-lg disabled:opacity-50 transition-colors font-medium text-sm ${
                    forceRescan 
                      ? 'bg-red-600 text-white hover:bg-red-700' 
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  <RefreshCw className={`w-4 h-4 ml-2 ${(syncing || syncInProgress) ? 'animate-spin' : ''}`} />
                  {syncInProgress ? 'רץ...' : syncing ? 'מסנכרן...' : forceRescan ? 'סנכרון מאולץ' : (syncFromDate || syncToDate) ? 'סנכרן עם התאריכים שנבחרו' : 'סנכרן'}
                </button>
              </div>
            </div>
          )}
          
          {/* Sync progress bar - show if syncing OR if syncInProgress (even without progress yet) */}
          {(syncing || syncInProgress) && (
            <div className="mt-4 bg-white rounded-lg border border-blue-300 shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <RefreshCw className="w-5 h-5 text-blue-600 animate-spin" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">מסנכרן קבלות...</p>
                    {syncProgress && (
                      <p className="text-xs text-gray-600">
                        {syncProgress.messages_scanned} הודעות נסרקו · {syncProgress.saved_receipts} קבלות נמצאו
                      </p>
                    )}
                    {!syncProgress && (
                      <p className="text-xs text-gray-600">מתחיל סנכרון...</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={handleCancelSync}
                  disabled={!activeSyncRunId || cancelling}
                  className="flex items-center px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors font-medium text-sm min-h-[44px] touch-manipulation disabled:opacity-50 disabled:cursor-not-allowed"
                  title="עצור סנכרון"
                >
                  <X className="w-4 h-4 ml-1" />
                  <span className="hidden sm:inline">{cancelling ? 'מבטל...' : 'ביטול'}</span>
                </button>
              </div>
              
              {/* Progress bar - showing actual progress percentage */}
              <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-400 via-blue-600 to-blue-500 transition-all duration-300 ease-out"
                  style={{ width: `${syncProgressPercentage || 0}%` }}
                ></div>
              </div>
              
              {syncProgress && (
                <p className="text-xs text-gray-500 mt-2 flex items-center justify-between">
                  <span>{syncProgressPercentage || 0}% הושלם</span>
                  <span>
                    {[
                      `${syncProgress.pages_scanned || 0} עמודים`,
                      syncProgress.candidate_receipts ? `${syncProgress.candidate_receipts} מועמדים` : null,
                      syncProgress.errors_count ? `${syncProgress.errors_count} שגיאות` : null
                    ].filter(Boolean).join(' · ')}
                  </span>
                </p>
              )}
              {!syncProgress && (
                <p className="text-xs text-gray-500 mt-2">
                  מכין סנכרון...
                </p>
              )}
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
                  onClick={() => { setStatusFilter('incomplete'); setPage(1); }}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    statusFilter === 'incomplete' ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  לא הושלם
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
              
              {/* Mobile: Button to open date picker modal */}
              <div className="md:hidden mb-3">
                <button
                  onClick={() => setShowMobileDatePicker(true)}
                  className={`w-full flex items-center justify-between px-4 py-3 border rounded-lg transition-colors min-h-[44px] ${
                    fromDate || toDate 
                      ? 'bg-blue-50 border-blue-200 text-blue-700' 
                      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className="flex items-center">
                    <Calendar className="w-4 h-4 ml-2" />
                    {fromDate || toDate ? (
                      <span>
                        {fromDate ? new Date(fromDate).toLocaleDateString('he') : 'התחלה'} - {toDate ? new Date(toDate).toLocaleDateString('he') : 'סיום'}
                      </span>
                    ) : (
                      'בחר טווח תאריכים'
                    )}
                  </span>
                  <ChevronDown className="w-4 h-4" />
                </button>
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
              
              {/* Desktop: Inline date inputs */}
              <div className="hidden md:grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                  className="mt-2 text-sm text-blue-600 hover:text-blue-700 hidden md:flex items-center"
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
                  onDelete={() => handleDeleteReceipt(receipt.id)}
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
                          <button
                            onClick={() => handleDeleteReceipt(receipt.id)}
                            className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                            title="מחק"
                          >
                            <X className="w-4 h-4" />
                          </button>
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
      
      {/* REMOVED: <SyncProgressDisplay /> - using only card-based progress bar to avoid duplicates */}
      
      {/* Mobile Date Picker Modal */}
      <MobileDatePickerModal
        isOpen={showMobileDatePicker}
        onClose={() => setShowMobileDatePicker(false)}
        fromDate={fromDate}
        toDate={toDate}
        onFromDateChange={setFromDate}
        onToDateChange={setToDate}
        onApply={() => {
          setPage(1);
          // The debounced effect will handle the fetch
        }}
        onClear={() => {
          setFromDate('');
          setToDate('');
          setPage(1);
        }}
      />
      
      {/* ============================================= */}
      {/* Delete Progress Modal */}
      {/* ============================================= */}
      {showDeleteProgress && deleteProgress && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-900">מוחק קבלות...</h3>
              {deleteProgress.status === 'running' && (
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
              )}
            </div>
            
            {/* Progress Bar */}
            <div className="mb-6">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-gray-700">
                  {deleteProgress.processed} מתוך {deleteProgress.total}
                </span>
                <span className="text-sm font-bold text-blue-600">
                  {deleteProgress.percent.toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div 
                  className="bg-blue-600 h-full transition-all duration-300 ease-out rounded-full"
                  style={{ width: `${deleteProgress.percent}%` }}
                />
              </div>
            </div>
            
            {/* Stats */}
            <div className="space-y-2 mb-6">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-600">נמחקו בהצלחה:</span>
                <span className="font-medium text-green-600">{deleteProgress.succeeded}</span>
              </div>
              {deleteProgress.failed_count > 0 && (
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-600">נכשלו:</span>
                  <span className="font-medium text-red-600">{deleteProgress.failed_count}</span>
                </div>
              )}
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-600">סטטוס:</span>
                <span className="font-medium text-gray-900">
                  {deleteProgress.status === 'running' ? 'רץ' :
                   deleteProgress.status === 'queued' ? 'בתור' :
                   deleteProgress.status === 'paused' ? 'מושהה' :
                   deleteProgress.status === 'completed' ? 'הושלם' :
                   deleteProgress.status}
                </span>
              </div>
            </div>
            
            {/* Error Message */}
            {deleteProgress.last_error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-xs text-red-800">
                  <strong>שגיאה אחרונה:</strong> {deleteProgress.last_error}
                </p>
              </div>
            )}
            
            {/* Info */}
            <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-800">
                <strong>💡 טיפ:</strong> המערכת מוחקת את הקבלות באצוות קטנות כדי לשמור על יציבות. 
                התהליך עשוי לקחת מספר דקות בהתאם לכמות הקבלות.
              </p>
            </div>
            
            {/* Actions */}
            <div className="flex gap-3">
              {deleteProgress.status === 'running' && (
                <button
                  onClick={handleCancelDelete}
                  className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium"
                >
                  בטל
                </button>
              )}
              {deleteProgress.status === 'completed' && (
                <button
                  onClick={() => {
                    setShowDeleteProgress(false);
                    setDeleteJobId(null);
                    fetchReceipts();
                    fetchStats();
                  }}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
                >
                  סגור
                </button>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

export default ReceiptsPage;
