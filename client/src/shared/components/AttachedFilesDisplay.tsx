import React, { useState, useEffect } from 'react';
import { X, File, Image, FileText, Video } from 'lucide-react';

interface Attachment {
  id: number;
  filename: string;
  mime_type: string;
  file_size: number;
}

interface AttachedFilesDisplayProps {
  attachmentIds: number[];
  onRemove: (attachmentId: number) => void;
  className?: string;
}

/**
 * Component to display attached files with remove buttons
 * Used in emails and WhatsApp to show files before sending
 */
export function AttachedFilesDisplay({ attachmentIds, onRemove, className = '' }: AttachedFilesDisplayProps) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (attachmentIds.length === 0) {
      setAttachments([]);
      return;
    }

    loadAttachmentDetails();
  }, [attachmentIds]);

  const loadAttachmentDetails = async () => {
    setLoading(true);
    try {
      // Fetch details for all attachment IDs
      const promises = attachmentIds.map(id =>
        fetch(`/api/attachments/${id}`, { credentials: 'include' })
          .then(res => res.ok ? res.json() : null)
      );
      
      const results = await Promise.all(promises);
      setAttachments(results.filter(Boolean));
    } catch (error) {
      console.error('Failed to load attachment details:', error);
    } finally {
      setLoading(false);
    }
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith('image/')) return <Image className="w-4 h-4" />;
    if (mimeType.startsWith('video/')) return <Video className="w-4 h-4" />;
    if (mimeType === 'application/pdf' || mimeType.includes('document')) return <FileText className="w-4 h-4" />;
    return <File className="w-4 h-4" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (attachmentIds.length === 0) {
    return null;
  }

  if (loading) {
    return (
      <div className={`p-3 bg-gray-50 border border-gray-200 rounded-md ${className}`}>
        <p className="text-sm text-gray-600">טוען קבצים...</p>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm font-semibold text-gray-700">
          קבצים מצורפים ({attachmentIds.length})
        </p>
      </div>
      
      <div className="space-y-2">
        {attachments.map((att) => (
          <div
            key={att.id}
            className="flex items-center gap-3 p-2.5 bg-green-50 border border-green-200 rounded-md group hover:bg-green-100 transition-colors"
          >
            {/* File icon */}
            <div className="flex-shrink-0 text-green-600">
              {getFileIcon(att.mime_type)}
            </div>
            
            {/* File info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate" title={att.filename}>
                {att.filename}
              </p>
              <p className="text-xs text-gray-500">
                {formatFileSize(att.file_size)}
              </p>
            </div>
            
            {/* Remove button */}
            <button
              type="button"
              onClick={() => onRemove(att.id)}
              className="flex-shrink-0 p-1.5 hover:bg-red-100 rounded-full transition-colors group"
              title="הסר קובץ"
              aria-label={`הסר ${att.filename}`}
            >
              <X className="w-4 h-4 text-red-600 group-hover:text-red-700" />
            </button>
          </div>
        ))}
      </div>
      
      {/* Summary */}
      <div className="flex items-center gap-2 pt-1">
        <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
        <span className="text-xs text-green-700 font-medium">
          מוכן לשליחה
        </span>
      </div>
    </div>
  );
}

export default AttachedFilesDisplay;
