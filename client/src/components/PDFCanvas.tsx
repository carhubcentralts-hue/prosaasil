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

// Set up PDF.js worker - use local copy for security
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.js/pdf.worker.min.js';

// Constants
const MIN_CONTAINER_WIDTH_FOR_RENDER = 200; // Minimum container width before rendering PDF (px)
const PDF_CANVAS_Z_INDEX = 1; // Z-index for PDF canvas layer
const PDF_OVERLAY_Z_INDEX = 2; // Z-index for overlay (signature fields, etc.)
const UI_TOOLBAR_Z_INDEX = 10; // Z-index for UI elements (toolbars, buttons)
const RENDER_TIMEOUT_MS = 10000; // Timeout for rendering to prevent stuck overlays (10 seconds)

export interface PDFCanvasProps {
  pdfUrl: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  onTotalPagesChange?: (total: number) => void;
  scale?: number;
  onScaleChange?: (scale: number) => void;
  showControls?: boolean;
  className?: string;
  containerRef?: React.RefObject<HTMLDivElement | null>;
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
  const [containerWidth, setContainerWidth] = useState(0);
  const [isRendering, setIsRendering] = useState(false);
  
  const scale = externalScale ?? internalScale;
  const handleScaleChange = onScaleChange ?? setInternalScale;
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerDivRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);
  const renderTimeoutRef = useRef<number | null>(null);

  // Load PDF document - only when URL changes
  useEffect(() => {
    if (!pdfUrl) return;

    let isCancelled = false;
    setLoading(true);
    setError(null);

    logger.debug('[PDF_CANVAS] Loading PDF from:', pdfUrl);

    // Load PDF with credentials if it's a backend URL
    // Custom cancellation is handled via isCancelled flag and loadingTask.destroy()
    const loadingTask = pdfjsLib.getDocument({
      url: pdfUrl,
      withCredentials: pdfUrl.startsWith('/api/'), // Include auth cookies for backend endpoints
    });
    
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
      // Cancel any ongoing render task
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
      // Destroy the loading task to free resources (safe to call even if still loading)
      try {
        loadingTask.destroy();
      } catch (err) {
        // Ignore errors during cleanup
        logger.debug('[PDF_CANVAS] Error destroying loading task during cleanup:', err);
      }
    };
    // Only depend on pdfUrl - onTotalPagesChange is called but not depended on
    // to avoid re-fetching when parent updates the callback
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pdfUrl]);

  // ResizeObserver to handle container size changes
  useEffect(() => {
    const container = containerRef?.current || containerDivRef.current;
    if (!container) return;

    // ✅ SET INITIAL WIDTH IMMEDIATELY (before creating observer)
    // This ensures containerWidth is set synchronously on mount
    // Only set if width meets minimum requirement to avoid triggering unnecessary renders
    const initialWidth = container.clientWidth;
    if (initialWidth >= MIN_CONTAINER_WIDTH_FOR_RENDER) {
      logger.debug('[PDF_CANVAS] Setting initial container width:', initialWidth);
      setContainerWidth(initialWidth);
    } else {
      logger.debug('[PDF_CANVAS] Container width too small, waiting for layout:', initialWidth);
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        logger.debug('[PDF_CANVAS] Container resized, width:', width);
        setContainerWidth(width);
      }
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [containerRef]);

  // Render current page
  useEffect(() => {
    if (!pdf || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    if (!context) return;

    // ✅ Get actual container width from ref (not state) to avoid timing issues
    // Use nullish coalescing (??) to prioritize ref's clientWidth unless it's null/undefined
    // If clientWidth is 0, that's a valid value (container not yet laid out)
    const container = containerRef?.current || containerDivRef.current;
    const actualWidth = container?.clientWidth ?? containerWidth;

    // Don't render if container is too small (waiting for layout)
    if (actualWidth < MIN_CONTAINER_WIDTH_FOR_RENDER) {
      logger.debug('[PDF_CANVAS] Container too small, waiting for layout. Width:', actualWidth);
      return;
    }

    // Cancel any ongoing render
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    // Clear any existing timeout
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
      renderTimeoutRef.current = null;
    }

    // 🔥 FIX: Set isRendering state BEFORE starting render
    setIsRendering(true);

    logger.debug('[PDF_CANVAS] Rendering page:', currentPage, 'scale:', scale, 'containerWidth:', actualWidth);

    // 🔥 FIX: Add timeout fallback to prevent stuck overlay (10 seconds)
    renderTimeoutRef.current = setTimeout(() => {
      logger.error('[PDF_CANVAS] Render timeout - forcing isRendering to false');
      setIsRendering(false);
      renderTaskRef.current = null;
    }, RENDER_TIMEOUT_MS);

    pdf.getPage(currentPage)
      .then((page) => {
        // 🔥 FIX: Use devicePixelRatio for sharp rendering on high-DPI displays
        const pixelRatio = window.devicePixelRatio || 1;
        const renderScale = scale * pixelRatio;
        
        const viewport = page.getViewport({ scale: renderScale });

        // 🔥 FIX: Set canvas internal size (high resolution)
        canvas.width = viewport.width;
        canvas.height = viewport.height;

        // 🔥 FIX: Set canvas CSS size (display size)
        const cssWidth = viewport.width / pixelRatio;
        const cssHeight = viewport.height / pixelRatio;
        canvas.style.width = `${cssWidth}px`;
        canvas.style.height = `${cssHeight}px`;

        logger.debug('[PDF_CANVAS] Canvas size - internal:', canvas.width, 'x', canvas.height, 'display:', cssWidth, 'x', cssHeight);

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
      })
      .catch((err: any) => {
        if (err.name === 'RenderingCancelledException') {
          logger.debug('[PDF_CANVAS] Rendering cancelled');
        } else {
          logger.error('[PDF_CANVAS] Error rendering page:', err);
        }
      })
      .finally(() => {
        // 🔥 FIX: Always clear state in finally to ensure overlay removal
        renderTaskRef.current = null;
        setIsRendering(false);
        if (renderTimeoutRef.current) {
          clearTimeout(renderTimeoutRef.current);
          renderTimeoutRef.current = null;
        }
      });

    return () => {
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
      if (renderTimeoutRef.current) {
        clearTimeout(renderTimeoutRef.current);
        renderTimeoutRef.current = null;
      }
      setIsRendering(false);
    };
  }, [pdf, currentPage, scale, containerWidth]);

  const handleZoomIn = () => {
    const newScale = Math.min(3.0, scale + 0.25);
    handleScaleChange(newScale);
  };

  const handleZoomOut = () => {
    const newScale = Math.max(0.5, scale - 0.25);
    handleScaleChange(newScale);
  };

  const handlePrevPage = () => {
    if (currentPage > 1 && !isRendering) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages && !isRendering) {
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
            disabled={currentPage === 1 || isRendering}
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
            disabled={currentPage === totalPages || isRendering}
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
          disabled={scale <= 0.5 || isRendering}
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
          disabled={scale >= 3.0 || isRendering}
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
        // 🔥 FIX: Always set minHeight to prevent height: 0 in flex layouts
        minHeight: isFullscreen ? '100vh' : '70vh',
        // Ensure proper positioning
        position: 'relative',
        width: '100%',
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
        <div className="flex items-start justify-center p-4 w-full h-full">
          <div className="relative inline-block">
            <canvas 
              ref={canvasRef}
              key={`pdf-${pdfUrl}-page-${currentPage}-scale-${Math.round(scale * 100)}`}
              className="shadow-lg bg-white block"
              style={{
                // 🔥 FIX: Ensure canvas is always displayed properly
                display: 'block',
                maxWidth: '100%',
                position: 'relative',
                zIndex: PDF_CANVAS_Z_INDEX,
              }}
            />
            {/* 🔥 FIX: Rendering overlay - show only during page render */}
            {isRendering && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-50 bg-opacity-75 pointer-events-none">
                <div className="text-center">
                  <Loader2 className="w-10 h-10 text-blue-600 animate-spin mx-auto mb-2" />
                  <p className="text-gray-600 text-sm font-medium">מרנדר עמוד...</p>
                </div>
              </div>
            )}
            {/* Overlay for custom elements (signature boxes, etc.) */}
            {children && canvasRef.current && canvasRef.current.style.width && (
              <div 
                className="absolute top-0 left-0"
                style={{
                  // Always use CSS display size, never internal canvas size
                  // Canvas internal size is high-DPI (e.g., 2000x3000), CSS size is display size (e.g., 1000x1500)
                  // Using internal size would make overlay huge and push PDF off-screen
                  width: canvasRef.current.style.width,
                  height: canvasRef.current.style.height,
                  // ✅ Transparent background prevents white box covering PDF
                  background: 'transparent',
                  // ✅ Default to pointer-events none to not block PDF, let children override
                  pointerEvents: 'none',
                  // ✅ Ensure proper z-index layering above canvas but below UI
                  zIndex: PDF_OVERLAY_Z_INDEX,
                  // ✅ Ensure overlay follows the same positioning as canvas
                  position: 'absolute',
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
