import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Upload, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';

interface SigningContract {
  id: number;
  title: string;
  signer_name?: string;
  signer_phone?: string;
  signer_email?: string;
  status: string;
  files: Array<{
    id: number;
    filename: string;
    mime_type: string;
    size_bytes: number;
    download_url: string;
  }>;
}

export function PublicSigningPage() {
  const { token } = useParams<{ token: string }>();
  const [contract, setContract] = useState<SigningContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [signing, setSigning] = useState(false);
  const [signedFile, setSignedFile] = useState<File | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (token) {
      loadContract();
    }
  }, [token]);

  const loadContract = async () => {
    if (!token) {
      setError('טוקן חסר');
      setLoading(false);
      return;
    }
    
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/contracts/sign/${token}`, {
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to load contract');
      }

      const data = await response.json();
      setContract(data);
    } catch (err: any) {
      console.error('Error loading contract:', err);
      setError(err.message || 'שגיאה בטעינת חוזה');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSignedFile(file);
      setError(null);
    }
  };

  const handleSign = async () => {
    if (!signedFile) {
      setError('יש לבחור קובץ חתום');
      return;
    }

    setSigning(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', signedFile);

      const response = await fetch(`/api/contracts/sign/${token}/complete`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to complete signing');
      }

      setSuccess(true);
    } catch (err: any) {
      console.error('Error signing contract:', err);
      setError(err.message || 'שגיאה בחתימת חוזה');
    } finally {
      setSigning(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center" dir="rtl">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">טוען חוזה...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !contract) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center" dir="rtl">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">שגיאה</h2>
            <p className="text-gray-600">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center" dir="rtl">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full mx-4">
          <div className="text-center">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">החוזה נחתם בהצלחה!</h2>
            <p className="text-gray-600 mb-6">תודה על חתימתך. החוזה עודכן במערכת.</p>
            <p className="text-sm text-gray-500">ניתן לסגור חלון זה</p>
          </div>
        </div>
      </div>
    );
  }

  if (!contract) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8 px-4" dir="rtl" style={{ fontFamily: 'Assistant, sans-serif' }}>
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-xl mb-6 p-8">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
              <FileText className="w-8 h-8 text-blue-600" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">חתימה על חוזה</h1>
            <p className="text-gray-600">{contract.title}</p>
          </div>

          {/* Signer Info */}
          {contract.signer_name && (
            <div className="bg-blue-50 rounded-lg p-4 mb-6">
              <p className="text-sm text-gray-600 mb-1">חותם:</p>
              <p className="font-semibold text-gray-900">{contract.signer_name}</p>
              {contract.signer_email && <p className="text-sm text-gray-600 mt-1">{contract.signer_email}</p>}
              {contract.signer_phone && <p className="text-sm text-gray-600">{contract.signer_phone}</p>}
            </div>
          )}

          {/* Files to Review */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">מסמכים לעיון</h2>
            {contract.files.length === 0 ? (
              <div className="text-center py-6 text-gray-500 bg-gray-50 rounded-lg">אין מסמכים זמינים</div>
            ) : (
              <div className="space-y-2">
                {contract.files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">{file.filename}</p>
                        <p className="text-xs text-gray-500">{formatFileSize(file.size_bytes)}</p>
                      </div>
                    </div>
                    <a
                      href={file.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 text-sm"
                    >
                      <Download className="w-4 h-4" />
                      הורד
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Upload Signed Document */}
          <div className="border-t border-gray-200 pt-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">העלאת מסמך חתום</h2>
            <p className="text-sm text-gray-600 mb-4">
              לאחר קריאת המסמך והחתימה עליו, אנא העלה את המסמך החתום
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">{error}</div>
            )}

            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              {!signedFile ? (
                <>
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600 mb-4">בחר קובץ חתום להעלאה</p>
                  <label className="cursor-pointer">
                    <input type="file" onChange={handleFileSelect} className="hidden" accept=".pdf,.doc,.docx" />
                    <span className="inline-block px-6 py-3 bg-blue-500 text-white rounded-md hover:bg-blue-600">
                      בחר קובץ
                    </span>
                  </label>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-center gap-2 text-gray-700">
                    <FileText className="w-5 h-5" />
                    <span className="font-medium">{signedFile.name}</span>
                    <span className="text-sm text-gray-500">({formatFileSize(signedFile.size)})</span>
                  </div>
                  <div className="flex gap-3 justify-center">
                    <Button onClick={handleSign} disabled={signing} className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4" />
                      {signing ? 'שולח...' : 'אשר וחתום'}
                    </Button>
                    <Button
                      onClick={() => setSignedFile(null)}
                      disabled={signing}
                      variant="secondary"
                    >
                      ביטול
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-sm text-gray-600">
          <p>חתימה מאובטחת • הקישור תקף ל-24 שעות</p>
        </div>
      </div>
    </div>
  );
}
