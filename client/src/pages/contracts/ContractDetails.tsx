import React, { useState, useEffect } from 'react';
import { X, FileText, Upload, Send, Download, Ban, Calendar, User, Clock, CheckCircle, Edit3, Trash2, Eye, Save, Edit } from 'lucide-react';
import { formatDate } from '../../shared/utils/format';
import { Badge } from '../../shared/components/Badge';
import { Button } from '../../shared/components/ui/Button';
import { SignatureFieldMarker, SignatureField } from '../../components/SignatureFieldMarker';
import { logger } from '../../shared/utils/logger';

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

type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'neutral';

const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  draft: 'neutral',
  sent: 'info',
  signed: 'success',
  cancelled: 'error',
};

const EVENT_LABELS: Record<string, string> = {
  created: 'נוצר',
  file_uploaded: 'קובץ הועלה',
  sent_for_signature: 'נשלח לחתימה',
  viewed: 'נצפה',
  signed_completed: 'חתימה הושלמה',
  cancelled: 'בוטל',
  file_downloaded: 'קובץ הורד',
  updated: 'עודכן',
};

function FilePreviewItem({ file, contractId, formatFileSize }: {
  file: ContractFile;
  contractId: number;
  formatFileSize: (bytes: number) => string;
}) {
  const [showPreview, setShowPreview] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Use ref to persist URL across re-renders to prevent iframe reset bug
  // We need both ref AND state because:
  // - ref persists data across any re-renders of this component (prevents data loss)
  // - state triggers React re-renders when data changes (updates UI)
  // This dual approach ensures stability while maintaining reactivity
  const previewUrlRef = React.useRef<string | null>(null);
  const textContentRef = React.useRef<string | null>(null);

  const canPreview = file.mime_type === 'application/pdf' || 
                     file.mime_type.startsWith('image/') || 
                     file.mime_type.startsWith('text/') ||
                     file.mime_type === 'application/json';

  const isTextFile = file.mime_type.startsWith('text/') || file.mime_type === 'application/json';

  // Debug: Log state changes only in development mode to diagnose render issues
  // TODO: Remove this after bug is confirmed fixed in production
  React.useEffect(() => {
    const DEBUG_PDF_VIEWER = process.env.NODE_ENV === 'development' && false; // Set to true to enable
    if (DEBUG_PDF_VIEWER) {
      if (previewUrl) {
        logger.debug('[FilePreviewItem] previewUrl set:', previewUrl);
      } else if (showPreview) {
        logger.warn('[FilePreviewItem] previewUrl is null while showPreview is true');
      }
    }
  }, [previewUrl, showPreview]);

  const handlePreviewToggle = async () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }

    // Guard: if URL already cached, use it instead of re-fetching
    if (previewUrlRef.current) {
      setPreviewUrl(previewUrlRef.current);
      if (textContentRef.current) {
        setTextContent(textContentRef.current);
      }
      setShowPreview(true);
      return;
    }

    setLoadingPreview(true);
    try {
      const response = await fetch(`/api/contracts/${contractId}/files/${file.id}/download`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        // Cache in ref to persist across re-renders
        previewUrlRef.current = data.url;
        setPreviewUrl(data.url);
        
        // For text files, fetch the content
        if (isTextFile && data.url) {
          try {
            const textResponse = await fetch(data.url);
            if (textResponse.ok) {
              const text = await textResponse.text();
              // Cache in ref to persist across re-renders
              textContentRef.current = text;
              setTextContent(text);
            }
          } catch (err) {
            logger.error('Error loading text content:', err);
          }
        }
        
        setShowPreview(true);
      }
    } catch (err) {
      logger.error('Error loading preview:', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await fetch(`/api/contracts/${contractId}/files/${file.id}/download`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        window.open(data.url, '_blank');
      }
    } catch (err) {
      logger.error('Error downloading file:', err);
    }
  };

  return (
    <div className="bg-gray-50 rounded-lg hover:bg-gray-100 overflow-hidden">
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-gray-400" />
          <div>
            <p className="font-medium text-gray-900">{file.filename}</p>
            <p className="text-xs text-gray-500">
              {file.purpose === 'original' ? 'מסמך מקורי' : file.purpose === 'signed' ? 'מסמך חתום' : 'מסמך נוסף'} - {formatFileSize(file.file_size)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {canPreview && (
            <button
              onClick={handlePreviewToggle}
              disabled={loadingPreview}
              className="p-2 hover:bg-blue-100 rounded-lg transition text-blue-600 disabled:opacity-50"
              title={showPreview ? 'סגור תצוגה מקדימה' : 'תצוגה מקדימה'}
            >
              {loadingPreview ? (
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          )}
          <button onClick={handleDownload} className="p-2 hover:bg-gray-200 rounded-lg transition" title="הורד קובץ">
            <Download className="w-4 h-4 text-gray-600" />
          </button>
        </div>
      </div>
      {showPreview && previewUrl && (
        <div className="border-t border-gray-200 p-4 bg-white">
          {file.mime_type === 'application/pdf' ? (
            <iframe 
              key={`pdf-${file.id}`}
              src={`${previewUrl}#view=FitH`} 
              className="w-full min-h-[400px] h-[60vh] md:h-[70vh] max-h-[800px] rounded-lg border border-gray-300" 
              title={file.filename}
              style={{ border: 'none', display: 'block' }}
            />
          ) : file.mime_type.startsWith('image/') ? (
            <div className="flex justify-center">
              <img src={previewUrl} alt={file.filename} className="max-w-full max-h-96 rounded-lg border border-gray-300" />
            </div>
          ) : isTextFile && textContent ? (
            <pre className="w-full h-96 overflow-auto p-4 bg-gray-900 text-gray-100 rounded-lg border border-gray-300 text-sm font-mono whitespace-pre-wrap" dir="ltr">
              {textContent}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function ContractDetails({ contractId, onClose, onUpdate }: ContractDetailsProps) {
  const [contract, setContract] = useState<Contract | null>(null);
  const [events, setEvents] = useState<ContractEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signUrl, setSignUrl] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editSignerName, setEditSignerName] = useState('');
  const [editSignerPhone, setEditSignerPhone] = useState('');
  const [editSignerEmail, setEditSignerEmail] = useState('');
  const [showSignatureMarker, setShowSignatureMarker] = useState(false);
  const [signatureFieldCount, setSignatureFieldCount] = useState(0);

  useEffect(() => {
    loadContract();
    loadEvents();
    loadSignatureFieldCount();
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
      logger.error('Error loading events:', err);
    }
  };

  const loadSignatureFieldCount = async () => {
    try {
      const response = await fetch(`/api/contracts/${contractId}/signature-fields`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setSignatureFieldCount(data.fields?.length || 0);
      }
    } catch (err) {
      logger.error('Error loading signature field count:', err);
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
      logger.error('Error uploading file:', err);
      setError(err.message || 'שגיאה בהעלאת קובץ');
    } finally {
      setUploading(false);
    }
  };

  const handleSendForSignature = async () => {
    if (!contract) return;

    // Validate signature fields exist
    if (signatureFieldCount === 0) {
      setError('יש לסמן לפחות אזור חתימה אחד לפני שליחה. לחץ על "סמן אזורי חתימה" כדי להוסיף.');
      return;
    }

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
      logger.error('Error sending for signature:', err);
      setError(err.message || 'שגיאה בשליחה לחתימה');
    } finally {
      setSending(false);
    }
  };

  const handleSaveSignatureFields = async (fields: SignatureField[]) => {
    const response = await fetch(`/api/contracts/${contractId}/signature-fields`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ fields }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to save signature fields');
    }

    await loadSignatureFieldCount();
    setShowSignatureMarker(false);
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
      logger.error('Error cancelling contract:', err);
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
      logger.error('Error downloading file:', err);
      setError('שגיאה בהורדת קובץ');
    }
  };

  const startEditing = () => {
    if (!contract) return;
    setEditTitle(contract.title);
    setEditSignerName(contract.signer_name || '');
    setEditSignerPhone(contract.signer_phone || '');
    setEditSignerEmail(contract.signer_email || '');
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setError(null);
  };

  const handleSaveEdit = async () => {
    if (!contract) return;
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`/api/contracts/${contractId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: editTitle.trim(),
          signer_name: editSignerName.trim() || null,
          signer_phone: editSignerPhone.trim() || null,
          signer_email: editSignerEmail.trim() || null,
        }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update contract');
      }
      await loadContract();
      await loadEvents();
      setIsEditing(false);
      onUpdate();
    } catch (err: any) {
      logger.error('Error updating contract:', err);
      setError(err.message || 'שגיאה בעדכון חוזה');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteContract = async () => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את החוזה? פעולה זו אינה ניתנת לביטול.')) return;
    setDeleting(true);
    setError(null);
    try {
      const response = await fetch(`/api/contracts/${contractId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete contract');
      }
      onUpdate();
      onClose();
    } catch (err: any) {
      logger.error('Error deleting contract:', err);
      setError(err.message || 'שגיאה במחיקת חוזה');
    } finally {
      setDeleting(false);
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
              {isEditing ? (
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="text-xl font-bold text-gray-900 border border-gray-300 rounded-md px-2 py-1 focus:ring-2 focus:ring-blue-500"
                  placeholder="כותרת החוזה"
                />
              ) : (
                <h2 className="text-xl font-bold text-gray-900">{contract.title}</h2>
              )}
              <Badge variant={STATUS_VARIANTS[contract.status]} className="mt-1">
                {STATUS_LABELS[contract.status]}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {contract.status === 'draft' && !isEditing && (
              <button onClick={startEditing} className="p-2 hover:bg-blue-100 rounded-lg transition text-blue-600" title="ערוך חוזה">
                <Edit3 className="w-5 h-5" />
              </button>
            )}
            {(contract.status === 'draft' || contract.status === 'cancelled') && (
              <button onClick={handleDeleteContract} disabled={deleting} className="p-2 hover:bg-red-100 rounded-lg transition text-red-600 disabled:opacity-50" title="מחק חוזה">
                <Trash2 className="w-5 h-5" />
              </button>
            )}
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
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
              {isEditing ? (
                <input
                  type="text"
                  value={editSignerName}
                  onChange={(e) => setEditSignerName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                  placeholder="שם החותם"
                />
              ) : (
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-900">{contract.signer_name || '—'}</span>
                </div>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">תאריך יצירה</label>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-gray-400" />
                <span className="text-gray-900">{formatDate(contract.created_at)}</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">טלפון</label>
              {isEditing ? (
                <input
                  type="tel"
                  value={editSignerPhone}
                  onChange={(e) => setEditSignerPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                  placeholder="טלפון"
                />
              ) : (
                <span className="text-gray-900">{contract.signer_phone || '—'}</span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">אימייל</label>
              {isEditing ? (
                <input
                  type="email"
                  value={editSignerEmail}
                  onChange={(e) => setEditSignerEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                  placeholder="אימייל"
                />
              ) : (
                <span className="text-gray-900">{contract.signer_email || '—'}</span>
              )}
            </div>
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

          {/* Signature Fields Section */}
          {contract.status === 'draft' && contract.files.length > 0 && (
            <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">אזורי חתימה</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {signatureFieldCount === 0 
                      ? 'לא סומנו אזורי חתימה - יש לסמן לפחות אזור אחד'
                      : `סומנו ${signatureFieldCount} אזורי חתימה במסמך`
                    }
                  </p>
                </div>
                <Button
                  onClick={() => {
                    setShowSignatureMarker(true);
                  }}
                  variant="secondary"
                  className="flex items-center gap-2"
                >
                  <Edit className="w-4 h-4" />
                  {signatureFieldCount === 0 ? 'סמן אזורי חתימה' : 'ערוך אזורים'}
                </Button>
              </div>
            </div>
          )}

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
                  <FilePreviewItem
                    key={file.id}
                    file={file}
                    contractId={contractId}
                    formatFileSize={formatFileSize}
                  />
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
        <div className="p-6 border-t border-gray-200 flex gap-3 flex-wrap">
          {isEditing ? (
            <>
              <Button onClick={handleSaveEdit} disabled={saving || !editTitle.trim()} className="flex items-center gap-2">
                <Save className="w-4 h-4" />
                {saving ? 'שומר...' : 'שמור שינויים'}
              </Button>
              <Button onClick={cancelEditing} disabled={saving} variant="secondary" className="flex items-center gap-2">
                <X className="w-4 h-4" />
                ביטול
              </Button>
            </>
          ) : (
            <>
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
            </>
          )}
        </div>
      </div>

      {/* Signature Field Marker Modal */}
      {showSignatureMarker && contract.files.length > 0 && (
        <SignatureFieldMarker
          pdfUrl={`/api/contracts/${contractId}/pdf`}
          contractId={contractId}
          onClose={() => {
            setShowSignatureMarker(false);
          }}
          onSave={handleSaveSignatureFields}
        />
      )}
    </div>
  );
}
