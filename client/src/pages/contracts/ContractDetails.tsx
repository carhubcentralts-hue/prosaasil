import React, { useState, useEffect } from 'react';
import { X, FileText, Upload, Send, Download, Ban, Calendar, User, Clock, CheckCircle } from 'lucide-react';
import { formatDate } from '../../shared/utils/format';
import { Badge } from '../../shared/components/Badge';
import { Button } from '../../shared/components/ui/Button';

interface ContractDetailsProps {
  contractId: number;
  onClose: () => void;
  onUpdate: () => void;
}

interface Contract {
  id: number;
  title: string;
  status: 'draft' | 'sent' | 'signed' | 'cancelled';
  lead_id?: number;
  signer_name?: string;
  signer_phone?: string;
  signer_email?: string;
  signed_at?: string;
  created_at: string;
  updated_at?: string;
  created_by?: number;
  files: ContractFile[];
}

interface ContractFile {
  id: number;
  purpose: string;
  attachment_id: number;
  filename: string;
  mime_type: string;
  file_size: number;
  created_at: string;
}

interface ContractEvent {
  id: number;
  event_type: string;
  metadata: any;
  created_at: string;
  created_by?: number;
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'טיוטה',
  sent: 'נשלח',
  signed: 'חתום',
  cancelled: 'בוטל',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'gray',
  sent: 'blue',
  signed: 'green',
  cancelled: 'red',
};

const EVENT_LABELS: Record<string, string> = {
  created: 'נוצר',
  file_uploaded: 'קובץ הועלה',
  sent_for_signature: 'נשלח לחתימה',
  viewed: 'נצפה',
  signed_completed: 'חתימה הושלמה',
  cancelled: 'בוטל',
  file_downloaded: 'קובץ הורד',
};

export function ContractDetails({ contractId, onClose, onUpdate }: ContractDetailsProps) {
  const [contract, setContract] = useState<Contract | null>(null);
  const [events, setEvents] = useState<ContractEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signUrl, setSignUrl] = useState<string | null>(null);

  useEffect(() => {
    loadContract();
    loadEvents();
  }, [contractId]);

  const loadContract = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/contracts/${contractId}`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to load contract');

      const data = await response.json();
      setContract(data);
    } catch (err) {
      console.error('Error loading contract:', err);
      setError('שגיאה בטעינת חוזה');
    } finally {
      setLoading(false);
    }
  };

  const loadEvents = async () => {
    try {
      const response = await fetch(`/api/contracts/${contractId}/events`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to load events');

      const data = await response.json();
      setEvents(data.events || []);
    } catch (err) {
      console.error('Error loading events:', err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('purpose', 'original');

      const response = await fetch(`/api/contracts/${contractId}/upload`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Upload failed');
      }

      await loadContract();
      await loadEvents();
      onUpdate();
    } catch (err: any) {
      console.error('Error uploading file:', err);
      setError(err.message || 'שגיאה בהעלאת קובץ');
    } finally {
      setUploading(false);
    }
  };

  const handleSendForSignature = async () => {
    if (!contract) return;

    setSending(true);
    setError(null);
    setSignUrl(null);

    try {
      const response = await fetch(`/api/contracts/${contractId}/send_for_signature`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to send for signature');
      }

      const data = await response.json();
      setSignUrl(data.sign_url);
      await loadContract();
      await loadEvents();
      onUpdate();
    } catch (err: any) {
      console.error('Error sending for signature:', err);
      setError(err.message || 'שגיאה בשליחה לחתימה');
    } finally {
      setSending(false);
    }
  };

  const handleCancelContract = async () => {
    if (!confirm('האם אתה בטוח שברצונך לבטל את החוזה?')) return;

    setCancelling(true);
    setError(null);

    try {
      const response = await fetch(`/api/contracts/${contractId}/cancel`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to cancel contract');
      }

      await loadContract();
      await loadEvents();
      onUpdate();
    } catch (err: any) {
      console.error('Error cancelling contract:', err);
      setError(err.message || 'שגיאה בביטול חוזה');
    } finally {
      setCancelling(false);
    }
  };

  const handleDownloadFile = async (fileId: number, filename: string) => {
    try {
      const response = await fetch(`/api/contracts/${contractId}/files/${fileId}/download`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to get download URL');

      const data = await response.json();
      window.open(data.url, '_blank');
    } catch (err) {
      console.error('Error downloading file:', err);
      setError('שגיאה בהורדת קובץ');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading || !contract) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl mx-4 p-6">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-600">טוען...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 my-8">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">{contract.title}</h2>
              <Badge color={STATUS_COLORS[contract.status] as any} className="mt-1">
                {STATUS_LABELS[contract.status]}
              </Badge>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">{error}</div>
          )}

          {signUrl && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-md">
              <p className="text-green-800 font-medium mb-2">קישור לחתימה נוצר בהצלחה!</p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={signUrl}
                  readOnly
                  className="flex-1 px-3 py-2 border border-green-300 rounded-md text-sm bg-white"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(signUrl);
                    alert('הקישור הועתק ללוח');
                  }}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                >
                  העתק
                </button>
              </div>
            </div>
          )}

          {/* Contract Info */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">שם החותם</label>
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-gray-400" />
                <span className="text-gray-900">{contract.signer_name || '—'}</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">תאריך יצירה</label>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-gray-400" />
                <span className="text-gray-900">{formatDate(contract.created_at)}</span>
              </div>
            </div>
            {contract.signer_phone && (
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">טלפון</label>
                <span className="text-gray-900">{contract.signer_phone}</span>
              </div>
            )}
            {contract.signer_email && (
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">אימייל</label>
                <span className="text-gray-900">{contract.signer_email}</span>
              </div>
            )}
            {contract.signed_at && (
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">תאריך חתימה</label>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span className="text-gray-900">{formatDate(contract.signed_at)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Files Section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-900">קבצים</h3>
              {contract.status === 'draft' && (
                <label className="cursor-pointer">
                  <input type="file" onChange={handleFileUpload} className="hidden" disabled={uploading} />
                  <div className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 text-sm">
                    <Upload className="w-4 h-4" />
                    {uploading ? 'מעלה...' : 'העלה קובץ'}
                  </div>
                </label>
              )}
            </div>

            {contract.files.length === 0 ? (
              <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">אין קבצים</div>
            ) : (
              <div className="space-y-2">
                {contract.files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">{file.filename}</p>
                        <p className="text-xs text-gray-500">
                          {file.purpose === 'original' ? 'מסמך מקורי' : 'מסמך חתום'} • {formatFileSize(file.file_size)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDownloadFile(file.id, file.filename)}
                      className="p-2 hover:bg-gray-200 rounded-lg transition"
                    >
                      <Download className="w-4 h-4 text-gray-600" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audit Timeline */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">היסטוריה</h3>
            {events.length === 0 ? (
              <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">אין אירועים</div>
            ) : (
              <div className="space-y-3">
                {events.map((event) => (
                  <div key={event.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <Clock className="w-4 h-4 text-gray-400 mt-1" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {EVENT_LABELS[event.event_type] || event.event_type}
                      </p>
                      <p className="text-xs text-gray-500">{formatDate(event.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t border-gray-200 flex gap-3">
          {contract.status === 'draft' && (
            <>
              <Button
                onClick={handleSendForSignature}
                disabled={sending || contract.files.length === 0}
                className="flex items-center gap-2"
              >
                <Send className="w-4 h-4" />
                {sending ? 'שולח...' : 'שלח לחתימה'}
              </Button>
              <Button onClick={handleCancelContract} disabled={cancelling} variant="secondary" className="flex items-center gap-2">
                <Ban className="w-4 h-4" />
                {cancelling ? 'מבטל...' : 'בטל חוזה'}
              </Button>
            </>
          )}
          {contract.status === 'sent' && (
            <Button onClick={handleCancelContract} disabled={cancelling} variant="secondary" className="flex items-center gap-2">
              <Ban className="w-4 h-4" />
              {cancelling ? 'מבטל...' : 'בטל חוזה'}
            </Button>
          )}
          <Button onClick={onClose} variant="secondary" className="mr-auto">
            סגור
          </Button>
        </div>
      </div>
    </div>
  );
}
