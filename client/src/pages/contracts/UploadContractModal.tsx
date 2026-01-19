import React, { useState } from 'react';
import { X, FileText, Upload, User, Phone, Mail, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';

interface UploadContractModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadContractModal({ onClose, onSuccess }: UploadContractModalProps) {
  const [formData, setFormData] = useState({
    title: '',
    lead_id: '',
    customer_id: '',
    signer_name: '',
    signer_phone: '',
    signer_email: '',
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const timeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ];
      
      if (!validTypes.includes(file.type)) {
        setError('סוג קובץ לא נתמך. אנא העלה PDF או DOCX');
        return;
      }

      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError('גודל הקובץ חורג מ-10MB');
        return;
      }

      setSelectedFile(file);
      setError(null);
      
      // Auto-populate title from filename if empty
      if (!formData.title) {
        const filename = file.name.replace(/\.[^/.]+$/, ''); // Remove extension
        setFormData({ ...formData, title: filename });
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.title.trim()) {
      setError('כותרת חובה');
      return;
    }

    if (!selectedFile) {
      setError('יש לבחור קובץ להעלאה');
      return;
    }

    setLoading(true);

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('file', selectedFile);
      formDataToSend.append('title', formData.title.trim());

      if (formData.lead_id) formDataToSend.append('lead_id', formData.lead_id);
      if (formData.customer_id) formDataToSend.append('customer_id', formData.customer_id);
      if (formData.signer_name) formDataToSend.append('signer_name', formData.signer_name.trim());
      if (formData.signer_phone) formDataToSend.append('signer_phone', formData.signer_phone.trim());
      if (formData.signer_email) formDataToSend.append('signer_email', formData.signer_email.trim());

      const response = await fetch('/api/contracts/upload', {
        method: 'POST',
        credentials: 'include',
        body: formDataToSend,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to upload contract');
      }

      const result = await response.json();
      console.log('Contract created:', result);
      
      // Show success message
      setSuccess(true);
      setError(null);
      
      // Close modal and refresh list after a short delay to show success message
      timeoutRef.current = setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err: any) {
      console.error('Error uploading contract:', err);
      setError(err.message || 'שגיאה בהעלאת חוזה');
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 md:p-6 border-b border-gray-200 sticky top-0 bg-white">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Upload className="w-4 h-4 md:w-5 md:h-5 text-blue-600" />
            </div>
            <h2 className="text-lg md:text-xl font-bold text-gray-900">העלאת חוזה</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
            disabled={loading}
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-4 md:p-6 space-y-4 md:space-y-6">
          {success && (
            <div 
              className="p-4 bg-green-50 border border-green-200 rounded-md flex items-start gap-3"
              role="alert"
              aria-live="polite"
            >
              <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-green-800 font-medium">החוזה הועלה בהצלחה!</p>
                <p className="text-green-700 text-sm mt-1">הדף יתרענן בעוד רגע...</p>
              </div>
            </div>
          )}
          
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <span className="text-red-700 text-sm">{error}</span>
            </div>
          )}

          {/* File Upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              קובץ חוזה <span className="text-red-500">*</span>
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-400 transition">
              <div className="text-center">
                {!selectedFile ? (
                  <>
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 mb-2">לחץ לבחירת קובץ PDF או DOCX</p>
                    <p className="text-xs text-gray-500 mb-3">גודל מקסימלי: 10MB</p>
                    <input
                      type="file"
                      onChange={handleFileSelect}
                      className="hidden"
                      id="contract-file-upload"
                      accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    />
                    <label
                      htmlFor="contract-file-upload"
                      className="inline-block px-4 py-2 bg-blue-500 text-white rounded-md cursor-pointer hover:bg-blue-600 transition"
                    >
                      בחר קובץ
                    </label>
                  </>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-center gap-3 text-gray-700">
                      <FileText className="w-8 h-8 text-blue-600" />
                      <div className="text-right">
                        <p className="font-medium">{selectedFile.name}</p>
                        <p className="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        const input = document.getElementById('contract-file-upload') as HTMLInputElement;
                        if (input) input.value = '';
                      }}
                      className="text-sm text-red-600 hover:text-red-700"
                    >
                      הסר קובץ
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Contract Details */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-900">פרטי חוזה</h3>
            
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                כותרת <span className="text-red-500">*</span>
              </label>
              <Input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="למשל: חוזה שירות - ינואר 2024"
                disabled={loading}
              />
            </div>

            {/* Lead ID (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                מזהה ליד (אופציונלי)
              </label>
              <Input
                type="number"
                value={formData.lead_id}
                onChange={(e) => setFormData({ ...formData, lead_id: e.target.value })}
                placeholder="למשל: 123"
                disabled={loading}
              />
            </div>
          </div>

          {/* Signer Details */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-900">פרטי חותם (אופציונלי)</h3>
            
            {/* Signer Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <User className="w-4 h-4 inline ml-1" />
                שם מלא
              </label>
              <Input
                type="text"
                value={formData.signer_name}
                onChange={(e) => setFormData({ ...formData, signer_name: e.target.value })}
                placeholder="שם החותם"
                disabled={loading}
              />
            </div>

            {/* Signer Phone */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Phone className="w-4 h-4 inline ml-1" />
                טלפון
              </label>
              <Input
                type="tel"
                value={formData.signer_phone}
                onChange={(e) => setFormData({ ...formData, signer_phone: e.target.value })}
                placeholder="050-1234567"
                disabled={loading}
              />
            </div>

            {/* Signer Email */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Mail className="w-4 h-4 inline ml-1" />
                אימייל
              </label>
              <Input
                type="email"
                value={formData.signer_email}
                onChange={(e) => setFormData({ ...formData, signer_email: e.target.value })}
                placeholder="email@example.com"
                disabled={loading}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t">
            <Button
              type="submit"
              disabled={loading || !selectedFile || !formData.title.trim()}
              className="flex-1 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  מעלה...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  העלה חוזה
                </>
              )}
            </Button>
            <Button
              type="button"
              onClick={onClose}
              disabled={loading}
              variant="outline"
              className="px-6"
            >
              ביטול
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
