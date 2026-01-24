/**
 * Prompt Builder Chat - Natural Conversational Interface
 * Creates prompts through free-form conversation instead of questionnaires
 * 
 * Key Features:
 * - Natural conversation flow
 * - No structured questions
 * - AI intelligently gathers information
 * - Automatically generates prompt when ready
 * - Resilient - always produces a result
 */
import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageCircle, 
  X, 
  Loader2,
  Save,
  Send,
  RotateCcw,
  CheckCircle2,
  Sparkles
} from 'lucide-react';
import { http } from '../../services/http';

// Types
interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface PromptBuilderChatProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (promptText: string, channel: 'calls' | 'whatsapp', metadata?: any) => void;
  initialChannel?: 'calls' | 'whatsapp';
}

export function PromptBuilderChat({ 
  isOpen, 
  onClose, 
  onSave, 
  initialChannel = 'calls' 
}: PromptBuilderChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [generatedPrompt, setGeneratedPrompt] = useState('');
  const [promptSummary, setPromptSummary] = useState('');
  const [selectedChannel, setSelectedChannel] = useState<'calls' | 'whatsapp'>(initialChannel);
  const [error, setError] = useState('');
  const [showPrompt, setShowPrompt] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Start with a welcoming message
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: 'assistant',
        content: 'היי! אני כאן כדי לעזור לך ליצור פרומפט מותאם לעסק שלך. ספר לי קצת על העסק — מה אתם עושים ומי הלקוחות שלכם?',
        timestamp: new Date()
      }]);
    }
  }, [isOpen]);

  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    // Focus input when opened
    if (isOpen && !showPrompt) {
      inputRef.current?.focus();
    }
  }, [isOpen, showPrompt]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || sending) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSending(true);
    setError('');

    // Add user message to conversation
    const newUserMessage: Message = {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, newUserMessage]);

    try {
      // Build conversation history for API
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const result = await http.post<{
        success: boolean;
        response: string;
        prompt_generated: boolean;
        prompt_text?: string;
        summary?: string;
        error?: string;
      }>(
        '/api/ai/prompt_builder_chat/message',
        {
          message: userMessage,
          conversation_history: conversationHistory
        }
      );

      if (result.success) {
        // Add assistant response
        const assistantMessage: Message = {
          role: 'assistant',
          content: result.response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);

        // Check if a prompt was generated
        if (result.prompt_generated && result.prompt_text) {
          setGeneratedPrompt(result.prompt_text);
          setPromptSummary(result.summary || '');
          setShowPrompt(true);
        }
      } else {
        setError(result.error || 'שגיאה בשליחת ההודעה');
      }
    } catch (err: any) {
      console.error('Failed to send message:', err);
      setError(err.message || 'שגיאה בשליחת ההודעה');
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleReset = async () => {
    try {
      await http.post('/api/ai/prompt_builder_chat/reset', {});
      setMessages([{
        role: 'assistant',
        content: 'בואו נתחיל מחדש! ספר לי על העסק שלך.',
        timestamp: new Date()
      }]);
      setGeneratedPrompt('');
      setPromptSummary('');
      setShowPrompt(false);
      setError('');
    } catch (err: any) {
      console.error('Failed to reset:', err);
    }
  };

  const handleSave = () => {
    onSave(generatedPrompt, selectedChannel, {
      source: 'chat',
      summary: promptSummary
    });
    handleClose();
  };

  const handleClose = () => {
    onClose();
  };

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      // Reset state when modal is closed
      setMessages([]);
      setInputMessage('');
      setGeneratedPrompt('');
      setPromptSummary('');
      setShowPrompt(false);
      setError('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl max-w-4xl w-full h-[85vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-gradient-to-l from-blue-50 via-purple-50 to-white">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center shadow-lg">
              <MessageCircle className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                שיחה ליצירת פרומפט
                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                  חדש
                </span>
              </h2>
              <p className="text-sm text-slate-600">
                {showPrompt ? 'הפרומפט מוכן!' : 'נהל שיחה טבעית ליצירת פרומפט מותאם'}
              </p>
            </div>
          </div>
          <button 
            onClick={handleClose} 
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-4 mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {!showPrompt ? (
          <>
            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, idx) => (
                <div 
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}
                >
                  <div 
                    className={`
                      max-w-[75%] rounded-2xl px-4 py-3 shadow-sm
                      ${msg.role === 'user' 
                        ? 'bg-blue-500 text-white' 
                        : 'bg-slate-100 text-slate-900 border border-slate-200'}
                    `}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-100' : 'text-slate-400'}`}>
                      {msg.timestamp.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}
              
              {sending && (
                <div className="flex justify-end">
                  <div className="bg-slate-100 border border-slate-200 rounded-2xl px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                      <span className="text-sm text-slate-600">מקליד...</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-slate-200 bg-slate-50">
              <div className="flex gap-2">
                <button
                  onClick={handleReset}
                  className="p-3 hover:bg-slate-200 rounded-lg transition-colors flex-shrink-0"
                  title="התחל מחדש"
                >
                  <RotateCcw className="h-5 w-5 text-slate-600" />
                </button>
                <input
                  ref={inputRef}
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="כתוב כאן..."
                  disabled={sending}
                  className="flex-1 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || sending}
                  className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2 flex-shrink-0"
                >
                  <Send className="h-5 w-5" />
                  <span className="hidden sm:inline">שלח</span>
                </button>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Generated Prompt View */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {/* Success Banner */}
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-6 w-6 text-green-600 flex-shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-green-900">הפרומפט מוכן!</h3>
                    <p className="text-sm text-green-700 mt-1">{promptSummary}</p>
                  </div>
                </div>
              </div>

              {/* Generated Prompt */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הפרומפט שנוצר:
                </label>
                <textarea
                  value={generatedPrompt}
                  onChange={(e) => setGeneratedPrompt(e.target.value)}
                  className="w-full p-4 border border-slate-300 rounded-lg resize-none h-64 text-sm leading-relaxed focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  dir="rtl"
                />
                <p className="text-xs text-slate-500 mt-2">
                  {generatedPrompt.length} תווים • ניתן לעריכה
                </p>
              </div>

              {/* Channel Selection */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  שמור עבור ערוץ:
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className={`
                    flex items-center gap-2 cursor-pointer p-3 border-2 rounded-lg transition-all
                    ${selectedChannel === 'calls' 
                      ? 'border-blue-500 bg-white shadow-sm' 
                      : 'border-slate-200 hover:border-slate-300 bg-white'}
                  `}>
                    <input
                      type="radio"
                      name="channel"
                      value="calls"
                      checked={selectedChannel === 'calls'}
                      onChange={() => setSelectedChannel('calls')}
                      className="w-4 h-4 text-blue-600"
                      aria-label="שיחות טלפון"
                    />
                    <span className="text-slate-700" aria-hidden="true">📞 שיחות טלפון</span>
                  </label>
                  <label className={`
                    flex items-center gap-2 cursor-pointer p-3 border-2 rounded-lg transition-all
                    ${selectedChannel === 'whatsapp' 
                      ? 'border-blue-500 bg-white shadow-sm' 
                      : 'border-slate-200 hover:border-slate-300 bg-white'}
                  `}>
                    <input
                      type="radio"
                      name="channel"
                      value="whatsapp"
                      checked={selectedChannel === 'whatsapp'}
                      onChange={() => setSelectedChannel('whatsapp')}
                      className="w-4 h-4 text-blue-600"
                      aria-label="WhatsApp"
                    />
                    <span className="text-slate-700" aria-hidden="true">💬 WhatsApp</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowPrompt(false)}
                  className="flex items-center gap-2 px-4 py-2.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <MessageCircle className="h-4 w-4" />
                  חזרה לשיחה
                </button>
                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 px-4 py-2.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <RotateCcw className="h-4 w-4" />
                  התחל מחדש
                </button>
              </div>
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg font-medium"
              >
                <Save className="h-5 w-5" />
                שמור פרומפט
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default PromptBuilderChat;
