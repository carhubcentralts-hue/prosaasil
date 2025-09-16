import React, { useState, useEffect } from 'react';
import { MessageSquare, Users, Settings, Phone, QrCode, RefreshCw, Send, Bot, Smartphone, Server } from 'lucide-react';
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
}

interface QRCodeData {
  success: boolean;
  qr?: string;
  status?: string;
  message?: string;
  error?: string;
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
  const [selectedPrompt, setSelectedPrompt] = useState('');
  const [prompts, setPrompts] = useState<any[]>([]);
  
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

  const loadWhatsAppStatus = async () => {
    try {
      const response = await http.get<WhatsAppStatus>('/api/whatsapp/status');
      setWhatsappStatus(response);
    } catch (error) {
      console.error('Error loading WhatsApp status:', error);
    }
  };

  const loadThreads = async () => {
    try {
      setLoading(true);
      // TODO: Replace with real API call to get WhatsApp threads
      // const response = await http.get('/api/whatsapp/threads');
      
      // Mock data for now - will be replaced with real API
      await new Promise(resolve => setTimeout(resolve, 500));
      setThreads([
        {
          id: '1',
          name: 'יוסי כהן',
          phone: '+972501234567',
          lastMessage: 'שלום, מעוניין בדירה',
          unread: 2,
          time: '10:30'
        },
        {
          id: '2', 
          name: 'רחל לוי',
          phone: '+972507654321',
          lastMessage: 'תודה על המידע',
          unread: 0,
          time: '09:15'
        }
      ]);
    } catch (error) {
      console.error('Error loading threads:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPrompts = async () => {
    try {
      // TODO: Replace with real API call to get AI prompts
      // const response = await http.get('/api/ai-prompts');
      
      // Mock data for now
      setPrompts([
        { id: '1', name: 'בוט נדל״ן כללי', active: true },
        { id: '2', name: 'בוט השכרה', active: false },
        { id: '3', name: 'בוט מכירה', active: false }
      ]);
      setSelectedPrompt('1');
    } catch (error) {
      console.error('Error loading prompts:', error);
    }
  };

  const generateQRCode = async () => {
    if (selectedProvider !== 'baileys') {
      alert('QR קוד זמין רק לספק Baileys');
      return;
    }
    
    try {
      setQrLoading(true);
      const response = await http.get<QRCodeData>('/api/whatsapp/baileys/qr');
      
      if (response.success && response.qr) {
        setQrCode(response.qr);
        setShowQR(true);
      } else {
        alert('שגיאה ביצירת QR קוד: ' + (response.error || 'שגיאה לא ידועה'));
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
      const response = await http.post<{success: boolean; error?: string}>('/api/whatsapp/send', {
        to: selectedThread.phone,
        message: messageText,
        provider: selectedProvider
      });
      
      if (response.success) {
        setMessageText('');
        // TODO: Update thread with new message
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

  // Function to save prompt
  const savePrompt = async () => {
    if (!editingPrompt.trim()) return;
    
    try {
      setSavingPrompt(true);
      
      // Call backend API to save prompt
      const response = await http.put<{success: boolean; error?: string}>('/api/business/current/prompt', {
        whatsapp_prompt: editingPrompt.trim()
      });
      
      if (response.success) {
        // Reload prompts
        await loadPrompts();
        setShowPromptEditor(false);
        setEditingPrompt('');
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
    const currentPrompt = prompts.find(p => p.id === selectedPrompt);
    setEditingPrompt(currentPrompt?.content || '');
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
        <div className="flex gap-3">
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
                פרומפט פעיל
              </label>
              <select
                value={selectedPrompt}
                onChange={(e) => setSelectedPrompt(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md"
                data-testid="select-prompt"
              >
                {prompts.map((prompt) => (
                  <option key={prompt.id} value={prompt.id}>
                    {prompt.name}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>שים לב:</strong> הבוט יגיב אוטומטית להודעות נכנסות לפי הפרומפט שנבחר
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
            
            <div className="space-y-2">
              {threads.map((thread) => (
                <div
                  key={thread.id}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedThread?.id === thread.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-slate-50'
                  }`}
                  onClick={() => setSelectedThread(thread)}
                  data-testid={`thread-${thread.id}`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <h3 className="font-medium text-slate-900">{thread.name}</h3>
                    <span className="text-xs text-slate-500">{thread.time}</span>
                  </div>
                  <p className="text-sm text-slate-600 mb-2">{thread.phone}</p>
                  <div className="flex justify-between items-center">
                    <p className="text-sm text-slate-700 truncate flex-1">
                      {thread.lastMessage}
                    </p>
                    {thread.unread > 0 && (
                      <Badge variant="destructive" className="ml-2">
                        {thread.unread}
                      </Badge>
                    )}
                  </div>
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
                  <p className="text-xs mt-2">בקרוב: תמליל שיחות קוליות ותצוגת הודעות מלאה</p>
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
                {prompts.find(p => p.id === selectedPrompt)?.name.split(' ')[1] || 'כללי'}
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
                  <img src={qrCode} alt="QR Code" className="mx-auto mb-2" data-testid="img-qr" />
                  <p className="text-sm text-slate-600">
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