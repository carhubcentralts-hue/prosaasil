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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען שיחות WhatsApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50" dir="rtl">
      {/* כותרת */}
      <div className="bg-white shadow-xl border-b-4 border-green-500">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <button
                onClick={() => navigate('/business/dashboard')}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-xl transition-all text-gray-700 font-hebrew shadow-md"
              >
                <ArrowLeft className="w-5 h-5" />
                חזרה לדשבורד
              </button>
              <div>
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
                      className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-green-50 transition-colors ${
                        selectedConversation?.id === conversation.id ? 'bg-green-100 border-r-4 border-r-green-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-gray-900 font-hebrew">
                          {conversation.customer_name}
                        </h4>
                        <div className={`w-3 h-3 rounded-full ${
                          conversation.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                        }`}></div>
                      </div>
                      <p className="text-sm text-gray-600 font-hebrew mb-1">
                        {conversation.customer_number}
                      </p>
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span className="flex items-center gap-1">
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
                  <div className="p-8 text-center text-gray-500 font-hebrew">
                    {searchTerm ? 'לא נמצאו שיחות מתאימות' : 'אין שיחות פעילות'}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* פרטי שיחה */}
          <div className="lg:col-span-2">
            {selectedConversation ? (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200">
                <div className="p-6 border-b border-gray-200 bg-green-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 font-hebrew mb-1">
                        {selectedConversation.customer_name}
                      </h3>
                      <p className="text-gray-600 font-hebrew">
                        {selectedConversation.customer_number}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <button className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 font-hebrew">
                        <Send className="w-4 h-4" />
                        שלח הודעה
                      </button>
                      <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 font-hebrew">
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