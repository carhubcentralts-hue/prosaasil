import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Upload, CheckCircle, XCircle, Eye, Edit3, X, Printer, Image, File, ChevronLeft, ChevronRight, Plus, Trash2, Move } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { SimplifiedPDFSigning } from '../../components/SimplifiedPDFSigning';

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
    file_size: number;
    download_url: string;
  }>;
}

interface SignedContractResult {
  signed_document_url?: string;
  signed_at?: string;
  signer_name?: string;
  signature_type?: string;
  signature_count?: number;
}

interface SignaturePlacement {
  id: string;
  pageNumber: number;
  x: number;
  y: number;
  width: number;
  height: number;
  signatureDataUrl: string;
}

interface PDFPageInfo {
  page_number: number;
  width: number;
  height: number;
}

// PDF Signing Component with multi-page support and signature placement
function PDFSigningView({
  file,
  token,
  signerName,
  onSigningComplete,
  onError,
}: {
  file: { id: number; filename: string; download_url: string };
  token: string;
  signerName: string;
  onSigningComplete: (result: SignedContractResult) => void;
  onError: (error: string) => void;
}) {
  const [pdfInfo, setPdfInfo] = useState<{ page_count: number; pages: PDFPageInfo[] } | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [signing, setSigning] = useState(false);
  const [signaturePlacements, setSignaturePlacements] = useState<SignaturePlacement[]>([]);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [pendingPlacement, setPendingPlacement] = useState<{ pageNumber: number; x: number; y: number } | null>(null);
  const [signatureDrawing, setSignatureDrawing] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [currentSignatureData, setCurrentSignatureData] = useState<string | null>(null);
  const pdfContainerRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [lastTapTime, setLastTapTime] = useState(0);
  const [signatureModeActive, setSignatureModeActive] = useState(false);
  const [pageBeforeSignatureMode, setPageBeforeSignatureMode] = useState(0);

  // Load PDF info
  useEffect(() => {
    const loadPdfInfo = async () => {
      try {
        const response = await fetch(`/api/contracts/sign/${token}/pdf-info/${file.id}`);
        if (response.ok) {
          const data = await response.json();
          setPdfInfo(data);
        } else {
          onError('Failed to load PDF info');
        }
      } catch (err) {
        console.error('Error loading PDF info:', err);
        onError('Failed to load PDF info');
      } finally {
        setLoading(false);
      }
    };
    loadPdfInfo();
  }, [file.id, token, onError]);

  // Initialize canvas - NO WHITE BACKGROUND for transparency
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas && showSignatureModal) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        // Clear canvas to transparent - DO NOT fill with white
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  }, [showSignatureModal]);

  // Update iframe src when page changes - with mobile fix
  useEffect(() => {
    const iframe = iframeRef.current;
    if (iframe && pdfInfo) {
      // Force complete reload on mobile to ensure page changes
      // Add timestamp to bust any caching
      const timestamp = Date.now();
      iframe.src = `${file.download_url}#page=${currentPage + 1}&t=${timestamp}`;
    }
  }, [currentPage, file.download_url, pdfInfo]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault(); // Prevent scrolling on touch
    setSignatureDrawing(true);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    // Get coordinates and scale to canvas resolution
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (clientX - rect.left) * scaleX;
    const y = (clientY - rect.top) * scaleY;
    
    // Configure drawing style for smooth, high-quality signatures
    ctx.strokeStyle = '#1a1a1a'; // Near-black for better appearance
    ctx.lineWidth = 3.5; // Thicker line for better visibility
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!signatureDrawing) return;
    e.preventDefault(); // Prevent scrolling on touch
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    // Get coordinates and scale to canvas resolution
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (clientX - rect.left) * scaleX;
    const y = (clientY - rect.top) * scaleY;
    
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setSignatureDrawing(false);
    if (canvasRef.current) {
      setCurrentSignatureData(canvasRef.current.toDataURL());
    }
  };

  const navigateToPage = (newPage: number) => {
    if (newPage >= 0 && newPage < (pdfInfo?.page_count || 0) && newPage !== currentPage) {
      if (process.env.NODE_ENV === 'development') {
        console.log(`[PDF_NAV] Navigating from page ${currentPage + 1} to page ${newPage + 1}`);
      }
      setCurrentPage(newPage);
    }
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    // Clear the canvas completely to transparent - NO WHITE BACKGROUND
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setCurrentSignatureData(null);
  };

  const handlePdfDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!pdfContainerRef.current) return;
    const rect = pdfContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Convert screen click coordinates to PDF-sized coordinates for storage
    // Note: We keep screen coordinate system (top-origin) since iframe displays PDF in screen space
    const pageInfo = pdfInfo?.pages[currentPage];
    if (!pageInfo) return;
    
    const containerWidth = rect.width;
    const containerHeight = rect.height;
    const scaleX = pageInfo.width / containerWidth;
    const scaleY = pageInfo.height / containerHeight;
    
    // Scale coordinates to match PDF dimensions while keeping top-origin coordinate system
    const pdfX = x * scaleX;
    const pdfY = y * scaleY;
    
    setPendingPlacement({ pageNumber: currentPage, x: pdfX, y: pdfY });
    setShowSignatureModal(true);
  };

  const confirmSignaturePlacement = () => {
    if (!pendingPlacement || !currentSignatureData) return;
    
    if (process.env.NODE_ENV === 'development') {
      console.log(`[PDF_SIGN] Adding signature on page ${pendingPlacement.pageNumber + 1} (0-indexed: ${pendingPlacement.pageNumber})`);
    }
    
    const newPlacement: SignaturePlacement = {
      id: `sig-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      pageNumber: pendingPlacement.pageNumber,
      x: pendingPlacement.x,
      y: pendingPlacement.y, // Use exact click position - NO offset adjustment
      width: 150,
      height: 50,
      signatureDataUrl: currentSignatureData,
    };
    
    setSignaturePlacements(prev => [...prev, newPlacement]);
    setShowSignatureModal(false);
    setPendingPlacement(null);
    clearSignature();
  };

  const removeSignature = (id: string) => {
    setSignaturePlacements(prev => prev.filter(s => s.id !== id));
  };

  const handleSubmitSignatures = async () => {
    if (signaturePlacements.length === 0) {
      onError('יש להוסיף לפחות חתימה אחת על המסמך');
      return;
    }

    if (process.env.NODE_ENV === 'development') {
      console.log('[PDF_SIGN] Submitting signatures:', signaturePlacements.map(sig => ({
        id: sig.id,
        pageNumber: sig.pageNumber,
        displayPage: sig.pageNumber + 1
      })));
    }

    setSigning(true);
    try {
      const response = await fetch(`/api/contracts/sign/${token}/embed-signature`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: file.id,
          signer_name: signerName,
          signatures: signaturePlacements.map(sig => ({
            page_number: sig.pageNumber,
            x: sig.x,
            y: sig.y,
            width: sig.width,
            height: sig.height,
            signature_data: sig.signatureDataUrl,
          })),
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
    } catch (err: any) {
      console.error('Error signing document:', err);
      onError(err.message || 'שגיאה בחתימה על המסמך');
    } finally {
      setSigning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="mr-3 text-gray-600">טוען מסמך...</span>
      </div>
    );
  }

  if (!pdfInfo) {
    return <div className="text-center py-8 text-red-600">לא ניתן לטעון את המסמך</div>;
  }

  const currentPageSignatures = signaturePlacements.filter(s => s.pageNumber === currentPage);

  return (
    <div className="space-y-4">
      {/* Header with page navigation */}
      <div className="flex items-center justify-between bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg border-2 border-blue-200 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigateToPage(Math.max(0, currentPage - 1))}
            onTouchEnd={(e) => {
              e.preventDefault();
              navigateToPage(Math.max(0, currentPage - 1));
            }}
            disabled={currentPage === 0}
            className="p-2 rounded-lg bg-white hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed active:bg-blue-200 touch-manipulation shadow-sm border border-blue-200"
            title="עמוד קודם"
          >
            <ChevronRight className="w-6 h-6 text-blue-600" />
          </button>
          <div className="px-4 py-2 bg-white rounded-lg border-2 border-blue-400 shadow-md">
            <span className="text-lg font-bold text-blue-900">
              עמוד {currentPage + 1} מתוך {pdfInfo.page_count}
            </span>
          </div>
          <button
            onClick={() => navigateToPage(Math.min(pdfInfo.page_count - 1, currentPage + 1))}
            onTouchEnd={(e) => {
              e.preventDefault();
              navigateToPage(Math.min(pdfInfo.page_count - 1, currentPage + 1));
            }}
            disabled={currentPage === pdfInfo.page_count - 1}
            className="p-2 rounded-lg bg-white hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed active:bg-blue-200 touch-manipulation shadow-sm border border-blue-200"
            title="עמוד הבא"
          >
            <ChevronLeft className="w-6 h-6 text-blue-600" />
          </button>
        </div>
        <div className="text-sm text-gray-700 bg-white px-3 py-2 rounded-lg border border-blue-200">
          <span className="font-bold text-blue-600">{signaturePlacements.length}</span> חתימות
        </div>
      </div>

      {/* Instructions */}
      <div className={`rounded-lg p-4 text-sm transition-all ${
        signatureModeActive 
          ? 'bg-green-50 border-2 border-green-400 shadow-md' 
          : 'bg-blue-50 border border-blue-200'
      }`}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className={signatureModeActive ? 'text-green-900 font-medium' : 'text-blue-800'}>
            {signatureModeActive ? (
              <div className="flex items-center gap-2">
                <span className="inline-block w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
                <span>
                  <strong>מצב חתימה פעיל!</strong> לחץ <strong>לחיצה כפולה</strong> על המסמך להוספת חתימה בעמוד {currentPage + 1}
                </span>
              </div>
            ) : (
              <span>
                <strong>הוראות:</strong> גלול וקרא את המסמך. לחץ על "הוסף חתימה" כדי להתחיל לחתום.
              </span>
            )}
          </div>
          <button
            onClick={() => {
              if (!signatureModeActive) {
                // Entering signature mode - save current page
                setPageBeforeSignatureMode(currentPage);
              } else {
                // Exiting signature mode - restore previous page
                setCurrentPage(pageBeforeSignatureMode);
              }
              setSignatureModeActive(!signatureModeActive);
            }}
            className={`px-4 py-2 md:px-6 md:py-3 rounded-lg font-bold transition-all text-sm md:text-base shadow-md hover:shadow-lg active:scale-95 touch-manipulation ${
              signatureModeActive
                ? 'bg-red-500 text-white hover:bg-red-600 ring-2 ring-red-300'
                : 'bg-green-500 text-white hover:bg-green-600 ring-2 ring-green-300'
            }`}
          >
            {signatureModeActive ? '✕ סגור מצב חתימה' : '✓ הוסף חתימה'}
          </button>
        </div>
      </div>

      {/* PDF Preview with double-click signature placement */}
      <div className="relative border-2 border-gray-300 rounded-lg bg-white">
        <div
          ref={pdfContainerRef}
          className="relative w-full"
          style={{ minHeight: '400px' }}
        >
          <iframe
            key={`pdf-page-${currentPage}`}
            ref={iframeRef}
            src={`${file.download_url}#page=${currentPage + 1}&view=FitH`}
            className="w-full min-h-[400px] h-[60vh] md:h-[70vh] max-h-[800px]"
            title={file.filename}
            style={{ 
              border: 'none',
              display: 'block',
              zIndex: 1,
              position: 'relative',
            }}
          />
          
          {/* Transparent overlay for capturing double-clicks - ONLY when signature mode is active */}
          {signatureModeActive && (
            <div
              className="absolute inset-0 cursor-crosshair transition-all"
              style={{
                backgroundColor: 'rgba(34, 197, 94, 0.08)', // Green tint for signature mode
                pointerEvents: 'auto',
                backgroundImage: 'radial-gradient(circle, rgba(34, 197, 94, 0.15) 1px, transparent 1px)',
                backgroundSize: '20px 20px',
                zIndex: 2,
              }}
              onDoubleClick={handlePdfDoubleClick}
              onTouchEnd={(e) => {
                // Handle double-tap on mobile
                const now = Date.now();
                const timeDiff = now - lastTapTime;
                
                if (timeDiff < 300 && timeDiff > 0) {
                  // Double tap detected
                  const touch = e.changedTouches[0];
                  const rect = pdfContainerRef.current?.getBoundingClientRect();
                  if (!rect) return;
                  
                  const x = touch.clientX - rect.left;
                  const y = touch.clientY - rect.top;
                  
                  // Convert screen tap coordinates to PDF-sized coordinates for storage
                  const pageInfo = pdfInfo?.pages[currentPage];
                  if (!pageInfo) return;
                  
                  const containerWidth = rect.width;
                  const containerHeight = rect.height;
                  const scaleX = pageInfo.width / containerWidth;
                  const scaleY = pageInfo.height / containerHeight;
                  
                  // Scale coordinates to match PDF dimensions while keeping top-origin coordinate system
                  const pdfX = x * scaleX;
                  const pdfY = y * scaleY;
                  
                  setPendingPlacement({ pageNumber: currentPage, x: pdfX, y: pdfY });
                  setShowSignatureModal(true);
                  
                  setLastTapTime(0); // Reset after double-tap
                } else {
                  setLastTapTime(now);
                }
              }}
              title={`לחץ לחיצה כפולה להוספת חתימה בעמוד ${currentPage + 1}`}
            >
              {/* Visual feedback for signature mode */}
              <div className="absolute top-2 right-2 bg-green-500 text-white px-3 py-1 rounded-full text-xs font-bold shadow-lg animate-pulse">
                מצב חתימה - עמוד {currentPage + 1}
              </div>
            </div>
          )}
          
          {/* Overlay for signature placements on current page */}
          <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 3 }}>
            {currentPageSignatures.map((sig) => {
              const pageInfo = pdfInfo.pages[currentPage];
              const containerWidth = pdfContainerRef.current?.offsetWidth || 800;
              const containerHeight = pdfContainerRef.current?.offsetHeight || 600;
              const scaleX = containerWidth / pageInfo.width;
              const scaleY = containerHeight / pageInfo.height;
              
              // Scale stored coordinates to current container dimensions for display
              const screenX = sig.x * scaleX;
              const screenY = sig.y * scaleY;
              const screenWidth = sig.width * scaleX;
              const screenHeight = sig.height * scaleY;
              
              return (
                <div
                  key={sig.id}
                  className="absolute pointer-events-auto"
                  style={{
                    left: screenX,
                    top: screenY,
                    width: screenWidth,
                    height: screenHeight,
                  }}
                >
                  <div className="relative w-full h-full border-2 border-blue-500 bg-blue-100 bg-opacity-30 rounded">
                    <img
                      src={sig.signatureDataUrl}
                      alt="Signature"
                      className="w-full h-full object-contain"
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSignature(sig.id);
                      }}
                      className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Signature list */}
      {signaturePlacements.length > 0 && (
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg p-4 border-2 border-green-200 shadow-md">
          <h4 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-green-500 rounded-full"></span>
            חתימות שנוספו ({signaturePlacements.length}):
          </h4>
          <div className="space-y-2">
            {signaturePlacements.map((sig, index) => (
              <div key={sig.id} className="flex items-center justify-between bg-white p-3 rounded-lg border-2 border-green-200 hover:border-green-400 transition-all shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex items-center justify-center w-8 h-8 bg-green-100 rounded-full text-green-700 font-bold text-sm">
                    {index + 1}
                  </span>
                  <div>
                    <span className="font-medium text-gray-900">חתימה {index + 1}</span>
                    <span className="text-sm text-gray-600 block">עמוד {sig.pageNumber + 1}</span>
                  </div>
                </div>
                <button
                  onClick={() => removeSignature(sig.id)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 p-2 rounded-lg transition-all active:scale-95"
                  title="הסר חתימה"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Submit button */}
      <Button
        onClick={handleSubmitSignatures}
        disabled={signing || signaturePlacements.length === 0}
        className="w-full flex items-center justify-center gap-3 text-base md:text-lg py-4 md:py-5 shadow-lg hover:shadow-xl transition-all active:scale-95 touch-manipulation"
      >
        <CheckCircle className="w-6 h-6 md:w-7 md:h-7" />
        {signing ? (
          <span>חותם על המסמך...</span>
        ) : (
          <span className="font-bold">
            {signaturePlacements.length === 0 
              ? 'הוסף חתימה כדי להמשיך' 
              : `אשר ${signaturePlacements.length} חתימות וחתום על המסמך`
            }
          </span>
        )}
      </Button>

      {/* Signature Modal */}
      {showSignatureModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-4 md:p-6 m-4" dir="rtl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg md:text-xl font-bold text-gray-900">צייר את חתימתך</h3>
                <p className="text-xs md:text-sm text-gray-600 mt-1">
                  החתימה תתווסף לעמוד {(pendingPlacement?.pageNumber ?? 0) + 1}
                </p>
              </div>
              <button 
                onClick={() => { setShowSignatureModal(false); clearSignature(); }} 
                className="p-2 hover:bg-gray-100 rounded-lg transition-all active:scale-95"
                title="סגור"
              >
                <X className="w-5 h-5 md:w-6 md:h-6" />
              </button>
            </div>
            
            <div className="border-2 border-gray-300 rounded-lg bg-white mb-4 shadow-inner">
              <div className="p-2 md:p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-300 flex justify-between items-center">
                <span className="text-sm md:text-base text-gray-700 font-medium">✍️ צייר את חתימתך כאן בעכבר או באצבע</span>
                <button 
                  onClick={clearSignature} 
                  className="text-sm text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1 md:py-2 rounded-lg transition-all flex items-center gap-1 font-medium active:scale-95"
                >
                  <X className="w-4 h-4" />
                  נקה
                </button>
              </div>
              <div className="relative p-2 md:p-4">
                <canvas
                  ref={canvasRef}
                  width={800}
                  height={300}
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={stopDrawing}
                  onMouseLeave={stopDrawing}
                  onTouchStart={startDrawing}
                  onTouchMove={draw}
                  onTouchEnd={stopDrawing}
                  className="w-full border border-gray-200 rounded cursor-crosshair touch-none bg-white signature-canvas-transparent"
                  style={{ 
                    maxWidth: '100%', 
                    height: 'auto',
                    minHeight: '200px',
                    display: 'block' 
                  }}
                />
                {!currentSignatureData && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none text-gray-400 text-sm md:text-base">
                    <span className="bg-white bg-opacity-70 px-3 py-2 rounded">התחל לצייר כדי ליצור חתימה...</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-3">
              <Button
                onClick={confirmSignaturePlacement}
                disabled={!currentSignatureData}
                className="flex-1 flex items-center justify-center gap-2 py-3 text-base font-bold touch-manipulation active:scale-95"
              >
                <Plus className="w-5 h-5" />
                הוסף חתימה
              </Button>
              <Button
                onClick={() => { setShowSignatureModal(false); clearSignature(); }}
                variant="secondary"
                className="px-6 py-3 text-base font-medium touch-manipulation active:scale-95"
              >
                ביטול
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// File Preview Component for Public Signing Page
function SigningFilePreview({ file, formatFileSize }: {
  file: {
    id: number;
    filename: string;
    mime_type: string;
    file_size: number;
    download_url: string;
  };
  formatFileSize: (bytes: number) => string;
}) {
  const [showPreview, setShowPreview] = useState(false);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState(false);

  const canPreview = file.mime_type === 'application/pdf' || 
                     file.mime_type.startsWith('image/') || 
                     file.mime_type.startsWith('text/') ||
                     file.mime_type === 'application/json';

  const isTextFile = file.mime_type.startsWith('text/') || file.mime_type === 'application/json';
  const isImage = file.mime_type.startsWith('image/');
  const isPdf = file.mime_type === 'application/pdf';

  const handlePreviewToggle = async () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }
    
    // For text files, fetch content
    if (isTextFile && !textContent) {
      setLoadingText(true);
      try {
        const response = await fetch(file.download_url);
        if (response.ok) {
          const text = await response.text();
          setTextContent(text);
        }
      } catch (err) {
        console.error('Error loading text content:', err);
      } finally {
        setLoadingText(false);
      }
    }
    
    setShowPreview(true);
  };

  const getFileIcon = () => {
    if (isImage) return <Image className="w-5 h-5 text-purple-500" />;
    if (isPdf) return <FileText className="w-5 h-5 text-red-500" />;
    if (isTextFile) return <File className="w-5 h-5 text-blue-500" />;
    return <FileText className="w-5 h-5 text-gray-400" />;
  };

  return (
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          {getFileIcon()}
          <div>
            <p className="font-medium text-gray-900">{file.filename}</p>
            <p className="text-xs text-gray-500">{formatFileSize(file.file_size)}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {canPreview && (
            <button
              onClick={handlePreviewToggle}
              disabled={loadingText}
              className="flex items-center gap-2 px-3 py-2 bg-indigo-500 text-white rounded-md hover:bg-indigo-600 text-sm disabled:opacity-50"
            >
              {loadingText ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
              {showPreview ? 'סגור תצוגה' : 'תצוגה מקדימה'}
            </button>
          )}
          <a
            href={file.download_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 text-sm"
          >
            <Download className="w-4 h-4" />
            הורד
          </a>
        </div>
      </div>
      
      {/* Preview Section */}
      {showPreview && (
        <div className="mt-4 border-2 border-gray-300 rounded-lg overflow-hidden">
          {isPdf ? (
            <iframe
              src={`${file.download_url}#view=FitH`}
              className="w-full min-h-[400px] h-[60vh] md:h-[70vh] max-h-[800px]"
              title={`Preview: ${file.filename}`}
              style={{ border: 'none', display: 'block' }}
            />
          ) : isImage ? (
            <div className="flex justify-center p-4 bg-white">
              <img 
                src={file.download_url} 
                alt={file.filename} 
                className="max-w-full max-h-[500px] rounded-lg shadow-lg"
              />
            </div>
          ) : isTextFile && textContent ? (
            <pre className="w-full h-[400px] overflow-auto p-4 bg-gray-900 text-gray-100 text-sm font-mono whitespace-pre-wrap" dir="ltr">
              {textContent}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function PublicSigningPage() {
  const { token } = useParams<{ token: string }>();
  const [contract, setContract] = useState<SigningContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [signing, setSigning] = useState(false);
  const [signedFile, setSignedFile] = useState<File | null>(null);
  const [success, setSuccess] = useState(false);
  
  // ✅ NEW: Store signed result with document URL
  const [signedResult, setSignedResult] = useState<SignedContractResult | null>(null);
  
  // ✅ PDF signing mode
  const [selectedPdfFile, setSelectedPdfFile] = useState<{ id: number; filename: string; download_url: string } | null>(null);
  const [signingMode, setSigningMode] = useState<'select' | 'pdf-sign' | 'upload'>('select');
  
  // ✅ Digital signature states (for simple signature without PDF embed)
  const [showDigitalSignature, setShowDigitalSignature] = useState(true);
  const [signerName, setSignerName] = useState('');
  const [signatureDrawing, setSignatureDrawing] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [signatureDataUrl, setSignatureDataUrl] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      loadContract();
    }
  }, [token]);

  useEffect(() => {
    if (contract?.signer_name) {
      setSignerName(contract.signer_name);
    }
  }, [contract]);

  // Initialize canvas with transparent background - NO WHITE FILL
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas && showDigitalSignature) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        // Clear to transparent - DO NOT fill with white
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  }, [showDigitalSignature]);

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

      // ✅ NEW: Capture signed result with document URL
      const result = await response.json();
      setSignedResult({
        signed_document_url: result.signed_document_url,
        signed_at: result.signed_at || new Date().toISOString(),
        signer_name: contract?.signer_name,
        signature_type: 'uploaded'
      });

      setSuccess(true);
    } catch (err: any) {
      console.error('Error signing contract:', err);
      setError(err.message || 'שגיאה בחתימת חוזה');
    } finally {
      setSigning(false);
    }
  };

  // ✅ NEW: Digital signature functions
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    setSignatureDrawing(true);
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = 'touches' in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = 'touches' in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;
    
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!signatureDrawing) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = 'touches' in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = 'touches' in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;
    
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setSignatureDrawing(false);
    if (canvasRef.current) {
      setSignatureDataUrl(canvasRef.current.toDataURL());
    }
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Clear the canvas completely to transparent - NO WHITE FILL
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setSignatureDataUrl(null);
  };

  const handleDigitalSign = async () => {
    if (!signatureDataUrl || !signerName.trim()) {
      setError('יש למלא שם ולחתום על ידי ציור חתימה');
      return;
    }

    setSigning(true);
    setError(null);

    try {
      // Convert data URL to blob
      const response = await fetch(signatureDataUrl);
      const blob = await response.blob();
      
      // Create file from blob
      const file = new File([blob], `signature_${Date.now()}.png`, { type: 'image/png' });
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('signer_name', signerName);
      formData.append('signature_type', 'digital');

      const apiResponse = await fetch(`/api/contracts/sign/${token}/complete`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!apiResponse.ok) {
        const errorData = await apiResponse.json();
        throw new Error(errorData.error || 'Failed to complete signing');
      }

      // ✅ NEW: Capture signed result with document URL
      const result = await apiResponse.json();
      setSignedResult({
        signed_document_url: result.signed_document_url,
        signed_at: result.signed_at || new Date().toISOString(),
        signer_name: signerName,
        signature_type: 'digital'
      });
      
      setSuccess(true);
    } catch (err: any) {
      console.error('Error signing contract:', err);
      setError(err.message || 'שגיאה בחתימה דיגיטלית');
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
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 py-8 px-4" dir="rtl" style={{ fontFamily: 'Assistant, sans-serif' }}>
        <div className="max-w-4xl mx-auto">
          {/* Success Header */}
          <div className="bg-white rounded-xl shadow-xl p-8 mb-6">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-4">
                <CheckCircle className="w-12 h-12 text-green-500" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">החוזה נחתם בהצלחה! 🎉</h1>
              <p className="text-lg text-gray-600 mb-2">תודה על חתימתך, {signedResult?.signer_name || contract?.signer_name || 'לקוח יקר'}.</p>
              <p className="text-gray-500">החוזה עודכן במערכת ונשלח לצדדים הרלוונטיים.</p>
              {signedResult?.signed_at && (
                <p className="text-sm text-green-600 mt-2">
                  נחתם בתאריך: {new Date(signedResult.signed_at).toLocaleString('he-IL')}
                </p>
              )}
            </div>
          </div>

          {/* Signed Contract Preview */}
          <div className="bg-white rounded-xl shadow-xl overflow-hidden mb-6">
            <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-green-50 to-emerald-50">
              <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <FileText className="w-6 h-6 text-green-600" />
                החוזה החתום
              </h2>
              <p className="text-sm text-gray-600 mt-1">{contract?.title}</p>
            </div>

            {/* Preview Section */}
            <div className="p-6">
              {signedResult?.signed_document_url ? (
                <>
                  {/* PDF Preview */}
                  <div className="border-2 border-gray-200 rounded-lg overflow-hidden mb-4">
                    <iframe
                      src={`${signedResult.signed_document_url}#view=FitH`}
                      className="w-full min-h-[400px] h-[60vh] md:h-[70vh] max-h-[800px]"
                      title="Signed Contract Preview"
                      style={{ border: 'none', display: 'block' }}
                    />
                  </div>
                  
                  {/* Download & Print Actions */}
                  <div className="flex flex-wrap gap-3 justify-center">
                    <a
                      href={signedResult.signed_document_url}
                      download={`${contract?.title || 'contract'}_signed.pdf`}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium shadow-md"
                    >
                      <Download className="w-5 h-5" />
                      הורד חוזה חתום
                    </a>
                    <button
                      onClick={() => {
                        const printWindow = window.open(signedResult.signed_document_url, '_blank');
                        printWindow?.print();
                      }}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium shadow-md"
                    >
                      <Printer className="w-5 h-5" />
                      הדפס
                    </button>
                  </div>
                </>
              ) : (
                /* Fallback if no signed document URL - show signature confirmation */
                <div className="text-center py-8">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                    <CheckCircle className="w-8 h-8 text-green-600" />
                  </div>
                  <p className="text-gray-600 mb-4">
                    החוזה נחתם והחתימה נשמרה במערכת.<br />
                    עותק של החוזה החתום ישלח אליך בהקדם.
                  </p>
                  
                  {/* Show signature if digital */}
                  {signatureDataUrl && (
                    <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200 inline-block">
                      <p className="text-sm font-medium text-gray-700 mb-2">החתימה שלך:</p>
                      <img src={signatureDataUrl} alt="Your Signature" className="max-w-[300px] h-auto border border-gray-300 rounded bg-white" />
                      <p className="text-xs text-gray-500 mt-2">{signedResult?.signer_name || signerName}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="text-center">
            <p className="text-sm text-gray-600 mb-2">
              📧 עותק מהחוזה החתום נשלח לכתובת המייל שלך
            </p>
            <p className="text-xs text-gray-500">
              שמור דף זה או הורד את החוזה לצורך תיעוד
            </p>
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

          {/* Name input for signing */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">שם החותם</label>
            <input
              type="text"
              value={signerName}
              onChange={(e) => setSignerName(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="הכנס שם מלא"
            />
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">{error}</div>
          )}

          {/* PDF Signing Mode */}
          {signingMode === 'pdf-sign' && selectedPdfFile && token ? (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">חתימה על מסמך</h2>
                <button
                  onClick={() => { setSigningMode('select'); setSelectedPdfFile(null); setError(null); }}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  ← חזור לבחירת מסמך
                </button>
              </div>
              <SimplifiedPDFSigning
                file={selectedPdfFile}
                token={token}
                signerName={signerName || contract.signer_name || 'Unknown'}
                onSigningComplete={(result) => {
                  setSignedResult(result);
                  setSuccess(true);
                }}
                onError={(err) => setError(err)}
              />
            </div>
          ) : signingMode === 'select' ? (
            <>
              {/* Files for signing */}
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">בחר מסמך לחתימה</h2>
                <p className="text-sm text-gray-600 mb-4">החתימה שלך תתווסף אוטומטית לכל האזורים המסומנים במסמך</p>
                
                {contract.files.length === 0 ? (
                  <div className="text-center py-6 text-gray-500 bg-gray-50 rounded-lg">אין מסמכים זמינים</div>
                ) : (
                  <div className="space-y-3">
                    {contract.files.map((file) => (
                      <div key={file.id} className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:border-blue-300 transition">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <FileText className={`w-6 h-6 ${file.mime_type === 'application/pdf' ? 'text-red-500' : 'text-gray-400'}`} />
                            <div>
                              <p className="font-medium text-gray-900">{file.filename}</p>
                              <p className="text-xs text-gray-500">{formatFileSize(file.file_size)}</p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <a
                              href={file.download_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 px-3 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
                            >
                              <Eye className="w-4 h-4" />
                              צפה
                            </a>
                            {file.mime_type === 'application/pdf' && (
                              <button
                                onClick={() => {
                                  if (!signerName.trim()) {
                                    setError('יש להזין שם לפני החתימה');
                                    return;
                                  }
                                  setSelectedPdfFile(file);
                                  setSigningMode('pdf-sign');
                                  setError(null);
                                }}
                                className="flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 text-sm font-medium"
                              >
                                <Edit3 className="w-4 h-4" />
                                חתום על מסמך
                              </button>
                            )}
                          </div>
                        </div>
                        {/* Preview for non-PDF files */}
                        {file.mime_type !== 'application/pdf' && (
                          <div className="mt-2">
                            <SigningFilePreview file={file} formatFileSize={formatFileSize} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Alternative: Upload signed document */}
              <div className="border-t border-gray-200 pt-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">או העלה מסמך חתום</h2>
                <button
                  onClick={() => setSigningMode('upload')}
                  className="w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-400 hover:text-blue-600 transition"
                >
                  <Upload className="w-8 h-8 mx-auto mb-2" />
                  <span>לחץ להעלאת מסמך שכבר חתום</span>
                </button>
              </div>
            </>
          ) : signingMode === 'upload' && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">העלאת מסמך חתום</h2>
                <button
                  onClick={() => { setSigningMode('select'); setSignedFile(null); }}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  ← חזור לבחירת מסמך
                </button>
              </div>
              
              <p className="text-sm text-gray-600 mb-4">
                לאחר קריאת המסמך והחתימה עליו, אנא העלה את המסמך החתום
              </p>

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
          )}
        </div>

        {/* Footer */}
        <div className="text-center text-sm text-gray-600">
          <p>חתימה מאובטחת • הקישור תקף ל-24 שעות</p>
        </div>
      </div>
    </div>
  );
}
