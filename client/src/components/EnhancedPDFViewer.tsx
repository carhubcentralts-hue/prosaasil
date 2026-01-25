import React, { useState, useRef, useEffect } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Minimize2, 
  ChevronLeft, 
  ChevronRight, 
  Minimize,
  FitWidth,
  FileText
} from 'lucide-react';
import { logger } from '../shared/utils/logger';

export interface PDFViewerProps {
  pdfUrl: string;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  showPageNav?: boolean;
  showZoom?: boolean;
  showFullscreen?: boolean;
  className?: string;
  containerRef?: React.RefObject<HTMLDivElement>;
  loading?: boolean;
  error?: string;
  children?: React.ReactNode;
}

type ZoomMode = 'fit-width' | 'fit-page' | 'custom';

export function EnhancedPDFViewer({
  pdfUrl,
  currentPage,
  totalPages,
  onPageChange,
  showPageNav = true,
  showZoom = true,
  showFullscreen = true,
  className = '',
  containerRef,
  loading = false,
  error,
  children,
}: PDFViewerProps) {
  const [zoom, setZoom] = useState(100);
  const [zoomMode, setZoomMode] = useState<ZoomMode>('fit-width');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const [showHelpTooltip, setShowHelpTooltip] = useState(false);
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [iframeError, setIframeError] = useState(false);

  // Fullscreen handling
  useEffect(() => {
    const handleEscKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };

    if (isFullscreen) {
      document.addEventListener('keydown', handleEscKey);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.removeEventListener('keydown', handleEscKey);
      document.body.style.overflow = '';
    };
  }, [isFullscreen]);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(200, prev + 25));
    setZoomMode('custom');
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(50, prev - 25));
    setZoomMode('custom');
  };

  const handleFitWidth = () => {
    setZoomMode('fit-width');
    setZoom(100);
  };

  const handleFitPage = () => {
    setZoomMode('fit-page');
    setZoom(100);
  };

  const handleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  // Build iframe src with zoom and view mode
  const getIframeSrc = () => {
    const baseUrl = `${pdfUrl}#page=${currentPage}`;
    if (zoomMode === 'fit-width') {
      return `${baseUrl}&view=FitH&zoom=${zoom}`;
    } else if (zoomMode === 'fit-page') {
      return `${baseUrl}&view=Fit&zoom=${zoom}`;
    } else {
      return `${baseUrl}&zoom=${zoom}`;
    }
  };

  // Handle iframe load events
  const handleIframeLoad = () => {
    logger.debug('PDF iframe loaded successfully');
    // Set loaded immediately to remove loading overlay
    setIframeLoaded(true);
    setIframeError(false);
  };

  const handleIframeError = () => {
    logger.error('PDF iframe failed to load');
    setIframeError(true);
    setIframeLoaded(false);
  };

  // Reset load state when URL changes
  useEffect(() => {
    // Only reset if URL actually changed (not just currentPage)
    setIframeLoaded(false);
    setIframeError(false);
  }, [pdfUrl]);

  // Toolbar component
  const Toolbar = () => (
    <div className="flex flex-wrap items-center justify-between gap-2 bg-gradient-to-r from-blue-50 to-indigo-50 p-3 rounded-lg border border-blue-200 shadow-sm">
      {/* Page Navigation */}
      {showPageNav && (
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevPage}
            disabled={currentPage === 1}
            className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="עמוד קודם"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium px-3 py-2 bg-white rounded-lg border border-blue-200 min-w-[120px] text-center">
            עמוד {currentPage} מתוך {totalPages}
          </span>
          <button
            onClick={handleNextPage}
            disabled={currentPage === totalPages}
            className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="עמוד הבא"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Zoom Controls */}
      {showZoom && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 50}
            className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="הקטן"
          >
            <ZoomOut className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium px-3 py-2 bg-white rounded-lg border border-blue-200 min-w-[80px] text-center">
            {zoom}%
          </span>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 200}
            className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="הגדל"
          >
            <ZoomIn className="w-5 h-5" />
          </button>
          <div className="w-px h-6 bg-blue-300 mx-1"></div>
          <button
            onClick={handleFitWidth}
            className={`p-2 border rounded-lg transition min-w-[44px] min-h-[44px] flex items-center justify-center ${
              zoomMode === 'fit-width'
                ? 'bg-blue-500 text-white border-blue-600'
                : 'bg-white border-blue-300 hover:bg-blue-50'
            }`}
            title="התאם לרוחב"
          >
            <Minimize2 className="w-5 h-5 rotate-90" />
          </button>
          <button
            onClick={handleFitPage}
            className={`p-2 border rounded-lg transition min-w-[44px] min-h-[44px] flex items-center justify-center ${
              zoomMode === 'fit-page'
                ? 'bg-blue-500 text-white border-blue-600'
                : 'bg-white border-blue-300 hover:bg-blue-50'
            }`}
            title="התאם לעמוד"
          >
            <Minimize className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Fullscreen Toggle */}
      {showFullscreen && (
        <button
          onClick={handleFullscreen}
          className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition min-w-[44px] min-h-[44px] flex items-center justify-center"
          title={isFullscreen ? 'צא ממסך מלא' : 'מסך מלא'}
        >
          <Maximize2 className="w-5 h-5" />
        </button>
      )}
    </div>
  );

  // PDF Container
  const PDFContainer = () => (
    <div
      ref={containerRef || viewerRef}
      className={`relative flex-1 bg-gray-100 rounded-lg overflow-hidden ${className}`}
      style={{
        minHeight: isFullscreen ? '100vh' : 'calc(100vh - 250px)',
      }}
    >
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-4 border-blue-600 mb-4"></div>
            <p className="text-gray-600 text-lg font-medium">טוען PDF...</p>
          </div>
        </div>
      ) : error ? (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="text-center max-w-md px-4">
            <FileText className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <p className="text-red-600 text-lg font-medium mb-2">שגיאה בטעינת המסמך</p>
            <p className="text-gray-600 text-sm">{error}</p>
          </div>
        </div>
      ) : pdfUrl ? (
        <>
          <iframe
            ref={iframeRef}
            key={pdfUrl}
            src={getIframeSrc()}
            className="absolute inset-0 w-full h-full"
            title="PDF Preview"
            sandbox="allow-same-origin allow-scripts allow-downloads"
            onLoad={handleIframeLoad}
            onError={handleIframeError}
            style={{ 
              border: 'none',
              transform: zoomMode === 'custom' ? `scale(${zoom / 100})` : 'none',
              transformOrigin: 'top center',
              zIndex: 1,
            }}
          />
          {/* Show loading overlay ONLY when iframe is loading AND not loaded yet - with defensive check */}
          {!iframeLoaded && !iframeError && !loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-50 bg-opacity-90 pointer-events-none" style={{ zIndex: 10 }}>
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-4 border-blue-600 mb-3"></div>
                <p className="text-gray-600 text-sm font-medium">טוען תצוגת PDF...</p>
              </div>
            </div>
          )}
          {/* Show error if iframe fails */}
          {iframeError && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-50 bg-opacity-95">
              <div className="text-center max-w-md px-4">
                <FileText className="w-12 h-12 text-orange-500 mx-auto mb-3" />
                <p className="text-orange-600 text-base font-medium mb-2">הדפדפן לא הצליח לטעון את ה-PDF</p>
                <p className="text-gray-600 text-sm mb-3">ייתכן שהדפדפן שלך לא תומך בתצוגת PDF מובנית</p>
                <a 
                  href={pdfUrl} 
                  download 
                  className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
                >
                  הורד PDF
                </a>
              </div>
            </div>
          )}
        </>
      ) : null}
      
      {/* Overlay for custom elements (signature boxes, etc.) */}
      {children}
    </div>
  );

  // Render fullscreen or normal mode
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-[9999] bg-black bg-opacity-95 flex flex-col" dir="rtl">
        <div className="p-4">
          <Toolbar />
        </div>
        <div className="flex-1 px-4 pb-4">
          <PDFContainer />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 h-full" dir="rtl">
      <Toolbar />
      <PDFContainer />
    </div>
  );
}
