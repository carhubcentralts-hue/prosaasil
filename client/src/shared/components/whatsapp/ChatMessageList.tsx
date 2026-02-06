import React, { useRef, useEffect } from 'react';
import { RefreshCw, MessageSquare, X, Volume2, FileText, Download, Image as ImageIcon } from 'lucide-react';
import { formatDate } from '../../utils/format';

// ─── Interfaces ──────────────────────────────────────────────────────────────
interface WhatsAppMessage {
  id: string | number;
  direction: 'in' | 'out';
  content_text?: string;
  body?: string;
  sent_at?: string;
  timestamp?: string;
  time?: string;
  status?: 'sending' | 'sent' | 'delivered' | 'read' | 'failed' | 'pending';
  source?: string;
  message_type?: string;
  media_url?: string | null;
}

interface ChatMessageListProps {
  messages: WhatsAppMessage[];
  loading?: boolean;
  onRetry?: (message: WhatsAppMessage) => void;
  showSourceBadges?: boolean;
  className?: string;
}

// ─── Source Badge ────────────────────────────────────────────────────────────
function SourceBadge({ source }: { source?: string }) {
  if (!source || source === 'client') return null;
  const config: Record<string, { label: string; cls: string }> = {
    bot: { label: '🤖 בוט', cls: 'bg-purple-100 text-purple-700' },
    human: { label: '👤 ידני', cls: 'bg-blue-100 text-blue-700' },
    automation: { label: '⚡ אוטומציה', cls: 'bg-amber-100 text-amber-700' },
    system: { label: '⚙️ מערכת', cls: 'bg-gray-100 text-gray-600' },
  };
  const c = config[source] || config.system;
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${c.cls}`}>{c.label}</span>;
}

// ─── Media Content ───────────────────────────────────────────────────────────
function MediaContent({ msg }: { msg: WhatsAppMessage }) {
  const { message_type, media_url, body, content_text } = msg;
  if (!media_url && (!message_type || message_type === 'text')) return null;

  const text = body || content_text || '';

  if (message_type === 'image' && media_url) {
    return (
      <div className="mb-1.5">
        <img
          src={media_url}
          alt={text || 'תמונה'}
          className="max-w-full rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
          style={{ maxHeight: 220 }}
          onClick={() => window.open(media_url, '_blank')}
        />
      </div>
    );
  }
  if (message_type === 'audio' && media_url) {
    return (
      <div className="mb-1.5 flex items-center gap-2 bg-white/20 rounded-lg p-2">
        <Volume2 className="h-4 w-4 flex-shrink-0" />
        <audio controls src={media_url} className="h-8 w-full" style={{ maxWidth: 200 }} />
      </div>
    );
  }
  if ((message_type === 'document' || message_type === 'video') && media_url) {
    return (
      <a href={media_url} target="_blank" rel="noopener noreferrer" className="mb-1.5 flex items-center gap-2 bg-white/20 rounded-lg p-2 hover:bg-white/30 transition-colors">
        {message_type === 'video' ? <ImageIcon className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
        <span className="text-xs underline">{text || 'קובץ'}</span>
        <Download className="h-3.5 w-3.5 ml-auto" />
      </a>
    );
  }
  return null;
}

// ─── Message Status Icon ─────────────────────────────────────────────────────
function MessageStatusIcon({ status }: { status?: string }) {
  switch (status) {
    case 'sending':
    case 'pending':
      return <div className="w-4 h-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />;
    case 'sent':
      return <span className="text-gray-400">✓</span>;
    case 'delivered':
      return <span className="text-gray-400">✓✓</span>;
    case 'read':
      return <span className="text-blue-500">✓✓</span>;
    case 'failed':
      return <span className="text-red-500">!</span>;
    default:
      return null;
  }
}

// ─── Bubble Style ────────────────────────────────────────────────────────────
function getBubbleStyle(msg: WhatsAppMessage) {
  if (msg.direction === 'in') return 'bg-white border border-gray-200 text-gray-900';
  const src = msg.source || 'bot';
  if (src === 'human') return 'bg-[#dcf8c6] text-gray-900';
  if (src === 'automation') return 'bg-amber-50 border border-amber-200 text-gray-900';
  return 'bg-[#d9fdd3] text-gray-900'; // bot / default outgoing
}

// ─── Main Component ──────────────────────────────────────────────────────────
export function ChatMessageList({ 
  messages, 
  loading = false, 
  onRetry, 
  showSourceBadges = true,
  className = '' 
}: ChatMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const getMessageText = (msg: WhatsAppMessage) => msg.content_text || msg.body || '';
  const getMessageTime = (msg: WhatsAppMessage) => {
    if (msg.time) return msg.time;
    if (msg.sent_at) return formatDate(msg.sent_at);
    if (msg.timestamp) return formatDate(msg.timestamp);
    return '';
  };

  return (
    <div
      className={`flex-1 overflow-y-auto px-2 md:px-4 py-3 min-h-0 ${className}`}
      style={{ 
        backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'200\' height=\'200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cdefs%3E%3Cpattern id=\'p\' width=\'40\' height=\'40\' patternUnits=\'userSpaceOnUse\'%3E%3Ccircle cx=\'20\' cy=\'20\' r=\'1\' fill=\'%23e5e7eb\' opacity=\'0.5\'/%3E%3C/pattern%3E%3C/defs%3E%3Crect fill=\'%23efeae2\' width=\'200\' height=\'200\'/%3E%3Crect fill=\'url(%23p)\' width=\'200\' height=\'200\'/%3E%3C/svg%3E")', 
        backgroundSize: '200px 200px' 
      }}
    >
      {loading && messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-gray-400">
          <RefreshCw className="h-8 w-8 animate-spin mb-2" />
          <p className="text-sm">טוען הודעות...</p>
        </div>
      ) : messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-gray-400">
          <div className="bg-white/80 rounded-2xl p-6 text-center shadow-sm">
            <MessageSquare className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            <p className="text-sm font-medium text-gray-500">אין הודעות עדיין</p>
            <p className="text-xs text-gray-400 mt-1">שלח הודעה כדי להתחיל שיחה</p>
          </div>
        </div>
      ) : (
        <div className="space-y-1.5 max-w-3xl mx-auto">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.direction === 'in' ? 'justify-start' : 'justify-end'}`}
              data-testid={`message-${msg.direction}-${msg.id}`}
            >
              <div
                className={`relative max-w-[85%] md:max-w-[75%] px-3 py-2 rounded-xl shadow-sm ${getBubbleStyle(msg)} ${
                  msg.status === 'pending' || msg.status === 'sending' ? 'opacity-70' : ''
                } ${msg.status === 'failed' ? 'border-2 border-red-300' : ''}`}
                style={{
                  borderTopRightRadius: msg.direction === 'out' ? '4px' : undefined,
                  borderTopLeftRadius: msg.direction === 'in' ? '4px' : undefined,
                  wordBreak: 'break-word',
                }}
                dir="rtl"
              >
                {/* Source badge for outgoing messages */}
                {msg.direction === 'out' && showSourceBadges && <SourceBadge source={msg.source} />}
                
                {/* Media content */}
                <MediaContent msg={msg} />
                
                {/* Text body */}
                {getMessageText(msg) && (
                  <p className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">
                    {getMessageText(msg)}
                  </p>
                )}
                
                {/* Footer: time + status + resend */}
                <div className="flex items-center justify-end gap-1 mt-0.5">
                  {msg.status === 'failed' && onRetry && (
                    <button
                      onClick={() => onRetry(msg)}
                      className="text-[10px] text-red-500 underline mr-1"
                    >
                      שלח שוב
                    </button>
                  )}
                  <span className="text-[10px] text-gray-500">{getMessageTime(msg)}</span>
                  {msg.direction === 'out' && <MessageStatusIcon status={msg.status} />}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  );
}
