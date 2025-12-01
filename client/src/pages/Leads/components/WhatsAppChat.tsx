import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Phone, MoreVertical, Paperclip, Smile, X, ArrowRight, Bot, BotOff } from 'lucide-react';
import QRCode from 'qrcode';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { http } from '../../../services/http';
import { formatDate } from '../../../shared/utils/format';
import { Lead } from '../types';
import { useAuth } from '../../../features/auth/hooks';

interface WhatsAppMessage {
  id: string;
  direction: 'in' | 'out';
  content_text: string;
  sent_at: string;
  status?: 'sending' | 'sent' | 'delivered' | 'read' | 'failed';
  provider?: string;
}

interface WhatsAppConversation {
  id: number;
  phone_number: string;
  messages: WhatsAppMessage[];
  total_messages: number;
  last_message_at?: string;
}

interface WhatsAppChatProps {
  lead: Lead;
  isOpen: boolean;
  onClose: () => void;
}

interface WhatsAppProvider {
  id: string;
  name: string;
  type: 'twilio' | 'baileys';
  status: 'active' | 'inactive';
  description: string;
}

export default function WhatsAppChat({ lead, isOpen, onClose }: WhatsAppChatProps) {
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [conversation, setConversation] = useState<WhatsAppConversation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('twilio');
  const [showQRCode, setShowQRCode] = useState(false);
  const [qrCode, setQRCode] = useState<string>('');
  const [qrImageUrl, setQrImageUrl] = useState<string>('');
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [aiEnabled, setAiEnabled] = useState(true);
  const [togglingAi, setTogglingAi] = useState(false);
  const [providers, setProviders] = useState<WhatsAppProvider[]>([
    { id: 'twilio', name: 'Twilio WhatsApp', type: 'twilio', status: 'active', description: 'ספק רשמי דרך Twilio Business API' },
    { id: 'baileys', name: 'WhatsApp Web', type: 'baileys', status: 'active', description: 'חיבור ישיר דרך WhatsApp Web' }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const { user, tenant } = useAuth();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchQRCode = async () => {
    try {
      setConnectionStatus('connecting');
      const response = await http.get<{ dataUrl: string }>('/api/whatsapp/qr');
      setQRCode(response.dataUrl);
      
      // Use the QR data URL directly if it's already base64, otherwise generate QR image
      try {
        let qrImageDataUrl = response.dataUrl;
        
        // If it's not a data URL, generate QR from the string
        if (!response.dataUrl.startsWith('data:image/')) {
          qrImageDataUrl = await QRCode.toDataURL(response.dataUrl, {
            width: 256,
            margin: 2,
            color: {
              dark: '#000000',
              light: '#FFFFFF'
            }
          });
        }
        
        setQrImageUrl(qrImageDataUrl);
        setConnectionStatus('connected');
      } catch (qrErr) {
        console.error('Failed to generate QR image:', qrErr);
        setQrImageUrl('');
        setConnectionStatus('connected'); // Still show text fallback
      }
    } catch (err) {
      console.error('Failed to fetch QR code:', err);
      setError('שגיאה בטעינת קוד QR - נתונים מדמה');
      // For demo purposes, generate a sample QR
      try {
        const sampleQr = 'baileys-whatsapp-demo-' + Date.now();
        setQRCode(sampleQr);
        const qrImageDataUrl = await QRCode.toDataURL(sampleQr, {
          width: 256,
          margin: 2,
          color: {
            dark: '#000000',
            light: '#FFFFFF'
          }
        });
        setQrImageUrl(qrImageDataUrl);
        setConnectionStatus('connected');
      } catch (qrErr) {
        setConnectionStatus('disconnected');
      }
    }
  };

  const getBusinessId = useCallback(() => {
    // Use business_id from user first, fallback to tenant.id
    return user?.business_id || tenant?.id || 1;
  }, [user, tenant]);

  const fetchConversation = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);
      
      // Clean phone number (remove +)
      const phoneNumber = lead.phone_e164?.replace('+', '') || '';
      
      const response = await http.get<WhatsAppConversation>(`/api/whatsapp/conversation/${phoneNumber}`);
      
      setConversation(response);
      setMessages(response.messages || []);
    } catch (err: any) {
      console.error('Failed to fetch WhatsApp conversation:', err);
      setError('שגיאה בטעינת השיחה');
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [lead.phone_e164]);

  const startPolling = useCallback(() => {
    stopPolling(); // Clear any existing interval
    
    pollingIntervalRef.current = setInterval(() => {
      // Poll for new messages without showing loading spinner
      fetchConversation(false);
    }, 5000); // Poll every 5 seconds
  }, [fetchConversation]);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  // Fetch AI state for this conversation
  const fetchAiState = useCallback(async () => {
    try {
      const phoneNumber = lead.phone_e164?.replace('+', '') || '';
      const response = await http.get<{ success: boolean; ai_enabled: boolean }>(`/api/whatsapp/ai-state/${phoneNumber}`);
      if (response.success) {
        setAiEnabled(response.ai_enabled);
      }
    } catch (err) {
      console.error('Failed to fetch AI state:', err);
      // Default to enabled if can't fetch
      setAiEnabled(true);
    }
  }, [lead.phone_e164]);

  useEffect(() => {
    if (isOpen && lead.phone_e164) {
      fetchConversation();
      fetchAiState();  // Load AI state when opening chat
      // Start polling for new messages every 5 seconds
      startPolling();
    } else {
      // Stop polling when chat is closed
      stopPolling();
    }
    
    return () => {
      stopPolling();
    };
  }, [isOpen, lead.phone_e164, fetchConversation, fetchAiState, startPolling, stopPolling]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !lead.phone_e164 || sending) {
      return;
    }

    try {
      setSending(true);
      setError(null);

      // Add optimistic message
      const optimisticMessage: WhatsAppMessage = {
        id: `temp-${Date.now()}`,
        direction: 'out',
        content_text: newMessage.trim(),
        sent_at: new Date().toISOString(),
        status: 'sending'
      };

      setMessages(prev => [...prev, optimisticMessage]);
      setNewMessage('');

      // Send to API
      const response = await http.post<{
        ok: boolean;
        success?: boolean;
        message_id?: string;
        error?: string;
      }>('/api/whatsapp/send', {
        to: lead.phone_e164,
        message: newMessage.trim(),
        business_id: getBusinessId(),
        provider: selectedProvider
      });

      // 🔥 FIX: Backend returns 'ok', frontend was checking 'success' - check both!
      if (response.ok || response.success) {
        // Update optimistic message with real data
        setMessages(prev => 
          prev.map(msg => 
            msg.id === optimisticMessage.id 
              ? { ...msg, id: response.message_id || msg.id, status: 'sent' }
              : msg
          )
        );
      } else {
        // Mark as failed
        setMessages(prev => 
          prev.map(msg => 
            msg.id === optimisticMessage.id 
              ? { ...msg, status: 'failed' }
              : msg
          )
        );
        setError(response.error || 'שליחת ההודעה נכשלה');
      }
    } catch (err: any) {
      console.error('Failed to send WhatsApp message:', err);
      setError('שגיאה בשליחת ההודעה');
      
      // Mark optimistic message as failed
      setMessages(prev => 
        prev.map(msg => 
          msg.direction === 'out' && msg.status === 'sending'
            ? { ...msg, status: 'failed' }
            : msg
        )
      );
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Toggle AI for this conversation
  const toggleAi = async () => {
    try {
      setTogglingAi(true);
      const phoneNumber = lead.phone_e164?.replace('+', '') || '';
      const newState = !aiEnabled;
      
      const response = await http.post<{ success: boolean; ai_enabled: boolean }>('/api/whatsapp/toggle-ai', {
        phone_number: phoneNumber,
        ai_enabled: newState,
        business_id: getBusinessId()
      });
      
      if (response.success) {
        setAiEnabled(response.ai_enabled);
        // Simple status update - no alert needed, UI will show the state
      }
    } catch (err) {
      console.error('Failed to toggle AI:', err);
      alert('שגיאה: לא ניתן לשנות מצב AI');
    } finally {
      setTogglingAi(false);
    }
  };

  // Placeholder handlers for emoji and attachment
  const handleEmojiClick = () => {
    alert('בחירת אימוג\'י תהיה זמינה בקרוב');
  };

  const handleAttachClick = () => {
    alert('צירוף קבצים יהיה זמין בקרוב');
  };

  const getMessageStatusIcon = (status?: string) => {
    switch (status) {
      case 'sending':
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
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="whatsapp-chat-modal">
      <Card className="w-full max-w-md h-[600px] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-green-50">
          {/* Back button - prominent */}
          <Button 
            size="sm" 
            variant="ghost" 
            onClick={onClose} 
            className="ml-2 hover:bg-green-100"
            data-testid="button-whatsapp-back"
          >
            <ArrowRight className="w-5 h-5" />
          </Button>
          
          <div className="flex items-center space-x-3 flex-1 mr-3">
            <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center text-white font-semibold">
              {lead.first_name?.charAt(0) || lead.full_name?.charAt(0) || '?'}
            </div>
            <div>
              <h3 className="font-semibold text-gray-900" data-testid="whatsapp-contact-name">
                {lead.full_name || `${lead.first_name} ${lead.last_name}`.trim() || 'ללא שם'}
              </h3>
              <p className="text-sm text-gray-600" data-testid="whatsapp-contact-phone">
                {lead.phone_e164}
              </p>
              <div className="flex items-center mt-1">
                <Badge variant="success" className="text-xs">
                  {providers.find(p => p.id === selectedProvider)?.name || 'Twilio'}
                </Badge>
                <select 
                  value={selectedProvider} 
                  onChange={(e) => {
                    setSelectedProvider(e.target.value);
                    if (e.target.value === 'baileys') {
                      setShowQRCode(true);
                      fetchQRCode();
                    } else {
                      setShowQRCode(false);
                    }
                  }}
                  className="ml-2 text-xs bg-transparent border-none cursor-pointer text-green-600 font-medium"
                  data-testid="select-whatsapp-provider"
                >
                  {providers.filter(p => p.status === 'active').map(provider => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* AI Toggle Button */}
            <Button 
              size="sm" 
              variant="secondary"
              onClick={toggleAi}
              disabled={togglingAi}
              className={`${aiEnabled ? 'bg-blue-500 hover:bg-blue-600' : 'bg-red-500 hover:bg-red-600'} text-white`}
              data-testid="button-toggle-ai"
              title={aiEnabled ? 'AI פעיל - לחץ לכיבוי' : 'AI מושבת - לחץ להפעלה'}
            >
              {togglingAi ? (
                <div className="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : aiEnabled ? (
                <Bot className="w-4 h-4" />
              ) : (
                <BotOff className="w-4 h-4" />
              )}
            </Button>
            <Button size="sm" variant="ghost" data-testid="button-whatsapp-call">
              <Phone className="w-4 h-4" />
            </Button>
            <Button size="sm" variant="ghost" data-testid="button-whatsapp-more">
              <MoreVertical className="w-4 h-4" />
            </Button>
            {/* Close X button */}
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={onClose} 
              className="hover:bg-red-100 hover:text-red-600"
              data-testid="button-whatsapp-close"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* QR Code Modal for Baileys */}
        {showQRCode && selectedProvider === 'baileys' && (
          <div className="p-4 border-b border-gray-200 bg-blue-50">
            <div className="text-center">
              <h4 className="font-medium text-blue-900 mb-2">חיבור WhatsApp Web</h4>
              {connectionStatus === 'connecting' ? (
                <div>
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                  <p className="text-sm text-blue-600">יוצר קוד QR...</p>
                </div>
              ) : qrCode ? (
                <div data-testid="qr-code-container">
                  <div className="bg-white p-3 rounded-lg inline-block mb-2">
                    {qrImageUrl ? (
                      <img src={qrImageUrl} alt="QR Code WhatsApp" className="w-32 h-32" data-testid="qr-code-image" />
                    ) : (
                      <div className="w-32 h-32 bg-gray-200 flex items-center justify-center text-xs text-gray-500 font-mono break-all p-1">
                        {qrCode.substring(0, 50)}...
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-blue-600">סרוק עם WhatsApp במכשיר שלך</p>
                  <button 
                    onClick={() => setShowQRCode(false)}
                    className="mt-2 text-xs text-blue-500 underline"
                    data-testid="button-close-qr"
                  >
                    סגור
                  </button>
                </div>
              ) : (
                <button 
                  onClick={fetchQRCode}
                  className="bg-blue-600 text-white px-4 py-2 rounded text-sm"
                >
                  צור קוד QR
                </button>
              )}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mx-auto mb-4"></div>
                <p className="text-gray-600">טוען שיחות...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-red-600 mb-2">{error}</p>
                <Button onClick={() => fetchConversation()} variant="secondary" size="sm">
                  נסה שוב
                </Button>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-gray-500">
                <p>אין הודעות</p>
                <p className="text-sm mt-1">שלח הודעה ראשונה להתחיל שיחה</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.direction === 'out' ? 'justify-end' : 'justify-start'}`}
                  data-testid={`message-${message.direction}-${message.id}`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                      message.direction === 'out'
                        ? message.status === 'failed'
                          ? 'bg-red-100 text-red-800 border border-red-200'
                          : 'bg-green-500 text-white'
                        : 'bg-white text-gray-900 border border-gray-200'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content_text}</p>
                    <div className={`flex items-center justify-between mt-1 text-xs ${
                      message.direction === 'out' && message.status !== 'failed' 
                        ? 'text-green-100' 
                        : 'text-gray-500'
                    }`}>
                      <span>{formatDate(message.sent_at)}</span>
                      {message.direction === 'out' && (
                        <span className="ml-2">
                          {getMessageStatusIcon(message.status)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 bg-white">
          {error && (
            <div className="mb-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}
          {/* AI Status Banner */}
          {!aiEnabled && (
            <div className="mb-2 p-2 bg-orange-50 border border-orange-200 rounded text-orange-700 text-sm flex items-center gap-2">
              <BotOff className="w-4 h-4" />
              <span>AI מושבת - הודעות לא ייענו אוטומטית</span>
            </div>
          )}
          <div className="flex items-center space-x-2">
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={handleAttachClick}
              data-testid="button-whatsapp-attach"
            >
              <Paperclip className="w-4 h-4" />
            </Button>
            <div className="flex-1">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="הקלד הודעה..."
                disabled={sending}
                className="border-0 focus:ring-0 bg-gray-50"
                data-testid="input-whatsapp-message"
              />
            </div>
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={handleEmojiClick}
              data-testid="button-whatsapp-emoji"
            >
              <Smile className="w-4 h-4" />
            </Button>
            <Button
              onClick={sendMessage}
              disabled={!newMessage.trim() || sending}
              size="sm"
              className="bg-green-500 hover:bg-green-600 text-white"
              data-testid="button-whatsapp-send"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}