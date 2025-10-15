import React, { useState, useEffect } from 'react';
import { MessageSquare, Users, Settings, Phone, QrCode, RefreshCw, Send, Bot, Smartphone, Server } from 'lucide-react';
import QRCodeReact from 'react-qr-code';
import { http } from '../../services/http';

// Temporary UI components
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700 disabled:hover:bg-blue-600",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      disabled={disabled}
      {...props}
    >
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
    default: "bg-gray-100 text-gray-800",
    secondary: "bg-gray-100 text-gray-800", 
    destructive: "bg-red-100 text-red-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Interface definitions
interface WhatsAppStatus {
  provider: string;
  ready: boolean;
  connected: boolean;
  configured: boolean;
}

interface WhatsAppThread {
  id: string;
  name: string;
  phone: string;
  lastMessage: string;
  unread: number;
  time: string;
  summary?: string;
  is_closed?: boolean;
}

interface QRCodeData {
  success?: boolean; // Optional - not all providers return this
  qr?: string; // Baileys format
  qr_data?: string; // Unified format  
  dataUrl?: string; // Base64 QR image format
  qrText?: string; // QR text format (new)
  status?: string;
  message?: string;
  error?: string;
  source?: string;
  fallback_mode?: boolean;
  ready?: boolean; // Connection status
}

export function WhatsAppPage() {
  // State management
  const [loading, setLoading] = useState(true);
  const [threads, setThreads] = useState<WhatsAppThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<WhatsAppThread | null>(null);
  const [whatsappStatus, setWhatsappStatus] = useState<WhatsAppStatus>({
    provider: 'unknown',
    ready: false,
    connected: false,
    configured: false
  });
  const [selectedProvider, setSelectedProvider] = useState<'twilio' | 'baileys'>('twilio');
  const [qrCode, setQrCode] = useState<string>('');
  const [showQR, setShowQR] = useState(false);
  const [qrLoading, setQrLoading] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  
  // Settings and prompt editing state
  const [showSettings, setShowSettings] = useState(false);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);

  // Load initial data
  useEffect(() => {
    loadWhatsAppStatus();
    loadThreads();
    loadPrompts();
  }, []);

  // Poll status/QR only - no start calls in loop
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    
    if (showQR && qrCode && !whatsappStatus.connected) {
      console.log('🔄 Starting QR auto-refresh interval');
      interval = setInterval(async () => {
        try {
          const statusResponse = await http.get<WhatsAppStatus>('/api/whatsapp/status');
          if (statusResponse.connected) {
            console.log('✅ WhatsApp connected - stopping QR refresh');
            setShowQR(false);
            setQrCode('');
            setWhatsappStatus(statusResponse);
            return;
          }
          
          const qrResponse = await getQRCode();
          const qrData = qrResponse?.dataUrl || qrResponse?.qrText;
          if (qrData && qrData !== qrCode) {
            console.log('🔄 QR code refreshed');
            setQrCode(qrData);
          }
        } catch (error) {
          console.warn('❌ QR auto-refresh failed:', error);
        }
      }, 2500); // Poll every 2.5s
    }
    
    return () => {
      if (interval) {
        console.log('🛑 Stopping QR auto-refresh interval');
        clearInterval(interval);
      }
    };
  }, [showQR, qrCode, whatsappStatus.connected]);

  const loadWhatsAppStatus = async () => {
    try {
      const response = await http.get<WhatsAppStatus>('/api/whatsapp/status');
      setWhatsappStatus(response);
      // No auto-start - let user manually trigger with QR button
    } catch (error) {
      console.error('Error loading WhatsApp status:', error);
    }
  };

  const loadThreadSummary = async (threadId: string) => {
    // Check if thread is closed
    const thread = threads.find(t => t.id === threadId);
    if (!thread?.is_closed) {
      return; // Don't load summary for active conversations
    }
    
    // Check if already loaded
    if (thread?.summary && thread.summary !== 'לחץ לצפייה בסיכום') {
      return; // Already loaded
    }
    
    try {
      // Update to loading state
      setThreads(prevThreads => 
        prevThreads.map(t => 
          t.id === threadId ? { ...t, summary: 'טוען...' } : t
        )
      );
      
      const response = await http.get<{summary: string}>(`/api/crm/threads/${threadId}/summary`);
      
      // Update thread with summary
      setThreads(prevThreads => 
        prevThreads.map(t => 
          t.id === threadId ? { ...t, summary: response.summary } : t
        )
      );
    } catch (error) {
      console.error('Error loading summary for thread:', threadId, error);
      setThreads(prevThreads => 
        prevThreads.map(t => 
          t.id === threadId ? { ...t, summary: 'שגיאה בטעינת סיכום' } : t
        )
      );
    }
  };

  const loadThreads = async () => {
    try {
      setLoading(true);
      // Load real WhatsApp threads from database
      const response = await http.get<{threads: any[]}>('/api/crm/threads');
      
      // Transform API response to match UI interface
      const transformedThreads = (response.threads || []).map((thread: any) => ({
        id: thread.id?.toString() || '',
        name: thread.name || thread.peer_name || thread.phone_e164 || 'לא ידוע',
        phone: thread.phone_e164 || thread.phone || '',
        lastMessage: thread.lastMessage || thread.last_message || '',
        unread: thread.unread_count || thread.unread || 0,
        time: thread.time || (thread.last_activity ? new Date(thread.last_activity).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }) : ''),
        is_closed: thread.is_closed || false,
        summary: thread.is_closed ? 'לחץ לצפייה בסיכום' : undefined  // Only for closed conversations
      }));
      
      setThreads(transformedThreads);
    } catch (error) {
      console.error('Error loading threads:', error);
      // Fallback to empty array if API fails
      setThreads([]);
    } finally {
      setLoading(false);
    }
  };

  const loadPrompts = async () => {
    try {
      // Load real AI prompt from database
      const response = await http.get<{calls_prompt: string, whatsapp_prompt: string, version: number}>('/api/business/current/prompt');
      
      // Set the WhatsApp prompt as the editing content
      setEditingPrompt(response.whatsapp_prompt || '');
    } catch (error) {
      console.error('Error loading prompts:', error);
      // Fallback to empty state if API fails
      setEditingPrompt('');
    }
  };

  // Unified QR retrieval function with all fallbacks
  const getQRCode = async (): Promise<QRCodeData | null> => {
    const endpoints = ['/api/whatsapp/qr'];
    
    for (const endpoint of endpoints) {
      try {
        console.log(`🔍 Trying ${endpoint}...`);
        const response = await http.get<QRCodeData>(endpoint);
        console.log(`✅ Response from ${endpoint}:`, response);
        
        // Check if we got valid QR data (support both dataUrl and qrText)
        if (response.dataUrl || response.qrText || response.status === 'connected') {
          return response;
        }
      } catch (error) {
        console.warn(`❌ ${endpoint} failed:`, error);
      }
    }
    
    return null;
  };

  const disconnectWhatsApp = async () => {
    try {
      console.log('🔌 Disconnecting WhatsApp...');
      const response = await http.post('/api/whatsapp/disconnect', {});
      console.log('✅ WhatsApp disconnected:', response);
      
      // Reset local state
      setQrCode('');
      setShowQR(false);
      setWhatsappStatus({ provider: 'baileys', ready: false, connected: false, configured: true });
      
      alert('WhatsApp נותק בהצלחה! כעת תוכל/י ליצור QR חדש.');
    } catch (error: any) {
      console.error('❌ Disconnect failed:', error);
      alert('שגיאה בניתוק WhatsApp: ' + (error?.message || 'שגיאה לא ידועה'));
    }
  };

  const generateQRCode = async () => {
    if (selectedProvider !== 'baileys') {
      alert('QR קוד זמין רק לספק Baileys');
      return;
    }
    
    try {
      setQrLoading(true);
      console.log('🔄 Generating QR code for provider:', selectedProvider);
      
      // Single start call - no duplicates!
      await http.post('/api/whatsapp/start', { provider: selectedProvider });
      
      // Start polling for status/QR - no looping on start!
      const pollForQR = async () => {
        const statusResponse = await http.get<WhatsAppStatus>('/api/whatsapp/status');
        if (statusResponse.connected) {
          alert('WhatsApp כבר מחובר למערכת');
          return true; // Stop polling
        }
        
        const qrResponse = await getQRCode();
        const qrData = qrResponse?.dataUrl || qrResponse?.qrText;
        if (qrData) {
          setQrCode(qrData);
          setShowQR(true);
          console.log('✅ QR Code received and set for display');
          return true; // Stop polling
        }
        return false; // Continue polling
      };
      
      // Poll up to 10 times with 2.5s intervals
      let attempts = 0;
      const maxAttempts = 10;
      
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, attempts === 0 ? 500 : 2500));
        const success = await pollForQR();
        if (success) break;
        attempts++;
      }
      
      if (attempts >= maxAttempts) {
        alert('לא ניתן היה ליצור QR קוד. נסה שוב מאוחר יותר.');
      }
    } catch (error: any) {
      console.error('Error generating QR code:', error);
      alert('שגיאה ביצירת QR קוד: ' + (error.message || 'שגיאת רשת'));
    } finally {
      setQrLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!selectedThread || !messageText.trim()) return;
    
    try {
      setSendingMessage(true);
      const response = await http.post<{success: boolean; error?: string}>(`/api/crm/threads/${selectedThread.id}/message`, {
        text: messageText.trim(),
        provider: selectedProvider
      });
      
      if (response.success) {
        setMessageText('');
        // Reload threads to get updated last message
        await loadThreads();
        alert('הודעה נשלחה בהצלחה');
      } else {
        alert('שגיאה בשליחת הודעה: ' + (response.error || 'שגיאה לא ידועה'));
      }
    } catch (error: any) {
      console.error('Error sending message:', error);
      alert('שגיאה בשליחת הודעה: ' + (error.message || 'שגיאת רשת'));
    } finally {
      setSendingMessage(false);
    }
  };

  // Function to save prompt - ✅ עכשיו שומר גם calls_prompt כדי לא לדרוס אותו!
  const savePrompt = async () => {
    if (!editingPrompt.trim()) return;
    
    try {
      setSavingPrompt(true);
      
      // ✅ קודם טוען את הפרומפט הנוכחי של calls
      const currentPrompt = await http.get<{calls_prompt: string, whatsapp_prompt: string}>('/api/business/current/prompt');
      
      // ✅ שולח גם calls וגם whatsapp כדי לא לדרוס!
      const response = await http.put<{success: boolean; error?: string}>('/api/business/current/prompt', {
        calls_prompt: currentPrompt.calls_prompt,  // ✅ שומר את ה-calls prompt
        whatsapp_prompt: editingPrompt.trim()      // ✅ מעדכן רק את ה-whatsapp
      });
      
      if (response.success) {
        // Reload prompts
        await loadPrompts();
        setShowPromptEditor(false);
        alert('פרומפט נשמר בהצלחה!');
      } else {
        alert('שגיאה בשמירת הפרומפט: ' + (response.error || 'שגיאה לא ידועה'));
      }
    } catch (error) {
      console.error('Error saving prompt:', error);
      alert('שגיאה בשמירת הפרומפט');
    } finally {
      setSavingPrompt(false);
    }
  };

  // Function to open prompt editor with current prompt
  const openPromptEditor = () => {
    setShowPromptEditor(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">טוען WhatsApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">WhatsApp Business</h1>
          <p className="text-slate-600 mt-1">נהל את כל שיחות WhatsApp במקום אחד</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <Button variant="outline" size="sm" onClick={() => setShowQR(true)} data-testid="button-qr">
            <QrCode className="h-4 w-4 ml-2" />
            QR קוד
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowSettings(true)} data-testid="button-settings">
            <Settings className="h-4 w-4 ml-2" />
            הגדרות
          </Button>
        </div>
      </div>

      {/* Provider & Bot Configuration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Provider Selection */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
            <Server className="h-5 w-5 ml-2" />
            בחירת ספק WhatsApp
          </h2>
          
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="provider"
                  value="twilio"
                  checked={selectedProvider === 'twilio'}
                  onChange={(e) => setSelectedProvider(e.target.value as 'twilio')}
                  className="ml-2"
                  data-testid="radio-twilio"
                />
                <div className="flex items-center">
                  <Smartphone className="h-4 w-4 ml-2" />
                  Twilio WhatsApp Business API
                </div>
              </label>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="provider"
                  value="baileys"
                  checked={selectedProvider === 'baileys'}
                  onChange={(e) => setSelectedProvider(e.target.value as 'baileys')}
                  className="ml-2"
                  data-testid="radio-baileys"
                />
                <div className="flex items-center">
                  <QrCode className="h-4 w-4 ml-2" />
                  Baileys (WhatsApp Web)
                </div>
              </label>
            </div>

            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-sm text-slate-600">
                <strong>סטטוס חיבור:</strong> 
                <Badge 
                  variant={whatsappStatus.connected ? "success" : "warning"} 
                  className="mr-2"
                  data-testid="status-connection"
                >
                  {whatsappStatus.connected ? "מחובר" : "לא מחובר"}
                </Badge>
              </p>
              <p className="text-sm text-slate-600 mt-1">
                <strong>ספק נוכחי:</strong> {whatsappStatus.provider}
              </p>
            </div>

            {selectedProvider === 'baileys' && (
              <div className="space-y-3">
                <Button 
                  onClick={generateQRCode} 
                  disabled={qrLoading}
                  className="w-full"
                  data-testid="button-generate-qr"
                >
                  {qrLoading ? (
                    <RefreshCw className="h-4 w-4 ml-2 animate-spin" />
                  ) : (
                    <QrCode className="h-4 w-4 ml-2" />
                  )}
                  {qrLoading ? "יוצר QR קוד..." : "צור QR קוד חדש"}
                </Button>
                
                <Button 
                  variant="destructive"
                  onClick={disconnectWhatsApp} 
                  className="w-full"
                  data-testid="button-disconnect"
                >
                  <RefreshCw className="h-4 w-4 ml-2" />
                  נתק חיבור מלא
                </Button>
              </div>
            )}
          </div>
        </Card>

        {/* Bot Prompt Selection */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
            <Bot className="h-5 w-5 ml-2" />
            הגדרות בוט WhatsApp
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                פרומפט WhatsApp נוכחי
              </label>
              <div className="p-3 border border-slate-200 rounded-lg bg-slate-50 max-h-32 overflow-y-auto">
                <p className="text-sm text-slate-700 whitespace-pre-wrap">
                  {editingPrompt || 'אין פרומפט מוגדר'}
                </p>
              </div>
            </div>
            
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>שים לב:</strong> הבוט יגיב אוטומטית להודעות נכנסות לפי הפרומפט שמוגדר
              </p>
            </div>

            <Button variant="outline" className="w-full" onClick={openPromptEditor} data-testid="button-edit-prompt">
              <Settings className="h-4 w-4 ml-2" />
              ערוך פרומפט
            </Button>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversations List */}
        <div className="lg:col-span-1">
          <Card className="p-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-slate-900">שיחות</h2>
              <Badge variant="secondary">{threads.length}</Badge>
            </div>
            
            <div className="space-y-3">
              {threads.map((thread) => (
                <div
                  key={thread.id}
                  className={`p-4 rounded-lg cursor-pointer transition-all border ${
                    selectedThread?.id === thread.id
                      ? 'bg-blue-50 border-blue-300 shadow-sm'
                      : 'bg-white border-slate-200 hover:bg-slate-50 hover:border-slate-300'
                  }`}
                  onClick={() => {
                    setSelectedThread(thread);
                    loadThreadSummary(thread.id);  // Load summary on click
                  }}
                  data-testid={`thread-${thread.id}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-slate-900 text-base">{thread.name}</h3>
                        {thread.is_closed && (
                          <Badge variant="success" className="text-xs">
                            נסגרה
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{thread.phone}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className="text-xs text-slate-500">{thread.time}</span>
                      {thread.unread > 0 && (
                        <Badge variant="destructive" className="ml-2">
                          {thread.unread}
                        </Badge>
                      )}
                    </div>
                  </div>
                  
                  {/* AI Summary - Only for closed conversations */}
                  {thread.is_closed && thread.summary && (
                    <div className="mt-2 pt-2 border-t border-slate-100">
                      <div className="flex items-start gap-2">
                        <MessageSquare className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-slate-700 leading-snug flex-1">
                          {thread.summary}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {threads.length === 0 && (
                <div className="text-center py-8 text-slate-500">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2" />
                  <p>אין שיחות פעילות</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Chat Area */}
        <div className="lg:col-span-2">
          {selectedThread ? (
            <Card className="p-0 h-96">
              {/* Chat Header */}
              <div className="p-4 border-b border-slate-200">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-semibold text-slate-900">{selectedThread.name}</h3>
                    <p className="text-sm text-slate-500">{selectedThread.phone}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" data-testid="button-call">
                      <Phone className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Messages Area */}
              <div className="flex-1 p-4 min-h-0 overflow-y-auto">
                <div className="text-center py-8 text-slate-500">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2" />
                  <p>טען את ההודעות...</p>
                  <p className="text-xs mt-2">מערכת ההודעות תוצג כאן עם קישור לשיחה</p>
                </div>
              </div>

              {/* Message Input */}
              <div className="p-4 border-t border-slate-200">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="כתוב הודעה..."
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-md"
                    dir="rtl"
                    data-testid="input-message"
                  />
                  <Button 
                    size="sm" 
                    onClick={sendMessage}
                    disabled={sendingMessage || !messageText.trim()}
                    data-testid="button-send-message"
                  >
                    {sendingMessage ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="p-8 text-center">
              <MessageSquare className="h-12 w-12 mx-auto mb-4 text-slate-400" />
              <h3 className="font-semibold text-slate-900 mb-2">בחר שיחה</h3>
              <p className="text-slate-600">בחר שיחה מהרשימה כדי להתחיל לצ'אט</p>
            </Card>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-green-100 rounded-full ml-3">
              <MessageSquare className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">הודעות היום</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-messages">47</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-full ml-3">
              <Users className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">שיחות פעילות</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-threads">{threads.length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-yellow-100 rounded-full ml-3">
              <MessageSquare className="h-5 w-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">ממתינות לטיפול</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-pending">3</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center">
            <div className="p-2 bg-purple-100 rounded-full ml-3">
              <Bot className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">בוט פעיל</p>
              <p className="text-2xl font-bold text-slate-900" data-testid="stat-bot">
                WhatsApp
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="modal-settings">
          <Card className="p-6 max-w-md mx-4 w-full">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-slate-900">הגדרות WhatsApp</h3>
              <Button variant="ghost" size="sm" onClick={() => setShowSettings(false)}>×</Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  ספק פעיל
                </label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value as 'twilio' | 'baileys')}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md"
                >
                  <option value="twilio">Twilio WhatsApp Business API</option>
                  <option value="baileys">Baileys (WhatsApp Web)</option>
                </select>
              </div>
              
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>סטטוס:</strong> {whatsappStatus.connected ? "מחובר" : "לא מחובר"}
                </p>
                <p className="text-sm text-blue-800 mt-1">
                  <strong>ספק נוכחי:</strong> {whatsappStatus.provider}
                </p>
              </div>
              
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => setShowSettings(false)}
                  className="flex-1"
                >
                  בטל
                </Button>
                <Button 
                  onClick={() => {
                    setShowSettings(false);
                    loadWhatsAppStatus(); // Refresh status after changes
                  }}
                  className="flex-1"
                >
                  שמור
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Prompt Editor Modal */}
      {showPromptEditor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="modal-prompt-editor">
          <Card className="p-6 max-w-2xl mx-4 w-full">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-slate-900">עריכת פרומפט WhatsApp</h3>
              <Button variant="ghost" size="sm" onClick={() => setShowPromptEditor(false)}>×</Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  תוכן הפרומפט
                </label>
                <textarea
                  value={editingPrompt}
                  onChange={(e) => setEditingPrompt(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md h-32"
                  placeholder="הכנס את הפרומפט לבוט WhatsApp..."
                  data-testid="textarea-prompt"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {editingPrompt.length} תווים
                </p>
              </div>
              
              <div className="p-3 bg-yellow-50 rounded-lg">
                <p className="text-sm text-yellow-800">
                  <strong>שים לב:</strong> שינויים בפרומפט יחולו מיידית על כל ההודעות החדשות
                </p>
              </div>
              
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => setShowPromptEditor(false)}
                  className="flex-1"
                >
                  בטל
                </Button>
                <Button 
                  onClick={savePrompt}
                  disabled={savingPrompt || !editingPrompt.trim()}
                  className="flex-1"
                >
                  {savingPrompt ? "שומר..." : "שמור פרומפט"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* QR Code Modal */}
      {showQR && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" data-testid="modal-qr">
          <Card className="p-6 max-w-sm mx-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">
                QR קוד לחיבור WhatsApp
              </h3>
              
              {qrCode ? (
                <div className="mb-4">
                  {qrCode.startsWith('data:image/') ? (
                    // Legacy base64 image support
                    <img src={qrCode} alt="QR Code" className="mx-auto mb-2 w-48 h-48" data-testid="img-qr" />
                  ) : (
                    // New QR string rendering with react-qr-code
                    <div className="bg-white p-4 rounded-lg mx-auto w-fit">
                      <QRCodeReact
                        value={qrCode}
                        size={192}
                        level="M"
                        data-testid="qr-component"
                      />
                    </div>
                  )}
                  <p className="text-sm text-slate-600 mt-2">
                    סרוק עם WhatsApp שלך כדי להתחבר
                  </p>
                </div>
              ) : (
                <div className="mb-4">
                  <div className="w-48 h-48 bg-slate-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                    <QrCode className="h-16 w-16 text-slate-400" />
                  </div>
                  <p className="text-sm text-slate-600">
                    לחץ על "צור QR קוד" כדי להתחיל
                  </p>
                </div>
              )}
              
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => setShowQR(false)}
                  className="flex-1"
                  data-testid="button-close-qr"
                >
                  סגור
                </Button>
                {!qrCode && (
                  <Button 
                    onClick={generateQRCode}
                    disabled={qrLoading}
                    className="flex-1"
                    data-testid="button-generate-qr-modal"
                  >
                    {qrLoading ? "יוצר..." : "צור QR קוד"}
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}