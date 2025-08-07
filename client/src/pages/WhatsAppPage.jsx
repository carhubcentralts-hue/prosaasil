import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  MessageSquare, 
  Phone, 
  Send, 
  Search, 
  ArrowLeft,
  Users,
  Clock,
  CheckCircle2
} from 'lucide-react';

const WhatsAppPage = () => {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.get('/api/whatsapp/conversations', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.data.success) {
        setConversations(response.data.conversations || []);
      }
    } catch (error) {
      console.error('Error loading conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredConversations = conversations.filter(conv =>
    conv.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.customer_number.includes(searchTerm)
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
        <div className="text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          </div>
          <h3 className="text-3xl font-bold text-gray-900 mb-2">💬 WhatsApp Business</h3>
          <p className="text-gray-600 text-lg">טוען שיחות ולקוחות...</p>
          <div className="mt-4 flex justify-center">
            <div className="bg-white rounded-full px-4 py-2 shadow-md">
              <span className="text-sm text-green-600 font-medium">אינטגרציה ישירה עם WhatsApp</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
      <div className="max-w-6xl mx-auto px-4 py-6">
        
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                💬 WhatsApp Business
              </h1>
              <p className="text-gray-600 text-lg mt-2">
                ניהול שיחות ולקוחות עם אינטגרציה ישירה לWhatsApp
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/admin/dashboard')}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-gray-500 to-gray-600 text-white rounded-xl hover:from-gray-600 hover:to-gray-700 shadow-lg transition-all"
              >
                <ArrowLeft className="w-5 h-5" />
                חזרה לדשבורד
              </button>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Search className="w-5 h-5 text-green-600" />
            חיפוש שיחות ולקוחות
          </h2>
          <div className="relative">
            <Search className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="חפש לפי שם לקוח או מספר טלפון..."
              className="w-full pr-12 pl-4 py-3 border border-gray-300 rounded-xl focus:ring-4 focus:ring-green-100 focus:border-green-500 transition-all"
              data-testid="input-search-conversations"
            />
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* שיחות */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-green-50 to-emerald-50">
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-3">
                  <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
                    <MessageSquare className="w-4 h-4 text-white" />
                  </div>
                  🗨️ שיחות פעילות ({filteredConversations.length})
                </h2>
              </div>
              <div className="max-h-96 overflow-y-auto">
                <h1 className="text-3xl font-bold text-green-600 font-hebrew mb-1">
                  💬 WhatsApp עסקי
                </h1>
                <p className="text-gray-600 font-hebrew">ניהול שיחות ותקשורת עם לקוחות</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* רשימת שיחות */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-lg border border-gray-200">
              <div className="p-4 border-b border-gray-200 bg-green-50">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900 font-hebrew">שיחות פעילות</h3>
                  <div className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-hebrew">
                    {conversations.length} שיחות
                  </div>
                </div>
                <div className="relative">
                  <Search className="absolute right-3 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="חיפוש שיחות..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pr-10 pl-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 font-hebrew"
                  />
                </div>
              </div>

              <div className="max-h-96 overflow-y-auto">
                {filteredConversations.length > 0 ? (
                  filteredConversations.map((conversation) => (
                    <div
                      key={conversation.id}
                      onClick={() => setSelectedConversation(conversation)}
                      className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-green-50 transition-all ${
                        selectedConversation?.id === conversation.id ? 'bg-green-100 border-r-4 border-r-green-500 shadow-inner' : ''
                      }`}
                      data-testid={`conversation-${conversation.id}`}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                          {conversation.customer_name?.charAt(0) || 'L'}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-semibold text-gray-900">
                            {conversation.customer_name}
                          </h4>
                          <p className="text-sm text-gray-600">
                            {conversation.customer_number}
                          </p>
                        </div>
                        <div className={`w-3 h-3 rounded-full ${
                          conversation.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                        }`}></div>
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded-full">
                          <MessageSquare className="w-3 h-3" />
                          {conversation.message_count} הודעות
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(conversation.last_message_time).toLocaleDateString('he-IL')}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-12 text-center">
                    <div className="w-16 h-16 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <MessageSquare className="w-6 h-6 text-gray-400" />
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">
                      {searchTerm ? '🔍 לא נמצאו שיחות' : '💬 אין שיחות פעילות'}
                    </h3>
                    <p className="text-gray-600">
                      {searchTerm ? 'נסה לשנות את החיפוש' : 'שיחות חדשות יופיעו כאן'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* פרטי שיחה */}
          <div className="lg:col-span-2">
            {selectedConversation ? (
              <div className="bg-white rounded-2xl shadow-lg border border-gray-100">
                <div className="p-8 border-b border-gray-200 bg-gradient-to-r from-green-50 to-emerald-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center text-white text-xl font-bold">
                        {selectedConversation.customer_name?.charAt(0) || 'L'}
                      </div>
                      <div>
                        <h3 className="text-2xl font-bold text-gray-900 mb-1">
                          {selectedConversation.customer_name}
                        </h3>
                        <p className="text-gray-600 flex items-center gap-2">
                          <Phone className="w-4 h-4" />
                          {selectedConversation.customer_number}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <button 
                        className="flex items-center gap-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-xl hover:from-green-700 hover:to-emerald-700 shadow-lg transition-all"
                        data-testid="button-send-whatsapp"
                      >
                        <Send className="w-4 h-4" />
                        שלח הודעה
                      </button>
                      <button 
                        className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-xl hover:from-blue-700 hover:to-blue-800 shadow-lg transition-all"
                        data-testid="button-make-call"
                      >
                        <Phone className="w-4 h-4" />
                        התקשר
                      </button>
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  <div className="mb-6">
                    <h4 className="font-bold text-gray-900 font-hebrew mb-3">הודעה אחרונה:</h4>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <p className="text-gray-800 font-hebrew mb-2">
                        "{selectedConversation.last_message}"
                      </p>
                      <p className="text-sm text-gray-500 font-hebrew">
                        {new Date(selectedConversation.last_message_time).toLocaleString('he-IL')}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <MessageSquare className="w-5 h-5 text-green-600" />
                        <h4 className="font-medium text-gray-900 font-hebrew">סך הודעות</h4>
                      </div>
                      <p className="text-2xl font-bold text-green-600">
                        {selectedConversation.message_count}
                      </p>
                    </div>

                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <CheckCircle2 className="w-5 h-5 text-blue-600" />
                        <h4 className="font-medium text-gray-900 font-hebrew">סטטוס</h4>
                      </div>
                      <p className={`text-sm font-medium font-hebrew ${
                        selectedConversation.status === 'active' ? 'text-green-600' : 'text-gray-600'
                      }`}>
                        {selectedConversation.status === 'active' ? 'פעיל' : 'ממתין'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 flex items-center justify-center h-96">
                <div className="text-center text-gray-500 font-hebrew">
                  <MessageSquare className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <h3 className="text-lg font-medium mb-2">בחר שיחה לצפייה</h3>
                  <p className="text-sm">לחץ על שיחה מהרשימה כדי לראות פרטים</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhatsAppPage;