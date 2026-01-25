import React, { useState, useRef, useEffect } from 'react';
import { X, Save, Trash2, Eye, Edit3 } from 'lucide-react';
import { Button } from '../shared/components/ui/Button';
import { PDFCanvas } from './PDFCanvas';
import { logger } from '../shared/utils/logger';
import * as pdfjsLib from 'pdfjs-dist';

export interface SignatureField {
  id: string;
  page: number; // 1-based
  x: number; // PDF units (not pixels) - relative to page width
  y: number; // PDF units (not pixels) - relative to page height
  w: number; // PDF units - relative to page width
  h: number; // PDF units - relative to page height
  required: boolean;
}

// Constants
const MIN_FIELD_SIZE = 0.05; // Minimum 5% width/height for signature fields
const FIELD_Z_INDEX_NORMAL = 5; // Z-index for normal signature fields
const FIELD_Z_INDEX_SELECTED = 10; // Z-index for selected signature field

interface SignatureFieldMarkerProps {
  contractId: number;
  onClose: () => void;
  onSave: (fields: SignatureField[]) => Promise<void>;
}

export function SignatureFieldMarker({ contractId, onClose, onSave }: SignatureFieldMarkerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [fields, setFields] = useState<SignatureField[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signatureMarkingMode, setSignatureMarkingMode] = useState(false);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number; fieldX: number; fieldY: number; fieldW: number; fieldH: number } | null>(null);
  const [showHelpTooltip, setShowHelpTooltip] = useState(false);
  const [scale, setScale] = useState(1.0);
  // Remove duplicate PDF loading - PDFCanvas will handle it
  const [pageViewport, setPageViewport] = useState<pdfjsLib.PageViewport | null>(null);
  
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  // Get viewport for current page - compute from rendered canvas
  useEffect(() => {
    // Use a timeout to allow canvas to render first
    const timer = setTimeout(() => {
      const container = canvasContainerRef.current;
      if (!container) return;

      // Find the canvas element rendered by PDFCanvas
      const canvas = container.querySelector('canvas') as HTMLCanvasElement;
      if (!canvas) return;

      // Get the CSS display size of the canvas
      const cssWidth = parseFloat(canvas.style.width) || canvas.offsetWidth;
      const cssHeight = parseFloat(canvas.style.height) || canvas.offsetHeight;

      if (cssWidth > 0 && cssHeight > 0) {
        // Create a mock viewport with the actual display dimensions
        setPageViewport({
          width: cssWidth,
          height: cssHeight,
        } as pdfjsLib.PageViewport);
        
        logger.debug('[SignatureFieldMarker] Viewport updated from canvas:', cssWidth, 'x', cssHeight);
      }
    }, 100); // Small delay to let PDFCanvas render

    return () => clearTimeout(timer);
  }, [currentPage, scale]); // Re-calculate when page or scale changes

  // Load existing signature fields
  useEffect(() => {
    loadSignatureFields();
  }, [contractId]);

  const loadSignatureFields = async () => {
    try {
      const response = await fetch(`/api/contracts/${contractId}/signature-fields`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setFields(data.fields || []);
      }
    } catch (err) {
      logger.error('Error loading signature fields:', err);
    }
  };

  const handleSave = async () => {
    if (fields.length === 0) {
      setError('יש להוסיף לפחות שדה חתימה אחד');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onSave(fields);
      onClose();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'שגיאה בשמירת שדות החתימה';
      setError(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement> | React.PointerEvent<HTMLDivElement>) => {
    if (!canvasContainerRef.current || !signatureMarkingMode || !pageViewport) return;
    
    const rect = canvasContainerRef.current.getBoundingClientRect();
    
    // Get click position in pixels relative to canvas (PointerEvent has clientX/clientY)
    const clientX = e.clientX;
    const clientY = e.clientY;
    const clickX = clientX - rect.left;
    const clickY = clientY - rect.top;
    
    // Convert to PDF units (0-1 relative to page dimensions)
    const pdfX = clickX / pageViewport.width;
    const pdfY = clickY / pageViewport.height;

    // Check if clicking on existing field
    const clickedField = fields.find(f => 
      f.page === currentPage &&
      pdfX >= f.x && pdfX <= f.x + f.w &&
      pdfY >= f.y && pdfY <= f.y + f.h
    );

    if (clickedField) {
      setSelectedFieldId(clickedField.id);
      return;
    }

    // Create new signature field at click location
    const newField: SignatureField = {
      id: crypto.randomUUID ? crypto.randomUUID() : `field-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`,
      page: currentPage,
      x: Math.max(0, Math.min(1 - 0.15, pdfX - 0.075)), // Center the box on click
      y: Math.max(0, Math.min(1 - 0.08, pdfY - 0.04)),
      w: 0.15, // Default width 15%
      h: 0.08, // Default height 8%
      required: true,
    };
    
    setFields(prev => [...prev, newField]);
    setSelectedFieldId(newField.id);
    
    // Show help tooltip first time
    if (fields.length === 0) {
      setShowHelpTooltip(true);
      setTimeout(() => setShowHelpTooltip(false), 5000);
    }
  };

  const handleFieldMouseDown = (e: React.MouseEvent | React.PointerEvent, field: SignatureField, handle?: string) => {
    e.stopPropagation();
    if (!canvasContainerRef.current || !pageViewport) return;
    
    const rect = canvasContainerRef.current.getBoundingClientRect();
    // PointerEvent has clientX/clientY directly, no need to check touches
    const clientX = e.clientX;
    const clientY = e.clientY;
    const x = (clientX - rect.left) / pageViewport.width;
    const y = (clientY - rect.top) / pageViewport.height;
    
    if (handle) {
      setIsResizing(handle);
    } else {
      setIsDragging(true);
    }
    
    setDragStart({
      x,
      y,
      fieldX: field.x,
      fieldY: field.y,
      fieldW: field.w,
      fieldH: field.h,
    });
    setSelectedFieldId(field.id);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement> | React.PointerEvent<HTMLDivElement>) => {
    if (!canvasContainerRef.current || !dragStart || !selectedFieldId || !pageViewport) return;
    
    const rect = canvasContainerRef.current.getBoundingClientRect();
    // PointerEvent has clientX/clientY directly
    const clientX = e.clientX;
    const clientY = e.clientY;
    const x = (clientX - rect.left) / pageViewport.width;
    const y = (clientY - rect.top) / pageViewport.height;
    
    const dx = x - dragStart.x;
    const dy = y - dragStart.y;
    
    setFields(prev => prev.map(f => {
      if (f.id !== selectedFieldId) return f;
      
      if (isDragging) {
        // Move the field
        return {
          ...f,
          x: Math.max(0, Math.min(1 - f.w, dragStart.fieldX + dx)),
          y: Math.max(0, Math.min(1 - f.h, dragStart.fieldY + dy)),
        };
      } else if (isResizing) {
        // Resize the field based on handle
        let newX = dragStart.fieldX;
        let newY = dragStart.fieldY;
        let newW = dragStart.fieldW;
        let newH = dragStart.fieldH;
        
        if (isResizing.includes('r')) {
          newW = Math.max(MIN_FIELD_SIZE, Math.min(1 - dragStart.fieldX, dragStart.fieldW + dx));
        } else if (isResizing.includes('l')) {
          newX = Math.max(0, Math.min(dragStart.fieldX + dragStart.fieldW - MIN_FIELD_SIZE, dragStart.fieldX + dx));
          newW = dragStart.fieldW + (dragStart.fieldX - newX);
        }
        
        if (isResizing.includes('t')) {
          newY = Math.max(0, Math.min(dragStart.fieldY + dragStart.fieldH - MIN_FIELD_SIZE, dragStart.fieldY + dy));
          newH = dragStart.fieldH + (dragStart.fieldY - newY);
        } else if (isResizing.includes('b')) {
          newH = Math.max(MIN_FIELD_SIZE, Math.min(1 - dragStart.fieldY, dragStart.fieldH + dy));
        }
        
        return {
          ...f,
          x: newX,
          y: newY,
          w: newW,
          h: newH,
        };
      }
      
      return f;
    }));
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setIsResizing(null);
    setDragStart(null);
  };

  const deleteField = (fieldId: string) => {
    setFields(prev => prev.filter(f => f.id !== fieldId));
    if (selectedFieldId === fieldId) {
      setSelectedFieldId(null);
    }
  };

  const clearAllFields = () => {
    if (confirm('האם אתה בטוח שברצונך למחוק את כל שדות החתימה?')) {
      setFields([]);
      setSelectedFieldId(null);
    }
  };

  const focusOnField = (fieldId: string) => {
    const field = fields.find(f => f.id === fieldId);
    if (field) {
      setCurrentPage(field.page);
      setSelectedFieldId(fieldId);
    }
  };

  const getCurrentPageFields = () => {
    return fields.filter(f => f.page === currentPage);
  };

  // Render signature field overlay
  const renderSignatureFields = () => {
    if (!pageViewport) return null;

    // Create a map of field IDs to their global index for efficient lookup
    const fieldIndexMap = new Map(fields.map((f, i) => [f.id, i + 1]));

    return getCurrentPageFields().map((field) => {
      // Convert PDF units to pixels
      const left = field.x * pageViewport.width;
      const top = field.y * pageViewport.height;
      const width = field.w * pageViewport.width;
      const height = field.h * pageViewport.height;
      
      const fieldNumber = fieldIndexMap.get(field.id) || 1;

      return (
        <div
          key={field.id}
          className={`absolute border-3 transition-all ${
            selectedFieldId === field.id
              ? 'border-blue-600 bg-blue-200 shadow-xl'
              : 'border-green-600 bg-green-200 hover:border-green-700'
          } bg-opacity-40 cursor-move`}
          style={{
            left: `${left}px`,
            top: `${top}px`,
            width: `${width}px`,
            height: `${height}px`,
            // 🔥 FIX: Ensure fields receive pointer events
            pointerEvents: 'auto',
            zIndex: selectedFieldId === field.id ? FIELD_Z_INDEX_SELECTED : FIELD_Z_INDEX_NORMAL,
          }}
          onMouseDown={(e) => handleFieldMouseDown(e, field)}
          onPointerDown={(e) => handleFieldMouseDown(e, field)}
        >
          {/* Field Label */}
          <div className="absolute -top-7 right-0 bg-gradient-to-r from-green-600 to-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-t-lg shadow-md whitespace-nowrap">
            חתימה #{fieldNumber}
          </div>
          
          {/* Delete Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              deleteField(field.id);
            }}
            className="absolute -top-2 -left-2 bg-red-600 text-white rounded-full p-1.5 hover:bg-red-700 shadow-lg z-20 min-w-[28px] min-h-[28px] flex items-center justify-center"
            title="מחק שדה"
          >
            <X className="w-4 h-4" />
          </button>

          {/* Resize Handles - Only show when selected */}
          {selectedFieldId === field.id && (
            <>
              <div 
                className="absolute -top-2 -right-2 w-4 h-4 bg-blue-600 border-2 border-white rounded-full cursor-nw-resize shadow-md z-20" 
                onMouseDown={(e) => handleFieldMouseDown(e, field, 'tr')}
                onPointerDown={(e) => handleFieldMouseDown(e, field, 'tr')}
              />
              <div 
                className="absolute -top-2 -left-2 w-4 h-4 bg-blue-600 border-2 border-white rounded-full cursor-ne-resize shadow-md z-20" 
                onMouseDown={(e) => handleFieldMouseDown(e, field, 'tl')}
                onPointerDown={(e) => handleFieldMouseDown(e, field, 'tl')}
              />
              <div 
                className="absolute -bottom-2 -right-2 w-4 h-4 bg-blue-600 border-2 border-white rounded-full cursor-sw-resize shadow-md z-20" 
                onMouseDown={(e) => handleFieldMouseDown(e, field, 'br')}
                onPointerDown={(e) => handleFieldMouseDown(e, field, 'br')}
              />
              <div 
                className="absolute -bottom-2 -left-2 w-4 h-4 bg-blue-600 border-2 border-white rounded-full cursor-se-resize shadow-md z-20" 
                onMouseDown={(e) => handleFieldMouseDown(e, field, 'bl')}
                onPointerDown={(e) => handleFieldMouseDown(e, field, 'bl')}
              />
            </>
          )}
        </div>
      );
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] overflow-y-auto p-2 md:p-4" dir="rtl">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-[95vw] mx-auto my-4 flex flex-col h-[95vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div>
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">סימון אזורי חתימה</h2>
            <p className="text-sm text-gray-600 mt-1">לחץ על המסמך כדי להוסיף אזור חתימה</p>
          </div>
          <button 
            onClick={onClose} 
            className="p-2 hover:bg-gray-100 rounded-lg transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="סגור"
          >
            <X className="w-6 h-6 text-gray-500" />
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Main Content - Responsive Layout */}
        <div className="flex-1 flex flex-col lg:flex-row-reverse gap-4 p-4 overflow-hidden min-h-0">
          {/* PDF Preview - Main Area (70-75% on desktop) */}
          <div className="flex-1 lg:w-[70%] flex flex-col min-h-0">
            {/* Signature Marking Toggle */}
            <div className="mb-3 flex items-center gap-3 bg-gradient-to-r from-green-50 to-emerald-50 p-3 rounded-lg border-2 border-green-200">
              <button
                onClick={() => setSignatureMarkingMode(!signatureMarkingMode)}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg font-medium transition-all min-w-[160px] justify-center min-h-[44px] ${
                  signatureMarkingMode
                    ? 'bg-green-600 text-white shadow-lg hover:bg-green-700'
                    : 'bg-white text-gray-700 border-2 border-gray-300 hover:bg-gray-50'
                }`}
                title={signatureMarkingMode ? 'מצב סימון פעיל - לחץ על המסמך להוספת חתימה' : 'לחץ להפעלת מצב סימון'}
              >
                <Edit3 className="w-5 h-5" />
                {signatureMarkingMode ? 'מצב סימון פעיל' : 'הפעל מצב סימון'}
              </button>
              <div className="flex-1 text-sm text-gray-700">
                {signatureMarkingMode ? (
                  <p className="font-medium">✓ לחץ על המסמך כדי להוסיף אזור חתימה</p>
                ) : (
                  <p>הפעל מצב סימון כדי להוסיף שדות חתימה</p>
                )}
              </div>
            </div>

            {/* Help Tooltip */}
            {showHelpTooltip && (
              <div className="mb-3 p-3 bg-blue-100 border-2 border-blue-400 rounded-lg text-blue-900 text-sm animate-pulse">
                💡 ניתן לגרור את אזור החתימה למיקום אחר ולשנות את גודלו
              </div>
            )}

            {/* PDF Canvas with Overlay */}
            <div className="flex-1 relative min-h-0">
              <PDFCanvas
                pdfUrl={`/api/contracts/${contractId}/pdf`}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                onTotalPagesChange={setTotalPages}
                scale={scale}
                onScaleChange={setScale}
                containerRef={canvasContainerRef}
                className="rounded-lg border-2 border-gray-300"
              >
                {/* Canvas Overlay for Signature Fields */}
                {pageViewport && (
                  <div
                    className={`absolute inset-0 ${signatureMarkingMode ? 'cursor-crosshair' : 'cursor-default'}`}
                    onClick={handleCanvasClick}
                    onPointerDown={handleCanvasClick}
                    onMouseMove={handleMouseMove}
                    onPointerMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onPointerUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                    onPointerLeave={handleMouseUp}
                    style={{
                      // 🔥 FIX: Set proper size and pointer-events
                      width: `${pageViewport.width}px`,
                      height: `${pageViewport.height}px`,
                      pointerEvents: signatureMarkingMode ? 'auto' : 'none',
                      zIndex: 2,
                      // 🔥 FIX: Ensure transparent background (don't cover PDF)
                      backgroundColor: 'transparent',
                    }}
                  >
                    {renderSignatureFields()}
                  </div>
                )}
              </PDFCanvas>
            </div>
          </div>

          {/* Sidebar - Fields List (25-30% on desktop) */}
          <div className="w-full lg:w-[30%] flex flex-col bg-gradient-to-br from-gray-50 to-blue-50 rounded-lg border-2 border-gray-200 shadow-lg overflow-hidden min-h-[300px] lg:min-h-0">
            <div className="p-4 border-b-2 border-gray-300 bg-white">
              <h3 className="font-bold text-gray-900 mb-3 text-lg">אזורי חתימה ({fields.length})</h3>
              <Button
                onClick={clearAllFields}
                disabled={fields.length === 0}
                variant="secondary"
                className="w-full flex items-center justify-center gap-2 text-sm min-h-[44px] font-medium"
              >
                <Trash2 className="w-5 h-5" />
                נקה את כל השדות
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {fields.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Edit3 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-base font-medium">לא נוספו שדות</p>
                  <p className="text-sm mt-2">הפעל מצב סימון ולחץ על המסמך</p>
                </div>
              ) : (
                fields.map((field, index) => (
                  <div
                    key={field.id}
                    className={`p-4 rounded-lg border-2 transition-all cursor-pointer ${
                      selectedFieldId === field.id
                        ? 'border-blue-600 bg-blue-100 shadow-lg'
                        : 'border-gray-300 bg-white hover:border-blue-400 hover:shadow-md'
                    }`}
                    onClick={() => focusOnField(field.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="font-bold text-gray-900 text-base">חתימה #{index + 1}</p>
                        <p className="text-sm text-gray-600 mt-1">עמוד {field.page}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            focusOnField(field.id);
                          }}
                          className="p-2 hover:bg-blue-200 rounded-lg transition min-w-[36px] min-h-[36px] flex items-center justify-center"
                          title="מקד על השדה"
                        >
                          <Eye className="w-5 h-5 text-blue-700" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteField(field.id);
                          }}
                          className="p-2 hover:bg-red-200 rounded-lg transition min-w-[36px] min-h-[36px] flex items-center justify-center"
                          title="מחק שדה"
                        >
                          <Trash2 className="w-5 h-5 text-red-700" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer Actions - Fixed on Mobile */}
        <div className="p-4 border-t-2 border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50 flex gap-3 flex-wrap lg:justify-end">
          <Button
            onClick={handleSave}
            disabled={saving || fields.length === 0}
            className="flex-1 lg:flex-none flex items-center justify-center gap-2 min-h-[48px] text-base font-medium"
          >
            <Save className="w-5 h-5" />
            {saving ? 'שומר...' : `שמור ${fields.length} שדות`}
          </Button>
          <Button 
            onClick={onClose} 
            variant="secondary"
            className="flex-1 lg:flex-none min-h-[48px] text-base font-medium"
          >
            ביטול
          </Button>
        </div>
      </div>
    </div>
  );
}
