import React, { useState, useRef, useEffect } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  ChevronLeft, 
  ChevronRight,
  FileText,
  Loader2
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import { logger } from '../shared/utils/logger';

// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

export interface PDFCanvasProps {
  pdfUrl: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  onTotalPagesChange?: (total: number) => void;
  scale?: number;
  onScaleChange?: (scale: number) => void;
  showControls?: boolean;
  className?: string;
  containerRef?: React.RefObject<HTMLDivElement>;
  children?: React.ReactNode;
}

export function PDFCanvas({
  pdfUrl,
  currentPage,
  onPageChange,
  onTotalPagesChange,
  scale: externalScale,
  onScaleChange,
  showControls = true,
  className = '',
  containerRef,
  children,
}: PDFCanvasProps) {
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [internalScale, setInternalScale] = useState(1.0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  const scale = externalScale ?? internalScale;
  const handleScaleChange = onScaleChange ?? setInternalScale;
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerDivRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);

  // Load PDF document
  useEffect(() => {
    if (!pdfUrl) return;

    let isCancelled = false;
    setLoading(true);
    setError(null);

    logger.debug('[PDF_CANVAS] Loading PDF from:', pdfUrl);

    const loadingTask = pdfjsLib.getDocument(pdfUrl);
    
    loadingTask.promise
      .then((loadedPdf) => {
        if (isCancelled) return;
        
        setPdf(loadedPdf);
        setTotalPages(loadedPdf.numPages);
        if (onTotalPagesChange) {
          onTotalPagesChange(loadedPdf.numPages);
        }
        setLoading(false);
        logger.debug('[PDF_CANVAS] PDF loaded successfully, pages:', loadedPdf.numPages);
      })
      .catch((err) => {
        if (isCancelled) return;
        
        logger.error('[PDF_CANVAS] Error loading PDF:', err);
        setError('שגיאה בטעינת PDF');
        setLoading(false);
      });

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [pdfUrl, onTotalPagesChange]);

  // Render current page
  useEffect(() => {
    if (!pdf || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    if (!context) return;

    // Cancel any ongoing render
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
    }

    logger.debug('[PDF_CANVAS] Rendering page:', currentPage, 'scale:', scale);

    pdf.getPage(currentPage)
      .then((page) => {
        const viewport = page.getViewport({ scale });

        // Set canvas dimensions
        canvas.width = viewport.width;
        canvas.height = viewport.height;

        // Render PDF page into canvas
        const renderContext = {
          canvasContext: context,
          viewport: viewport,
        };

        const renderTask = page.render(renderContext);
        renderTaskRef.current = renderTask;

        return renderTask.promise;
      })
      .then(() => {
        logger.debug('[PDF_CANVAS] Page rendered successfully');
        renderTaskRef.current = null;
      })
      .catch((err: any) => {
        if (err.name === 'RenderingCancelledException') {
          logger.debug('[PDF_CANVAS] Rendering cancelled');
        } else {
          logger.error('[PDF_CANVAS] Error rendering page:', err);
        }
      });

    return () => {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [pdf, currentPage, scale]);

  const handleZoomIn = () => {
    const newScale = Math.min(3.0, scale + 0.25);
    handleScaleChange(newScale);
  };

  const handleZoomOut = () => {
    const newScale = Math.max(0.5, scale - 0.25);
    handleScaleChange(newScale);
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

  const handleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

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

  const Toolbar = () => (
    <div className="flex flex-wrap items-center justify-between gap-2 bg-gradient-to-r from-blue-50 to-indigo-50 p-3 rounded-lg border border-blue-200 shadow-sm">
      {/* Page Navigation */}
      {totalPages > 0 && (
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
      <div className="flex items-center gap-2">
        <button
          onClick={handleZoomOut}
          disabled={scale <= 0.5}
          className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="הקטן"
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <span className="text-sm font-medium px-3 py-2 bg-white rounded-lg border border-blue-200 min-w-[80px] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          disabled={scale >= 3.0}
          className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="הגדל"
        >
          <ZoomIn className="w-5 h-5" />
        </button>
      </div>

      {/* Fullscreen Toggle */}
      <button
        onClick={handleFullscreen}
        className="p-2 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition min-w-[44px] min-h-[44px] flex items-center justify-center"
        title={isFullscreen ? 'צא ממסך מלא' : 'מסך מלא'}
      >
        <Maximize2 className="w-5 h-5" />
      </button>
    </div>
  );

  const PDFContainer = () => (
    <div
      ref={containerRef || containerDivRef}
      className={`relative flex-1 bg-gray-100 rounded-lg overflow-auto ${className}`}
      style={{
        minHeight: isFullscreen ? '100vh' : 'calc(100vh - 250px)',
      }}
    >
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
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
      ) : (
        <div className="flex items-start justify-center p-4 min-h-full">
          <div className="relative">
            <canvas 
              ref={canvasRef} 
              className="shadow-lg bg-white"
            />
            {/* Overlay for custom elements (signature boxes, etc.) */}
            {children && (
              <div 
                className="absolute inset-0 pointer-events-none"
                style={{
                  width: canvasRef.current?.width || 0,
                  height: canvasRef.current?.height || 0,
                }}
              >
                {children}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  // Render fullscreen or normal mode
  if (isFullscreen) {
    return (
      <div className="fixed inset-0 z-[9999] bg-black bg-opacity-95 flex flex-col" dir="rtl">
        <div className="p-4">
          {showControls && <Toolbar />}
        </div>
        <div className="flex-1 px-4 pb-4">
          <PDFContainer />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 h-full" dir="rtl">
      {showControls && <Toolbar />}
      <PDFContainer />
    </div>
  );
}
