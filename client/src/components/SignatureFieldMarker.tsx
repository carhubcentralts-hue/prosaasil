import React, { useState, useRef, useEffect } from 'react';
import { X, Plus, Save, Trash2, Eye, Move } from 'lucide-react';
import { Button } from '../shared/components/ui/Button';

export interface SignatureField {
  id: string;
  page: number; // 1-based
  x: number; // 0-1 relative
  y: number; // 0-1 relative
  w: number; // 0-1 relative
  h: number; // 0-1 relative
  required: boolean;
}

// Constants
const MIN_FIELD_SIZE = 0.05; // Minimum 5% width/height for signature fields
const DEFAULT_TOTAL_PAGES = 10; // Default page count for navigation (user can navigate beyond this)
const PDF_MIN_HEIGHT_VH = '70vh'; // Minimum height for PDF viewer on mobile

interface SignatureFieldMarkerProps {
  pdfUrl: string;
  contractId: number;
  onClose: () => void;
  onSave: (fields: SignatureField[]) => Promise<void>;
}

interface Rectangle {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}

export function SignatureFieldMarker({ pdfUrl, contractId, onClose, onSave }: SignatureFieldMarkerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [fields, setFields] = useState<SignatureField[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentRect, setCurrentRect] = useState<Rectangle | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<string | null>(null); // 'tl', 'tr', 'bl', 'br'
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Load existing signature fields
  useEffect(() => {
    loadSignatureFields();
  }, [contractId]);

  // Set PDF URL directly - the streaming endpoint handles authentication
  useEffect(() => {
    if (!pdfUrl) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    
    console.log('[PDF_LOAD] Using streaming endpoint:', pdfUrl);
    setPdfObjectUrl(pdfUrl);
    
    // Default page count for navigation
    setTotalPages(DEFAULT_TOTAL_PAGES);
    setLoading(false);
    
    // No cleanup needed - we're using a direct endpoint URL
  }, [pdfUrl]); // Only run when pdfUrl changes
  
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
      console.error('Error loading signature fields:', err);
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

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!canvasRef.current) return;
    
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // Check if clicking on existing field
    const clickedField = fields.find(f => 
      f.page === currentPage &&
      x >= f.x && x <= f.x + f.w &&
      y >= f.y && y <= f.y + f.h
    );

    if (clickedField) {
      setSelectedFieldId(clickedField.id);
      return;
    }

    // Start drawing new field
    setIsDrawing(true);
    setCurrentRect({
      startX: x,
      startY: y,
      endX: x,
      endY: y,
    });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !currentRect || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    setCurrentRect({
      ...currentRect,
      endX: Math.max(0, Math.min(1, x)),
      endY: Math.max(0, Math.min(1, y)),
    });
  };

  const handleMouseUp = () => {
    if (isDrawing && currentRect) {
      const width = Math.abs(currentRect.endX - currentRect.startX);
      const height = Math.abs(currentRect.endY - currentRect.startY);

      if (width > MIN_FIELD_SIZE && height > MIN_FIELD_SIZE) {
        const newField: SignatureField = {
          id: crypto.randomUUID ? crypto.randomUUID() : `field-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`,
          page: currentPage,
          x: Math.min(currentRect.startX, currentRect.endX),
          y: Math.min(currentRect.startY, currentRect.endY),
          w: width,
          h: height,
          required: true,
        };
        setFields(prev => [...prev, newField]);
      }
    }
    setIsDrawing(false);
    setCurrentRect(null);
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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-7xl mx-4 my-8 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-bold text-gray-900">סימון אזורי חתימה</h2>
            <p className="text-sm text-gray-600 mt-1">צייר מלבנים על המסמך כדי לסמן היכן יופיעו החתימות</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Main Content */}
        <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 overflow-hidden">
          {/* PDF Preview with Canvas Overlay */}
          <div className="flex-1 flex flex-col min-h-0">
            {/* Page Navigation */}
            <div className="flex items-center justify-between bg-blue-50 p-3 rounded-lg mb-3 border border-blue-200">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1 bg-white border border-blue-300 rounded hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                עמוד קודם
              </button>
              <span className="text-sm font-medium">
                עמוד {currentPage} מתוך {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1 bg-white border border-blue-300 rounded hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                עמוד הבא
              </button>
            </div>

            {/* PDF with Overlay */}
            <div className="flex-1 relative border-2 border-gray-300 rounded-lg bg-white overflow-hidden">
              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
                  <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
                    <p className="text-gray-600">טוען PDF...</p>
                  </div>
                </div>
              ) : pdfObjectUrl ? (
                <iframe
                  ref={iframeRef}
                  key={`${pdfObjectUrl}-${currentPage}`}
                  src={`${pdfObjectUrl}#page=${currentPage}&view=FitH`}
                  className="absolute inset-0 w-full h-full"
                  title="PDF Preview"
                  sandbox="allow-same-origin allow-scripts allow-downloads"
                  style={{ border: 'none', minHeight: PDF_MIN_HEIGHT_VH }}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
                  <p className="text-red-600">לא ניתן לטעון PDF</p>
                </div>
              )}
              
              {/* Canvas Overlay for Drawing - only show when PDF is loaded */}
              {pdfObjectUrl && !loading && (
                <div
                  ref={canvasRef}
                  className="absolute inset-0 cursor-crosshair"
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                >
                  {/* Render existing fields on current page */}
                  {getCurrentPageFields().map(field => (
                    <div
                      key={field.id}
                      className={`absolute border-2 ${
                        selectedFieldId === field.id
                          ? 'border-blue-500 bg-blue-100'
                          : 'border-green-500 bg-green-100'
                      } bg-opacity-30 transition-all`}
                      style={{
                        left: `${field.x * 100}%`,
                        top: `${field.y * 100}%`,
                        width: `${field.w * 100}%`,
                        height: `${field.h * 100}%`,
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFieldId(field.id);
                      }}
                    >
                      {/* Field Label */}
                      <div className="absolute -top-6 right-0 bg-green-600 text-white text-xs px-2 py-1 rounded">
                        חתימה {fields.indexOf(field) + 1}
                      </div>
                      
                      {/* Delete Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteField(field.id);
                        }}
                        className="absolute -top-2 -left-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                        title="מחק שדה"
                      >
                        <X className="w-3 h-3" />
                      </button>

                      {/* Resize Handles */}
                      {selectedFieldId === field.id && (
                        <>
                          <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 border border-white rounded-full cursor-nw-resize" />
                          <div className="absolute -top-1 -left-1 w-3 h-3 bg-blue-500 border border-white rounded-full cursor-ne-resize" />
                          <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-blue-500 border border-white rounded-full cursor-sw-resize" />
                          <div className="absolute -bottom-1 -left-1 w-3 h-3 bg-blue-500 border border-white rounded-full cursor-se-resize" />
                        </>
                      )}
                    </div>
                  ))}

                  {/* Current drawing rectangle */}
                  {isDrawing && currentRect && (
                    <div
                      className="absolute border-2 border-dashed border-blue-500 bg-blue-100 bg-opacity-20"
                      style={{
                        left: `${Math.min(currentRect.startX, currentRect.endX) * 100}%`,
                        top: `${Math.min(currentRect.startY, currentRect.endY) * 100}%`,
                        width: `${Math.abs(currentRect.endX - currentRect.startX) * 100}%`,
                        height: `${Math.abs(currentRect.endY - currentRect.startY) * 100}%`,
                      }}
                    />
                  )}
                </div>
              )}
            </div>

            {/* Instructions */}
            <div className="mt-3 p-3 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg border border-green-200">
              <p className="text-sm text-gray-700">
                <strong>הוראות:</strong> לחץ וגרור על המסמך כדי לצייר מלבן חתימה. לחץ על מלבן קיים כדי לבחור אותו.
              </p>
            </div>
          </div>

          {/* Sidebar - Fields List */}
          <div className="w-full md:w-80 flex flex-col bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">
            <div className="p-4 border-b border-gray-200 bg-white">
              <h3 className="font-bold text-gray-900 mb-2">שדות חתימה ({fields.length})</h3>
              <Button
                onClick={clearAllFields}
                disabled={fields.length === 0}
                variant="secondary"
                className="w-full flex items-center justify-center gap-2 text-sm"
              >
                <Trash2 className="w-4 h-4" />
                נקה הכל
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {fields.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Plus className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">לא נוספו שדות חתימה</p>
                  <p className="text-xs mt-1">צייר על המסמך כדי להוסיף</p>
                </div>
              ) : (
                fields.map((field, index) => (
                  <div
                    key={field.id}
                    className={`p-3 rounded-lg border-2 transition-all cursor-pointer ${
                      selectedFieldId === field.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                    onClick={() => focusOnField(field.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">חתימה {index + 1}</p>
                        <p className="text-sm text-gray-600">עמוד {field.page}</p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            focusOnField(field.id);
                          }}
                          className="p-1 hover:bg-blue-100 rounded transition"
                          title="מקד על השדה"
                        >
                          <Eye className="w-4 h-4 text-blue-600" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteField(field.id);
                          }}
                          className="p-1 hover:bg-red-100 rounded transition"
                          title="מחק שדה"
                        >
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-gray-200 flex gap-3 flex-wrap">
          <Button
            onClick={handleSave}
            disabled={saving || fields.length === 0}
            className="flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? 'שומר...' : `שמור ${fields.length} שדות`}
          </Button>
          <Button onClick={onClose} variant="secondary">
            ביטול
          </Button>
        </div>
      </div>
    </div>
  );
}
