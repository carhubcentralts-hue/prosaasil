import React, { useState, useEffect } from 'react';
import { Upload, X, Image, FileText, Video, File, Paperclip } from 'lucide-react';

interface Attachment {
  id: number;
  filename: string;
  mime_type: string;
  file_size: number;
  channel_compatibility: {
    email: boolean;
    whatsapp: boolean;
    broadcast: boolean;
  };
  preview_url: string;
  created_at: string;
}

interface AttachmentPickerProps {
  channel: 'email' | 'whatsapp' | 'broadcast';
  onAttachmentSelect: (attachmentId: number | number[] | null) => void;
  selectedAttachmentId?: number | null;
  mode?: 'single' | 'multi';  // NEW: support multiple selections
}

export function AttachmentPicker({ channel, onAttachmentSelect, selectedAttachmentId, mode = 'single' }: AttachmentPickerProps) {
  const [modeView, setModeView] = useState<'select' | 'upload'>('select');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [filter, setFilter] = useState<'all' | 'images' | 'documents' | 'videos'>('all');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);  // NEW: for multi mode

  // Load attachments on mount and when filter changes
  useEffect(() => {
    loadAttachments();
  }, [filter, channel]);

  const loadAttachments = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      params.append('channel', channel);
      
      if (filter !== 'all') {
        if (filter === 'images') params.append('mime_type', 'image/');
        else if (filter === 'documents') params.append('mime_type', 'application/');
        else if (filter === 'videos') params.append('mime_type', 'video/');
      }
      
      const response = await fetch(`/api/attachments?${params.toString()}`, {
        credentials: 'include',
      });
      
      if (!response.ok) {
        throw new Error('Failed to load attachments');
      }
      
      const data = await response.json();
      setAttachments(data.items || []);
    } catch (err) {
      console.error('Error loading attachments:', err);
      setError('Failed to load attachments');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    
    setUploading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('channel', channel);
      
      const response = await fetch('/api/attachments/upload', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Upload failed');
      }
      
      const attachment = await response.json();
      
      // Add to list and select
      setAttachments([attachment, ...attachments]);
      onAttachmentSelect(attachment.id);
      
      // Reset upload state
      setSelectedFile(null);
      setModeView('select');
      
    } catch (err: any) {
      console.error('Error uploading file:', err);
      setError(err.message || 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith('image/')) return <Image className="w-5 h-5" />;
    if (mimeType.startsWith('video/')) return <Video className="w-5 h-5" />;
    if (mimeType === 'application/pdf' || mimeType.includes('document')) return <FileText className="w-5 h-5" />;
    return <File className="w-5 h-5" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full">
      {/* Header with mode toggle */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Paperclip className="w-5 h-5 text-gray-500" />
          <h3 className="text-lg font-semibold">צרף קובץ</h3>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={() => setModeView('select')}
            className={`px-3 py-1 rounded-md text-sm ${
              modeView === 'select'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            בחר קיים
          </button>
          <button
            onClick={() => setModeView('upload')}
            className={`px-3 py-1 rounded-md text-sm ${
              modeView === 'upload'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            העלה חדש
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Upload mode */}
      {modeView === 'upload' && (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
          <div className="text-center">
            <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            
            {!selectedFile ? (
              <>
                <p className="text-gray-600 mb-2">לחץ לבחירת קובץ או גרור לכאן</p>
                <input
                  type="file"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="file-upload"
                  accept="image/*,video/*,application/pdf,.doc,.docx,.xls,.xlsx"
                />
                <label
                  htmlFor="file-upload"
                  className="inline-block px-4 py-2 bg-blue-500 text-white rounded-md cursor-pointer hover:bg-blue-600"
                >
                  בחר קובץ
                </label>
              </>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-center gap-2 text-gray-700">
                  {getFileIcon(selectedFile.type)}
                  <span>{selectedFile.name}</span>
                  <span className="text-sm text-gray-500">({formatFileSize(selectedFile.size)})</span>
                </div>
                
                <div className="flex gap-2 justify-center">
                  <button
                    onClick={handleUpload}
                    disabled={uploading}
                    className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 disabled:opacity-50"
                  >
                    {uploading ? 'מעלה...' : 'העלה'}
                  </button>
                  <button
                    onClick={() => setSelectedFile(null)}
                    disabled={uploading}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50"
                  >
                    ביטול
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Select mode */}
      {modeView === 'select' && (
        <>
          {/* Filter tabs */}
          <div className="flex gap-2 mb-4">
            {(['all', 'images', 'documents', 'videos'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded-md text-sm ${
                  filter === f
                    ? 'bg-blue-100 text-blue-700 border border-blue-300'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {f === 'all' ? 'הכל' : f === 'images' ? 'תמונות' : f === 'documents' ? 'מסמכים' : 'סרטונים'}
              </button>
            ))}
          </div>

          {/* Attachments grid */}
          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="text-center py-8 text-gray-500">טוען...</div>
            ) : attachments.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                אין קבצים
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {attachments.map((att) => {
                  const isSelected = modeView === 'multi' 
                    ? selectedIds.includes(att.id)
                    : att.id === selectedAttachmentId;
                  
                  return (
                    <button
                      key={att.id}
                      onClick={() => {
                        if (modeView === 'multi') {
                          // Toggle selection in multi mode
                          const newIds = selectedIds.includes(att.id)
                            ? selectedIds.filter(id => id !== att.id)
                            : [...selectedIds, att.id];
                          setSelectedIds(newIds);
                          onAttachmentSelect(newIds.length > 0 ? newIds : null);
                        } else {
                          // Single mode
                          onAttachmentSelect(att.id === selectedAttachmentId ? null : att.id);
                        }
                      }}
                      className={`relative p-3 border rounded-lg hover:border-blue-300 transition ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200'
                      }`}
                    >
                    {/* Preview */}
                    <div className="aspect-square mb-2 bg-gray-100 rounded flex items-center justify-center overflow-hidden">
                      {att.mime_type.startsWith('image/') ? (
                        <img
                          src={att.preview_url}
                          alt={att.filename}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="text-gray-400">
                          {getFileIcon(att.mime_type)}
                        </div>
                      )}
                    </div>
                    
                    {/* Filename */}
                    <p className="text-xs text-gray-700 truncate" title={att.filename}>
                      {att.filename}
                    </p>
                    
                    {/* File size */}
                    <p className="text-xs text-gray-500">
                      {formatFileSize(att.file_size)}
                    </p>
                    
                    {/* Selected indicator */}
                    {isSelected && (
                      <div className="absolute top-2 left-2 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                    )}
                  </button>
                );
                })}
              </div>
            )}
          </div>

          {/* Clear selection button */}
          {((modeView === 'single' && selectedAttachmentId) || (modeView === 'multi' && selectedIds.length > 0)) && (
            <div className="mt-4 text-center">
              <button
                onClick={() => {
                  if (modeView === 'multi') {
                    setSelectedIds([]);
                  }
                  onAttachmentSelect(null);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                <X className="w-4 h-4" />
                נקה בחירה {modeView === 'multi' && selectedIds.length > 0 && `(${selectedIds.length})`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default AttachmentPicker;
