import React, { useState, useRef, useEffect } from 'react';
import { CheckCircle, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../shared/components/ui/Button';
import { logger } from '../shared/utils/logger';
import { PDFCanvas } from './PDFCanvas';

// Constants
const MIN_CONTAINER_WIDTH = 200; // Minimum container width for PDF rendering
const ERROR_LOADING_PDF_INFO = 'שגיאה בטעינת מידע על PDF';

interface SignatureField {
  id: string;
  page: number; // 1-based
  x: number; // 0-1 relative
  y: number; // 0-1 relative
  w: number; // 0-1 relative
  h: number; // 0-1 relative
  required: boolean;
}

interface SignedContractResult {
  signed_document_url?: string;
  signed_at?: string;
  signer_name?: string;
  signature_type?: string;
  signature_count?: number;
}

interface SimplifiedPDFSigningProps {
  file: { id: number; filename: string; download_url: string };
  token: string;
  signerName: string;
  onSigningComplete: (result: SignedContractResult) => void;
  onError: (error: string) => void;
}

export function SimplifiedPDFSigning({ file, token, signerName, onSigningComplete, onError }: SimplifiedPDFSigningProps) {
  const [signatureFields, setSignatureFields] = useState<SignatureField[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);
  const [signatureData, setSignatureData] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [scale, setScale] = useState(1.0);
  const [error, setError] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pdfContainerRef = useRef<HTMLDivElement>(null);

  // Load signature fields and PDF info
  useEffect(() => {
    loadSignatureFields();
    loadPdfInfo();
  }, [token, file.id]);
  
  const loadSignatureFields = async () => {
    try {
      const response = await fetch(`/api/contracts/sign/${token}/signature-fields`);
      if (response.ok) {
        const data = await response.json();
        setSignatureFields(data.fields || []);
      }
    } catch (err) {
      console.error('Error loading signature fields:', err);
    }
  };

  const loadPdfInfo = async () => {
    try {
      console.log('[PDF_LOAD_START] Loading PDF info for file:', file.id);
      const response = await fetch(`/api/contracts/sign/${token}/pdf-info/${file.id}`);
      if (response.ok) {
        const data = await response.json();
        setTotalPages(data.page_count || 1);
        console.log('[PDF_LOAD_SUCCESS] PDF info loaded, pages:', data.page_count);
      } else {
        console.error('[PDF_LOAD_ERROR] Failed to load PDF info:', response.status);
        setError(ERROR_LOADING_PDF_INFO);
      }
    } catch (err) {
      console.error('[PDF_LOAD_ERROR] Error loading PDF info:', err);
      setError(ERROR_LOADING_PDF_INFO);
    } finally {
      setLoading(false);
    }
  };

  // Initialize canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  }, []);

  const startDrawing = (e: React.PointerEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const draw = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
    if (canvasRef.current) {
      setSignatureData(canvasRef.current.toDataURL());
    }
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setSignatureData(null);
  };

  const handleSubmit = async () => {
    if (!signatureData) {
      onError('יש לצייר חתימה לפני השליחה');
      return;
    }

    setSigning(true);
    try {
      const response = await fetch(`/api/contracts/sign/${token}/embed-signature`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: file.id,
          signature_data: signatureData,
          signer_name: signerName,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to sign document');
      }

      const result = await response.json();
      onSigningComplete({
        signed_document_url: result.signed_document_url,
        signed_at: result.signed_at,
        signer_name: result.signer_name,
        signature_type: 'embedded',
        signature_count: result.signature_count,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'שגיאה בחתימה על המסמך';
      console.error('Error signing document:', err);
      onError(errorMessage);
    } finally {
      setSigning(false);
    }
  };

  const navigateToPage = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages && newPage !== currentPage) {
      setCurrentPage(newPage);
    }
  };

  const getCurrentPageFields = () => {
    return signatureFields.filter(f => f.page === currentPage);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
          <p className="text-gray-600">טוען מסמך...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-red-600 font-medium mb-2">שגיאה בטעינת PDF</p>
          <p className="text-gray-600 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  // Don't allow signing if no signature data or no signature fields
  const canSign = signatureData && signatureFields.length > 0;

  return (
    <div className="space-y-4">
      {/* Signature Creation Area */}
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg p-4 border-2 border-purple-200">
        <h3 className="font-bold text-gray-900 mb-2">צור את החתימה שלך</h3>
        <p className="text-sm text-gray-700 mb-4">
          החתימה שלך תתווסף אוטומטית לכל המקומות המסומנים בחוזה 
          ({signatureFields.length} {signatureFields.length === 1 ? 'מקום' : 'מקומות'})
        </p>
        
        <div className="border-2 border-gray-300 rounded-lg bg-white overflow-hidden">
          <div className="p-2 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-300 flex justify-between items-center">
            <span className="text-sm text-gray-700 font-medium">צייר את חתימתך כאן</span>
            <button 
              onClick={clearSignature} 
              className="text-sm text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1 rounded-lg transition-all flex items-center gap-1 font-medium"
            >
              <X className="w-4 h-4" />
              נקה
            </button>
          </div>
          <canvas
            ref={canvasRef}
            width={600}
            height={150}
            onPointerDown={startDrawing}
            onPointerMove={draw}
            onPointerUp={stopDrawing}
            onPointerLeave={stopDrawing}
            className="w-full cursor-crosshair"
            style={{ maxWidth: '100%', height: '150px', display: 'block', touchAction: 'none' }}
          />
        </div>
      </div>

      {/* PDF Preview with Signature Field Overlay */}
      <div className="space-y-3">
        {/* Page Navigation */}
        <div className="flex items-center justify-between bg-blue-50 p-3 rounded-lg border border-blue-200">
          <button
            onClick={() => navigateToPage(currentPage - 1)}
            disabled={currentPage === 1 || loading}
            className="p-2 rounded-lg bg-white hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed border border-blue-200"
          >
            <ChevronRight className="w-5 h-5 text-blue-600" />
          </button>
          <span className="text-sm font-medium">
            עמוד {currentPage} מתוך {totalPages}
          </span>
          <button
            onClick={() => navigateToPage(currentPage + 1)}
            disabled={currentPage === totalPages || loading}
            className="p-2 rounded-lg bg-white hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed border border-blue-200"
          >
            <ChevronLeft className="w-5 h-5 text-blue-600" />
          </button>
        </div>

        {/* PDF with Signature Field Overlays */}
        <div className="space-y-3">
          {!file.download_url ? (
            <div className="w-full min-h-[400px] flex items-center justify-center bg-gray-50 rounded-lg border-2 border-gray-300">
              <p className="text-red-600">לא נמצא URL של PDF</p>
            </div>
          ) : (
            <PDFCanvas
              pdfUrl={file.download_url}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
              onTotalPagesChange={setTotalPages}
              scale={scale}
              onScaleChange={setScale}
              showControls={false}
              className="min-h-[400px]"
              containerRef={pdfContainerRef}
            >
              {/* Overlay showing where signatures will be placed */}
              <div className="absolute inset-0 pointer-events-none" style={{ background: 'transparent' }}>
                {getCurrentPageFields().map((field, index) => (
                  <div
                    key={field.id}
                    className="absolute border-2 border-dashed border-purple-500 bg-purple-100 bg-opacity-30 flex items-center justify-center"
                    style={{
                      left: `${field.x * 100}%`,
                      top: `${field.y * 100}%`,
                      width: `${field.w * 100}%`,
                      height: `${field.h * 100}%`,
                    }}
                  >
                    <div className="bg-purple-600 text-white text-xs px-2 py-1 rounded">
                      חתימה {signatureFields.indexOf(field) + 1}
                    </div>
                  </div>
                ))}
              </div>
            </PDFCanvas>
          )}
        </div>

        {/* Info about signature fields */}
        {signatureFields.length > 0 && (
          <div className="bg-green-50 rounded-lg p-3 border border-green-200">
            <p className="text-sm text-green-800">
              <strong>✓</strong> המסמך מכיל {signatureFields.length} אזורי חתימה מסומנים.
              החתימה שלך תוצב אוטומטית בכל המקומות המסומנים.
            </p>
          </div>
        )}
        
        {signatureFields.length === 0 && (
          <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200">
            <p className="text-sm text-yellow-800">
              <strong>⚠</strong> לא נמצאו אזורי חתימה מוגדרים במסמך. פנה לשולח המסמך.
            </p>
          </div>
        )}
      </div>

      {/* Submit Button with Progress Indicator */}
      <div className="space-y-3">
        {signing && (
          <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
            <div className="flex items-center gap-3">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <div className="flex-1">
                <p className="text-blue-900 font-medium">מטביע חתימה במסמך...</p>
                <p className="text-blue-700 text-sm mt-1">
                  מטביע את החתימה ב-{signatureFields.length} מקומות במסמך
                </p>
              </div>
            </div>
          </div>
        )}
        
        <Button
          onClick={handleSubmit}
          disabled={signing || !canSign}
          className="w-full flex items-center justify-center gap-3 text-lg py-4 shadow-lg"
        >
          <CheckCircle className="w-6 h-6" />
          {signing ? (
            'חותם על המסמך...'
          ) : !signatureData ? (
            'יש לצייר חתימה תחילה'
          ) : signatureFields.length === 0 ? (
            'לא נמצאו אזורי חתימה'
          ) : (
            `חתום על המסמך (${signatureFields.length} ${signatureFields.length === 1 ? 'חתימה' : 'חתימות'})`
          )}
        </Button>
      </div>
    </div>
  );
}
