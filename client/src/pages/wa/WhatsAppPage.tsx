import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageSquare, Users, Settings, Phone, QrCode, RefreshCw, Send, Bot, Smartphone, Server, ArrowRight, Power, Smile, Paperclip, Image, File, Trash2, Archive, Search, CheckCheck, Check, X, Clock, AlertCircle, Volume2, FileText, Download } from 'lucide-react';
import QRCodeReact from 'react-qr-code';
import { http } from '../../services/http';
import { formatDate, formatDateOnly, formatTimeOnly } from '../../shared/utils/format';
import { getConversationDisplayName } from '../../shared/utils/conversation';

// ─── UI Primitives ───────────────────────────────────────────────────────────
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-xl bg-white shadow-sm ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-[#25D366] text-white hover:bg-[#1da851] shadow-sm",
    outline: "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-300",
    ghost: "text-gray-600 hover:bg-gray-100",
    destructive: "bg-red-500 text-white hover:bg-red-600 shadow-sm"
  };
  const sizeClasses = { default: "px-4 py-2 text-sm", sm: "px-3 py-1.5 text-xs" };
  return (
    <button className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} disabled={disabled} {...props}>
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "secondary" | "destructive" | "success" | "warning";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-700",
    secondary: "bg-gray-100 text-gray-600",
    destructive: "bg-red-500 text-white",
    success: "bg-green-100 text-green-700",
    warning: "bg-amber-100 text-amber-700"
  };
  return <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${variantClasses[variant]} ${className}`}>{children}</span>;
};

// ─── Interfaces ──────────────────────────────────────────────────────────────
interface WhatsAppStatus {
  provider: string;
  ready: boolean;
  connected: boolean;
  configured: boolean;
  hasQR?: boolean;
  qr_required?: boolean;
  canSend?: boolean;
  session_age?: number;
  session_age_human?: string;
  last_message_ts?: string;
  last_message_age?: number;
  last_message_age_human?: string;
  active_phone?: string;
  error?: string;
}

interface WhatsAppThread {
  id: string;
  name: string;
  lead_name?: string;
  push_name?: string;
  lead_id?: number;
  phone: string;
  lastMessage: string;
  unread: number;
  time: string;
  summary?: string;
  is_closed?: boolean;
  has_media?: boolean;
}

interface WhatsAppMessageData {
  id: number;
  body: string;
  direction: 'in' | 'out';
  timestamp: string;
  time: string;
  status: string;
  message_type?: string;
  source?: string;
  media_url?: string | null;
}

interface QRCodeData {
  success?: boolean;
  qr?: string;
  qr_data?: string;
  dataUrl?: string;
  qrText?: string;
  status?: string;
  message?: string;
  error?: string;
  source?: string;
  fallback_mode?: boolean;
  ready?: boolean;
}

// ─── Message Status Icon ─────────────────────────────────────────────────────
function MessageStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'read':
      return <CheckCheck className="h-3.5 w-3.5 text-blue-400" />;
    case 'delivered':
      return <CheckCheck className="h-3.5 w-3.5 text-gray-400" />;
    case 'sent':
      return <Check className="h-3.5 w-3.5 text-gray-400" />;
    case 'pending':
    case 'queued':
      return <Clock className="h-3.5 w-3.5 text-gray-300" />;
    case 'failed':
      return <AlertCircle className="h-3.5 w-3.5 text-red-400" />;
    default:
      return <Check className="h-3.5 w-3.5 text-gray-400" />;
  }
}

// ─── Source Badge ─────────────────────────────────────────────────────────────
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

// ─── Media Renderer ──────────────────────────────────────────────────────────
function MediaContent({ msg }: { msg: WhatsAppMessageData }) {
  const { message_type, media_url, body } = msg;
  if (!media_url && (!message_type || message_type === 'text')) return null;

  if (message_type === 'image' && media_url) {
    return (
      <div className="mb-1.5">
        <img
          src={media_url}
          alt={body || 'תמונה'}
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
        {message_type === 'video' ? <Image className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
        <span className="text-xs underline">{body || 'קובץ'}</span>
        <Download className="h-3.5 w-3.5 ml-auto" />
      </a>
    );
  }
  return null;
}

export function WhatsAppPage() {
  const location = useLocation();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ─── State ──────────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [threads, setThreads] = useState<WhatsAppThread[]>([]);
  const [filteredThreads, setFilteredThreads] = useState<WhatsAppThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<WhatsAppThread | null>(null);
  const [whatsappStatus, setWhatsappStatus] = useState<WhatsAppStatus>({ provider: 'unknown', ready: false, connected: false, configured: false });
  const [selectedProvider, setSelectedProvider] = useState<'baileys' | 'meta'>('baileys');
  const [providerInfo, setProviderInfo] = useState<any>(null);
  const [qrCode, setQrCode] = useState<string>('');
  const [showQR, setShowQR] = useState(false);
  const [qrLoading, setQrLoading] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [messages, setMessages] = useState<WhatsAppMessageData[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'active' | 'unread' | 'closed'>('all');
  const [deepLinkPhone, setDeepLinkPhone] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [aiActive, setAiActive] = useState(true);
  const [togglingAi, setTogglingAi] = useState(false);
  const [savingProvider, setSavingProvider] = useState(false);
  const [providerChanged, setProviderChanged] = useState(false);
  const [activeChatsCount, setActiveChatsCount] = useState(0);
  const [summaries, setSummaries] = useState<{id: number; lead_name: string; phone: string; summary: string; summary_at: string}[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  // New: active tab for right panel (summaries vs settings)
  const [rightTab, setRightTab] = useState<'summaries' | 'settings'>('summaries');
  // New: deleting states
  const [deletingChat, setDeletingChat] = useState<string | null>(null);
  const [deletingSummary, setDeletingSummary] = useState<number | null>(null);
  // Mobile detection
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // ─── Auto-scroll messages ──────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ─── Initial data load ────────────────────────────────────────────────────
  useEffect(() => {
    loadWhatsAppStatus();
    loadThreads();
    loadPrompts();
    loadActiveChats();
    loadSummaries();
  }, []);

  // ─── Deep-link support ────────────────────────────────────────────────────
  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const phoneParam = sp.get('phone');
    if (!phoneParam) return;
    const normalized = phoneParam.replace(/[^0-9]/g, '');
    if (!normalized) return;
    setDeepLinkPhone(normalized);
    setSearchQuery(normalized);
    setFilterType('all');
  }, [location.search]);

  useEffect(() => {
    if (!deepLinkPhone || threads.length === 0) return;
    if (selectedThread) return;
    const match = threads.find(t => (t.phone || '').replace(/[^0-9]/g, '') === deepLinkPhone);
    if (match) setSelectedThread(match);
  }, [deepLinkPhone, threads, selectedThread]);

  // ─── Poll messages for selected thread ────────────────────────────────────
  useEffect(() => {
    if (!selectedThread) {
      setMessages([]);
      setAiActive(true);
      return;
    }

    const fetchAiState = async () => {
      try {
        const response = await http.get<{success: boolean; ai_active: boolean}>(`/api/whatsapp/ai-state?phone=${encodeURIComponent(selectedThread.phone)}`);
        if (response.success) setAiActive(response.ai_active);
      } catch { setAiActive(true); }
    };

    const fetchMessages = async () => {
      try {
        setLoadingMessages(true);
        const response = await http.get<{messages: WhatsAppMessageData[]}>(`/api/crm/threads/${selectedThread.phone}/messages`);
        setMessages(response.messages || []);
      } catch { setMessages([]); }
      finally { setLoadingMessages(false); }
    };

    fetchAiState();
    fetchMessages();
    const interval = setInterval(fetchMessages, 3000);
    return () => clearInterval(interval);
  }, [selectedThread]);

  // ─── QR polling ───────────────────────────────────────────────────────────
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (showQR && qrCode && !whatsappStatus.connected) {
      interval = setInterval(async () => {
        try {
          const statusResponse = await http.get<WhatsAppStatus>('/api/whatsapp/status');
          if (statusResponse.connected) {
            setShowQR(false);
            setQrCode('');
            setWhatsappStatus(statusResponse);
            return;
          }
          const qrResponse = await getQRCode();
          const qrData = qrResponse?.dataUrl || qrResponse?.qrText;
          if (qrData && qrData !== qrCode) setQrCode(qrData);
        } catch { /* QR refresh failed silently */ }
      }, 2500);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [showQR, qrCode, whatsappStatus.connected]);

  // ─── Filter threads ───────────────────────────────────────────────────────
  useEffect(() => {
    let filtered = [...threads];
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(t =>
        t.name.toLowerCase().includes(query) || t.phone.toLowerCase().includes(query) || t.lastMessage.toLowerCase().includes(query)
      );
    }
    switch (filterType) {
      case 'active': filtered = filtered.filter(t => !t.is_closed); break;
      case 'unread': filtered = filtered.filter(t => t.unread > 0); break;
      case 'closed': filtered = filtered.filter(t => t.is_closed); break;
    }
    setFilteredThreads(filtered);
  }, [threads, searchQuery, filterType]);

  // ─── Data loaders ─────────────────────────────────────────────────────────
  const loadWhatsAppStatus = async () => {
    try {
      const response = await http.get<WhatsAppStatus>('/api/whatsapp/status');
      setWhatsappStatus(response);
      try {
        const providerResponse = await http.get<any>('/api/whatsapp/provider-info');
        if (providerResponse.success) {
          setProviderInfo(providerResponse);
          if (providerResponse.provider === 'meta' || providerResponse.provider === 'baileys') setSelectedProvider(providerResponse.provider);
        }
      } catch { /* provider info load failed */ }
    } catch { /* status load failed */ }
  };

  const loadActiveChats = async () => {
    try {
      const response = await http.get<{success: boolean; count: number; chats: any[]}>('/api/whatsapp/active-chats');
      if (response.success) setActiveChatsCount(response.count);
    } catch { /* active chats load failed */ }
  };

  const loadSummaries = async () => {
    try {
      setLoadingSummaries(true);
      const response = await http.get<{success: boolean; summaries: any[]}>('/api/whatsapp/summaries');
      if (response.success && response.summaries) setSummaries(response.summaries);
    } catch { /* summaries load failed */ }
    finally { setLoadingSummaries(false); }
  };

  const loadThreadSummary = async (threadId: string) => {
    const thread = threads.find(t => t.id === threadId);
    if (!thread?.is_closed) return;
    if (thread?.summary && thread.summary !== 'לחץ לצפייה בסיכום') return;
    try {
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, summary: 'טוען...' } : t));
      const response = await http.get<{summary: string}>(`/api/crm/threads/${threadId}/summary`);
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, summary: response.summary } : t));
    } catch {
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, summary: 'שגיאה בטעינת סיכום' } : t));
    }
  };

  const loadThreads = async () => {
    try {
      setLoading(true);
      const response = await http.get<{threads: any[]}>('/api/crm/threads');
      const transformedThreads = (response.threads || []).map((thread: any) => ({
        id: thread.id?.toString() || '',
        name: getConversationDisplayName(thread, 'לא ידוע'),
        lead_name: thread.lead_name || undefined,
        push_name: thread.push_name || undefined,
        lead_id: thread.lead_id || undefined,
        phone: thread.phone_e164 || thread.phone || '',
        lastMessage: thread.lastMessage || thread.last_message || '',
        unread: thread.unread_count || thread.unread || 0,
        time: thread.time || (thread.last_activity ? formatTimeOnly(thread.last_activity) : ''),
        is_closed: thread.is_closed || false,
        has_media: thread.has_media || false,
        summary: thread.is_closed ? 'לחץ לצפייה בסיכום' : undefined
      }));
      setThreads(transformedThreads);
      setFilteredThreads(transformedThreads);
    } catch {
      setThreads([]);
      setFilteredThreads([]);
    } finally { setLoading(false); }
  };

  const loadPrompts = async () => {
    try {
      const response = await http.get<{calls_prompt: string, whatsapp_prompt: string, version: number}>('/api/business/current/prompt');
      setEditingPrompt(response.whatsapp_prompt || '');
    } catch { setEditingPrompt(''); }
  };

  // ─── QR Code ──────────────────────────────────────────────────────────────
  const getQRCode = async (): Promise<QRCodeData | null> => {
    try {
      const response = await http.get<QRCodeData>('/api/whatsapp/qr');
      if (response.dataUrl || response.qrText || response.status === 'connected') return response;
    } catch { /* qr failed */ }
    return null;
  };

  const disconnectWhatsApp = async () => {
    try {
      await http.post('/api/whatsapp/disconnect', {});
      setQrCode('');
      setShowQR(false);
      setWhatsappStatus({ provider: 'baileys', ready: false, connected: false, configured: true });
      alert('WhatsApp נותק בהצלחה!');
    } catch (error: any) {
      alert('שגיאה בניתוק: ' + (error?.message || 'שגיאה לא ידועה'));
    }
  };

  const generateQRCode = async () => {
    if (selectedProvider !== 'baileys') { alert('QR קוד זמין רק לספק Baileys'); return; }
    try {
      setQrLoading(true);
      await http.post('/api/whatsapp/start', { provider: selectedProvider });
      let attempts = 0;
      while (attempts < 10) {
        await new Promise(resolve => setTimeout(resolve, attempts === 0 ? 500 : 2500));
        const statusResponse = await http.get<WhatsAppStatus>('/api/whatsapp/status');
        if (statusResponse.connected) { alert('WhatsApp כבר מחובר למערכת'); break; }
        const qrResponse = await getQRCode();
        const qrData = qrResponse?.dataUrl || qrResponse?.qrText;
        if (qrData) { setQrCode(qrData); setShowQR(true); break; }
        attempts++;
      }
      if (attempts >= 10) alert('לא ניתן היה ליצור QR קוד. נסה שוב.');
    } catch (error: any) {
      alert('שגיאה ביצירת QR קוד: ' + (error.message || 'שגיאת רשת'));
    } finally { setQrLoading(false); }
  };

  // ─── Send Message (with optimistic UI) ────────────────────────────────────
  const sendMessage = async () => {
    if (!selectedThread || (!messageText.trim() && !selectedFile)) return;
    const textToSend = messageText.trim();
    const fileToSend = selectedFile;

    // Optimistic: add pending message to UI immediately
    const pendingId = -(Date.now() + Math.floor(Math.random() * 10000));
    if (textToSend && !fileToSend) {
      const pendingMsg: WhatsAppMessageData = {
        id: pendingId, body: textToSend, direction: 'out', timestamp: '', time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
        status: 'pending', message_type: 'text', source: 'human'
      };
      setMessages(prev => [...prev, pendingMsg]);
    }
    setMessageText('');
    setSelectedFile(null);
    setShowEmojiPicker(false);

    try {
      setSendingMessage(true);
      setUploadingFile(!!fileToSend);

      if (fileToSend) {
        const formData = new FormData();
        formData.append('file', fileToSend);
        if (textToSend) formData.append('caption', textToSend);
        formData.append('provider', selectedProvider);
        const response = await http.post<{success: boolean; error?: string}>(`/api/crm/threads/${selectedThread.phone}/message`, formData);
        if (!response.success) {
          setMessages(prev => prev.map(m => m.id === pendingId ? { ...m, status: 'failed' } : m));
          alert('שגיאה בשליחת הודעה: ' + (response.error || 'שגיאה'));
        }
      } else {
        const response = await http.post<{success: boolean; error?: string}>(`/api/crm/threads/${selectedThread.phone}/message`, { text: textToSend, provider: selectedProvider });
        if (!response.success) {
          // Revert optimistic message on failure
          setMessages(prev => prev.map(m => m.id === pendingId ? { ...m, status: 'failed' } : m));
        }
      }
      // Refresh messages from server
      const messagesResponse = await http.get<{messages: WhatsAppMessageData[]}>(`/api/crm/threads/${selectedThread.phone}/messages`);
      setMessages(messagesResponse.messages || []);
      loadThreads();
    } catch (error: any) {
      setMessages(prev => prev.map(m => m.id === pendingId ? { ...m, status: 'failed' } : m));
      alert('שגיאה בשליחת הודעה: ' + (error.message || 'שגיאה'));
    } finally {
      setSendingMessage(false);
      setUploadingFile(false);
    }
  };

  // ─── AI Toggle ────────────────────────────────────────────────────────────
  const toggleAi = async () => {
    if (!selectedThread) return;
    try {
      setTogglingAi(true);
      const newState = !aiActive;
      const response = await http.post<{success: boolean}>('/api/whatsapp/ai-state', { phone: selectedThread.phone, active: newState });
      if (response.success) setAiActive(newState);
    } catch { /* toggle failed */ }
    finally { setTogglingAi(false); }
  };

  const closeChat = () => { setSelectedThread(null); setMessages([]); setAiActive(true); };

  // ─── Provider ─────────────────────────────────────────────────────────────
  const saveProvider = async () => {
    try {
      setSavingProvider(true);
      const response = await http.put<{success: boolean; error?: string}>('/api/whatsapp/provider', { provider: selectedProvider });
      if (response.success) { setProviderChanged(false); await loadWhatsAppStatus(); alert('ספק נשמר בהצלחה!'); }
      else alert('שגיאה: ' + (response.error || 'שגיאה'));
    } catch (error: any) { alert('שגיאה: ' + (error.message || 'שגיאה')); }
    finally { setSavingProvider(false); }
  };

  const savePrompt = async () => {
    if (!editingPrompt.trim()) return;
    try {
      setSavingPrompt(true);
      const currentPrompt = await http.get<{calls_prompt: string, whatsapp_prompt: string}>('/api/business/current/prompt');
      const response = await http.put<{success: boolean; error?: string}>('/api/business/current/prompt', {
        calls_prompt: currentPrompt.calls_prompt, whatsapp_prompt: editingPrompt.trim()
      });
      if (response.success) { await loadPrompts(); setShowPromptEditor(false); alert('פרומפט נשמר!'); }
      else alert('שגיאה: ' + (response.error || 'שגיאה'));
    } catch { alert('שגיאה בשמירת הפרומפט'); }
    finally { setSavingPrompt(false); }
  };

  // ─── Delete summary ───────────────────────────────────────────────────────
  const deleteSummary = async (leadId: number) => {
    if (!confirm('למחוק את סיכום השיחה?')) return;
    try {
      setDeletingSummary(leadId);
      await http.delete(`/api/whatsapp/summaries/${leadId}`);
      setSummaries(prev => prev.filter(s => s.id !== leadId));
    } catch { alert('שגיאה במחיקת סיכום'); }
    finally { setDeletingSummary(null); }
  };

  // ─── Delete chat (soft-delete) ────────────────────────────────────────────
  const deleteChat = async (phone: string) => {
    if (!confirm('למחוק את השיחה? (ניתן לשחזר)')) return;
    try {
      setDeletingChat(phone);
      await http.post(`/api/whatsapp/conversations/${encodeURIComponent(phone)}/delete`, {});
      if (selectedThread?.phone === phone) closeChat();
      await loadThreads();
    } catch { alert('שגיאה במחיקת שיחה'); }
    finally { setDeletingChat(null); }
  };

  // ─── Bubble color based on source ────────────────────────────────────────
  const bubbleStyle = (msg: WhatsAppMessageData) => {
    if (msg.direction === 'in') return 'bg-white border border-gray-200 text-gray-900';
    const src = msg.source || 'bot';
    if (src === 'human') return 'bg-[#dcf8c6] text-gray-900';
    if (src === 'automation') return 'bg-amber-50 border border-amber-200 text-gray-900';
    return 'bg-[#d9fdd3] text-gray-900'; // bot / default outgoing
  };

  // ─── File validation helper ────────────────────────────────────────────────
  const handleFileSelect = (file: globalThis.File | undefined) => {
    if (!file) return;
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) { alert('הקובץ גדול מדי (מקסימום 10MB)'); return; }
    const ok = ['image/', 'video/', 'audio/', 'application/pdf', 'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!ok.some(t => file.type.startsWith(t) || file.type === t)) { alert('סוג קובץ לא נתמך'); return; }
    setSelectedFile(file);
  };

  // ─── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="relative mx-auto mb-5 h-12 w-12">
            <div className="absolute inset-0 rounded-full border-4 border-[#25D366]/20" />
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#25D366] animate-spin" />
          </div>
          <p className="text-gray-500 font-medium">טוען WhatsApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col max-w-[100vw] overflow-x-hidden" dir="rtl">
      {/* ══════ Top bar ══════ */}
      <div className="flex-shrink-0 bg-[#075e54] text-white px-3 md:px-4 py-2.5 md:py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <MessageSquare className="h-5 w-5 md:h-6 md:w-6 flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-base md:text-lg font-bold leading-tight truncate">WhatsApp Business</h1>
            <div className="flex items-center gap-1.5 md:gap-2 text-[10px] md:text-xs text-green-200">
              <span className={`inline-block h-2 w-2 rounded-full flex-shrink-0 ${whatsappStatus.connected ? 'bg-green-400' : 'bg-red-400'}`} />
              {whatsappStatus.connected ? 'מחובר' : 'לא מחובר'}
              {!isMobile && whatsappStatus.connected && <span>· {providerInfo?.provider || whatsappStatus.provider}</span>}
              {!isMobile && activeChatsCount > 0 && <span>· {activeChatsCount} שיחות פעילות</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
          <Button variant="ghost" size="sm" onClick={() => setShowQR(true)} className="text-white hover:bg-white/10" data-testid="button-qr">
            <QrCode className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setShowSettings(true)} className="text-white hover:bg-white/10" data-testid="button-settings">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {/* ══════ Main content: Sidebar + Chat (mobile-first) ══════ */}
      <div className="flex-1 flex min-h-0 bg-gray-100">

        {/* ── Right sidebar: Conversations list (hidden on mobile when chat is open) ── */}
        <div className={`${isMobile ? (selectedThread ? 'hidden' : 'w-full') : 'w-[340px] flex-shrink-0'} bg-white border-l border-gray-200 flex flex-col`}>
          {/* Search */}
          <div className="p-3 bg-gray-50 border-b border-gray-100">
            <div className="relative">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="חיפוש לפי שם או טלפון..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pr-9 pl-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]/30 focus:border-[#25D366]"
                dir="rtl"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-1 px-3 py-2 border-b border-gray-100 overflow-x-auto">
            {([
              { key: 'all' as const, label: 'הכל', count: threads.length },
              { key: 'active' as const, label: 'פעילים', count: threads.filter(t => !t.is_closed).length },
              { key: 'unread' as const, label: 'לא נקראו', count: threads.filter(t => t.unread > 0).length },
              { key: 'closed' as const, label: 'נסגרו', count: threads.filter(t => t.is_closed).length },
            ]).map(f => (
              <button
                key={f.key}
                onClick={() => setFilterType(f.key)}
                className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 ${
                  filterType === f.key
                    ? 'bg-[#25D366] text-white shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {f.label} ({f.count})
              </button>
            ))}
            <button onClick={loadThreads} className="p-1 text-gray-400 hover:text-gray-600 mr-auto" data-testid="button-refresh-threads">
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Thread list */}
          <div className="flex-1 overflow-y-auto">
            {filteredThreads.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 px-6">
                <MessageSquare className="h-10 w-10 mb-3" />
                <p className="text-sm text-center">{searchQuery || filterType !== 'all' ? 'לא נמצאו שיחות' : 'אין שיחות עדיין'}</p>
              </div>
            ) : (
              filteredThreads.map(thread => (
                <div
                  key={thread.id}
                  className={`group flex items-start gap-3 px-4 py-3 cursor-pointer border-b border-gray-50 transition-colors duration-150 ${
                    selectedThread?.id === thread.id ? 'bg-[#f0faf0]' : 'hover:bg-gray-50'
                  }`}
                  onClick={() => { setSelectedThread(thread); loadThreadSummary(thread.id); }}
                  data-testid={`thread-${thread.id}`}
                >
                  {/* Avatar */}
                  <div className="flex-shrink-0 w-11 h-11 rounded-full bg-gradient-to-br from-[#25D366] to-[#128C7E] flex items-center justify-center text-white text-sm font-bold shadow-sm">
                    {(thread.name || '?')[0]}
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="font-semibold text-gray-900 text-sm truncate">{thread.name}</span>
                        {thread.lead_name && <span className="text-[9px] px-1 py-0.5 bg-blue-100 text-blue-600 rounded flex-shrink-0">ליד</span>}
                      </div>
                      <span className="text-[11px] text-gray-400 flex-shrink-0 mr-2">{thread.time}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-gray-500 truncate leading-relaxed">{thread.lastMessage || thread.phone}</p>
                      <div className="flex items-center gap-1 flex-shrink-0 mr-2">
                        {thread.unread > 0 && (
                          <span className="min-w-[18px] h-[18px] bg-[#25D366] text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">{thread.unread}</span>
                        )}
                        {thread.is_closed && <Badge variant="success">נסגרה</Badge>}
                      </div>
                    </div>
                  </div>
                  {/* Delete action (visible on hover, always visible on mobile) */}
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteChat(thread.phone); }}
                    className={`${isMobile ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} p-1 text-gray-300 hover:text-red-500 transition-all duration-200 flex-shrink-0`}
                    title="מחק שיחה"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Center: Chat panel (full width on mobile) ── */}
        <div className={`${isMobile ? (selectedThread ? 'flex w-full' : 'hidden') : 'flex-1'} flex flex-col min-w-0`}>
          {selectedThread ? (
            <>
              {/* Chat header */}
              <div className="flex-shrink-0 bg-[#075e54] text-white px-3 md:px-4 py-2 md:py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-2 md:gap-3 min-w-0">
                  <button onClick={closeChat} className={`${isMobile ? '' : 'lg:hidden'} p-1 hover:bg-white/10 rounded flex-shrink-0`} data-testid="button-back-chat">
                    <ArrowRight className="h-5 w-5" />
                  </button>
                  <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold flex-shrink-0">
                    {(selectedThread.name || '?')[0]}
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-sm leading-tight truncate">{selectedThread.name}</h3>
                    <p className="text-xs text-green-200 truncate">{selectedThread.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
                  <button
                    onClick={toggleAi}
                    disabled={togglingAi}
                    className={`flex items-center gap-1 md:gap-1.5 px-2 md:px-2.5 py-1 rounded-full text-[11px] md:text-xs font-medium transition-all duration-200 ${
                      aiActive ? 'bg-green-400/20 text-green-200 hover:bg-green-400/30' : 'bg-red-400/20 text-red-200 hover:bg-red-400/30'
                    } ${togglingAi ? 'opacity-50' : ''}`}
                    data-testid="toggle-ai-active"
                  >
                    {togglingAi ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Power className="h-3.5 w-3.5" />}
                    {isMobile ? (aiActive ? 'AI' : 'AI') : (aiActive ? 'AI פעיל' : 'AI כבוי')}
                  </button>
                  <button onClick={() => deleteChat(selectedThread.phone)} className="p-1.5 hover:bg-white/10 rounded text-white/70 hover:text-white" title="מחק שיחה">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Messages area - WhatsApp wallpaper style */}
              <div
                className="flex-1 overflow-y-auto px-2 md:px-4 py-3 min-h-0"
                style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'200\' height=\'200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cdefs%3E%3Cpattern id=\'p\' width=\'40\' height=\'40\' patternUnits=\'userSpaceOnUse\'%3E%3Ccircle cx=\'20\' cy=\'20\' r=\'1\' fill=\'%23e5e7eb\' opacity=\'0.5\'/%3E%3C/pattern%3E%3C/defs%3E%3Crect fill=\'%23efeae2\' width=\'200\' height=\'200\'/%3E%3Crect fill=\'url(%23p)\' width=\'200\' height=\'200\'/%3E%3C/svg%3E")', backgroundSize: '200px 200px' }}
              >
                {loadingMessages && messages.length === 0 ? (
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
                      >
                        <div
                          className={`relative max-w-[85%] md:max-w-[75%] px-3 py-2 rounded-xl shadow-sm ${bubbleStyle(msg)} ${
                            msg.status === 'pending' ? 'opacity-70' : ''
                          } ${msg.status === 'failed' ? 'border-2 border-red-300' : ''}`}
                          style={{
                            borderTopRightRadius: msg.direction === 'out' ? '4px' : undefined,
                            borderTopLeftRadius: msg.direction === 'in' ? '4px' : undefined,
                            wordBreak: 'break-word',
                          }}
                          dir="rtl"
                        >
                          {/* Source badge for outgoing */}
                          {msg.direction === 'out' && <SourceBadge source={msg.source} />}
                          {/* Media content */}
                          <MediaContent msg={msg} />
                          {/* Text body */}
                          {msg.body && <p className="text-[13px] leading-relaxed whitespace-pre-wrap break-words">{msg.body}</p>}
                          {/* Footer: time + status + resend */}
                          <div className="flex items-center justify-end gap-1 mt-0.5">
                            {msg.status === 'failed' && (
                              <button
                                onClick={() => {
                                  setMessageText(msg.body);
                                  setMessages(prev => prev.filter(m => m.id !== msg.id));
                                }}
                                className="text-[10px] text-red-500 underline mr-1"
                              >
                                שלח שוב
                              </button>
                            )}
                            <span className="text-[10px] text-gray-500">{msg.time}</span>
                            {msg.direction === 'out' && <MessageStatusIcon status={msg.status} />}
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* ── Input area (with safe-area for iPhone) ── */}
              <div className="flex-shrink-0 bg-gray-50 border-t border-gray-200 px-2 md:px-3 py-2" style={{ paddingBottom: 'max(8px, env(safe-area-inset-bottom))' }}>
                {/* File preview */}
                {selectedFile && (
                  <div className="mb-2 p-2 bg-white rounded-lg border border-gray-200 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      {selectedFile.type.startsWith('image/') ? <Image className="h-4 w-4 text-blue-500 flex-shrink-0" /> : <File className="h-4 w-4 text-gray-500 flex-shrink-0" />}
                      <span className="text-xs text-gray-700 truncate">{selectedFile.name}</span>
                      <span className="text-[10px] text-gray-400 flex-shrink-0">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
                    </div>
                    <button onClick={() => setSelectedFile(null)} className="text-red-400 hover:text-red-600 p-0.5"><X className="h-3.5 w-3.5" /></button>
                  </div>
                )}
                {/* Emoji grid */}
                {showEmojiPicker && (
                  <div className="mb-2 p-2 bg-white rounded-lg border border-gray-200 shadow-lg">
                    <div className="grid grid-cols-8 gap-1">
                      {['😀','😂','😍','🤔','👍','👎','❤️','🎉','🔥','✅','❌','⭐','💪','🙏','👏','🤝'].map(em => (
                        <button key={em} onClick={() => { setMessageText(p => p + em); setShowEmojiPicker(false); }}
                          className="text-xl hover:bg-gray-100 rounded p-1 transition-colors">{em}</button>
                      ))}
                    </div>
                  </div>
                )}
                {/* Input row */}
                <div className="flex items-center gap-2">
                  <button onClick={() => setShowEmojiPicker(!showEmojiPicker)} className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full transition-colors">
                    <Smile className="h-5 w-5" />
                  </button>
                  <label className="cursor-pointer p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full transition-colors">
                    <input ref={fileInputRef} type="file" accept="image/*,video/*,audio/*,.pdf,.doc,.docx"
                      onChange={(e) => { handleFileSelect(e.target.files?.[0]); if (e.target) e.target.value = ''; }} className="hidden" />
                    <Paperclip className="h-5 w-5" />
                  </label>
                  <input
                    type="text"
                    placeholder="כתוב הודעה..."
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                    className="flex-1 px-4 py-2.5 bg-white border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]/30 focus:border-[#25D366]"
                    dir="rtl"
                    data-testid="input-message"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={sendingMessage || (!messageText.trim() && !selectedFile)}
                    className="p-2.5 bg-[#25D366] text-white rounded-full hover:bg-[#1da851] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-sm"
                    data-testid="button-send-message"
                  >
                    {sendingMessage ? <RefreshCw className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                  </button>
                </div>
              </div>
            </>
          ) : (
            /* Empty state - no chat selected (hidden on mobile - thread list shows instead) */
            <div className={`flex-1 ${isMobile ? 'hidden' : 'flex'} flex-col items-center justify-center bg-[#f0ebe3]`}>
              <div className="text-center max-w-sm px-4">
                <div className="w-20 h-20 mx-auto mb-5 rounded-full bg-[#25D366]/10 flex items-center justify-center">
                  <MessageSquare className="h-10 w-10 text-[#25D366]" />
                </div>
                <h3 className="text-xl font-semibold text-gray-700 mb-2">WhatsApp Business</h3>
                <p className="text-sm text-gray-500 leading-relaxed">בחר שיחה מהרשימה כדי לצפות בהודעות ולשלוח הודעות ללקוחות</p>
                <div className="mt-4 flex items-center justify-center gap-3 text-xs text-gray-400">
                  <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {threads.length} שיחות</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><Bot className="h-3.5 w-3.5" /> {activeChatsCount} פעילות</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Left sidebar: Summaries ── */}
        <div className="hidden xl:flex w-[300px] flex-shrink-0 bg-white border-r border-gray-200 flex-col">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-sm text-gray-700 flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4 text-[#25D366]" /> סיכומי שיחות
            </h3>
            <button onClick={loadSummaries} disabled={loadingSummaries} className="p-1 text-gray-400 hover:text-gray-600" data-testid="button-refresh-summaries">
              <RefreshCw className={`h-3.5 w-3.5 ${loadingSummaries ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingSummaries ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="h-5 w-5 animate-spin text-gray-300" />
              </div>
            ) : summaries.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full px-6 text-gray-400">
                <MessageSquare className="h-8 w-8 mb-2" />
                <p className="text-xs text-center">אין סיכומים עדיין</p>
                <p className="text-[10px] text-center mt-1">סיכום נוצר אוטומטית אחרי 5 דקות ללא פעילות</p>
              </div>
            ) : (
              summaries.map(s => (
                <div key={s.id} className="group px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between mb-1">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{s.lead_name || 'לקוח'}</p>
                      <p className="text-[10px] text-gray-400">{s.phone}</p>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0 mr-2">
                      <span className="text-[10px] text-gray-400">
                        {s.summary_at ? new Date(s.summary_at).toLocaleDateString('he-IL', { day: 'numeric', month: 'short', timeZone: 'Asia/Jerusalem' }) : ''}
                      </span>
                      <button
                        onClick={() => deleteSummary(s.id)}
                        disabled={deletingSummary === s.id}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-300 hover:text-red-500 transition-all"
                        title="מחק סיכום"
                      >
                        {deletingSummary === s.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed line-clamp-3">{s.summary}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ══════ Settings Modal ══════ */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" data-testid="modal-settings" onClick={() => setShowSettings(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="bg-[#075e54] text-white px-6 py-4 flex items-center justify-between">
              <h3 className="font-semibold">הגדרות WhatsApp</h3>
              <button onClick={() => setShowSettings(false)} className="hover:bg-white/10 rounded p-1"><X className="h-5 w-5" /></button>
            </div>
            <div className="p-6 space-y-5">
              {/* Provider selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">ספק WhatsApp</label>
                <div className="grid grid-cols-2 gap-3">
                  {(['baileys', 'meta'] as const).map(prov => (
                    <button key={prov} onClick={() => { setSelectedProvider(prov); setProviderChanged(true); }}
                      className={`p-3 rounded-xl border-2 text-sm font-medium transition-all ${selectedProvider === prov ? 'border-[#25D366] bg-green-50 text-green-800' : 'border-gray-200 hover:border-gray-300 text-gray-600'}`}
                      data-testid={`radio-${prov}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {prov === 'baileys' ? <QrCode className="h-4 w-4" /> : <Smartphone className="h-4 w-4" />}
                        {prov === 'baileys' ? 'Baileys' : 'Meta Cloud'}
                      </div>
                      <p className="text-[10px] text-gray-400">{prov === 'baileys' ? 'WhatsApp Web (QR)' : 'Business Cloud API'}</p>
                    </button>
                  ))}
                </div>
                {providerChanged && (
                  <Button onClick={saveProvider} disabled={savingProvider} className="w-full mt-3" data-testid="button-save-provider">
                    {savingProvider ? <RefreshCw className="h-4 w-4 animate-spin ml-2" /> : null}
                    {savingProvider ? 'שומר...' : 'שמור שינוי ספק'}
                  </Button>
                )}
              </div>
              {/* Connection status */}
              <div className="p-4 bg-gray-50 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 font-medium">סטטוס חיבור</span>
                  <Badge variant={whatsappStatus.connected ? 'success' : 'warning'} data-testid="status-connection">
                    {whatsappStatus.connected ? 'מחובר ✅' : 'לא מחובר'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>ספק: {providerInfo?.provider || whatsappStatus.provider}</span>
                  {whatsappStatus.session_age_human && <span>חיבור: {whatsappStatus.session_age_human}</span>}
                </div>
                {whatsappStatus.qr_required && !whatsappStatus.connected && (
                  <p className="text-xs text-amber-600">⚠️ נדרש סריקת QR code</p>
                )}
              </div>
              {/* Baileys controls */}
              {selectedProvider === 'baileys' && (
                <div className="flex gap-2">
                  <Button onClick={generateQRCode} disabled={qrLoading} className="flex-1" data-testid="button-generate-qr">
                    {qrLoading ? <RefreshCw className="h-4 w-4 animate-spin ml-2" /> : <QrCode className="h-4 w-4 ml-2" />}
                    {qrLoading ? 'יוצר...' : 'QR קוד'}
                  </Button>
                  <Button variant="destructive" onClick={disconnectWhatsApp} className="flex-1" data-testid="button-disconnect">
                    נתק חיבור
                  </Button>
                </div>
              )}
              {selectedProvider === 'meta' && (
                <Button variant="outline" className="w-full" data-testid="button-test-meta"
                  onClick={async () => {
                    const ph = prompt('הכנס מספר טלפון (כולל קידומת):');
                    if (!ph) return;
                    try {
                      const r = await http.post<any>('/api/whatsapp/test', { to: ph, text: 'הודעת בדיקה מ-ProSaaS 🚀' });
                      alert(r.success ? '✅ נשלחה!' : '❌ שגיאה: ' + (r.error || ''));
                    } catch (err: any) { alert('❌ ' + err.message); }
                  }}>
                  <Send className="h-4 w-4 ml-2" /> שלח הודעת בדיקה
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══════ QR Modal ══════ */}
      {showQR && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" data-testid="modal-qr" onClick={() => setShowQR(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="bg-[#075e54] text-white px-6 py-4 text-center">
              <h3 className="font-semibold">חיבור WhatsApp</h3>
              <p className="text-xs text-green-200 mt-1">סרוק את הקוד עם WhatsApp שלך</p>
            </div>
            <div className="p-6 flex flex-col items-center">
              {qrCode ? (
                <>
                  <div className="bg-white p-4 rounded-xl border border-gray-100 shadow-inner">
                    {qrCode.startsWith('data:image/') ? (
                      <img src={qrCode} alt="QR Code" className="w-52 h-52" data-testid="img-qr" />
                    ) : (
                      <QRCodeReact value={qrCode} size={208} level="M" data-testid="qr-component" />
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-3">סרוק עם WhatsApp שלך כדי להתחבר</p>
                </>
              ) : (
                <>
                  <div className="w-52 h-52 bg-gray-100 rounded-xl flex items-center justify-center">
                    <QrCode className="h-16 w-16 text-gray-300" />
                  </div>
                  <p className="text-xs text-gray-500 mt-3">לחץ כדי ליצור QR קוד</p>
                </>
              )}
              <div className="flex gap-2 w-full mt-5">
                <Button variant="outline" onClick={() => setShowQR(false)} className="flex-1" data-testid="button-close-qr">סגור</Button>
                {!qrCode && (
                  <Button onClick={generateQRCode} disabled={qrLoading} className="flex-1" data-testid="button-generate-qr-modal">
                    {qrLoading ? 'יוצר...' : 'צור QR קוד'}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

}