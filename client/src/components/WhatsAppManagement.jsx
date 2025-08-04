import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  MessageSquare, 
  Send, 
  Phone, 
  Users, 
  Search,
  Filter,
  Plus,
  Settings,
  Smartphone,
  Globe,
  CheckCircle,
  Clock,
  AlertCircle,
  Download,
  Upload,
  MoreHorizontal,
  Image,
  Paperclip,
  Smile
} from 'lucide-react';

const WhatsAppManagement = ({ businessId, isAdmin = false }) => {
  const [conversations, setConversations] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [serviceType, setServiceType] = useState('twilio'); // twilio or baileys
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  useEffect(() => {
    fetchWhatsAppData();
    checkConnectionStatus();
  }, [businessId, searchTerm, statusFilter]);

  const fetchWhatsAppData = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter) params.append('status', statusFilter);
      
      const [conversationsRes, statsRes] = await Promise.all([
        axios.get(`/api/whatsapp/conversations?business_id=${businessId}&${params}`),
        axios.get(`/api/whatsapp/stats?business_id=${businessId}`)
      ]);

      setConversations(conversationsRes.data.conversations || []);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Error fetching WhatsApp data:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkConnectionStatus = async () => {
    try {
      const response = await axios.get(`/api/whatsapp/status?business_id=${businessId}`);
      setConnectionStatus(response.data.status);
      setServiceType(response.data.service_type || 'twilio');
    } catch (error) {
      console.error('Error checking WhatsApp status:', error);
    }
  };

  const fetchMessages = async (conversationId) => {
    try {
      const response = await axios.get(`/api/whatsapp/messages?conversation_id=${conversationId}`);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedConversation) return;

    try {
      await axios.post('/api/whatsapp/send', {
        business_id: businessId,
        conversation_id: selectedConversation.id,
        message: newMessage,
        service_type: serviceType
      });

      setNewMessage('');
      fetchMessages(selectedConversation.id);
      fetchWhatsAppData(); // Refresh conversations
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  const connectService = async (type) => {
    try {
      if (type === 'baileys') {
        const response = await axios.post('/api/whatsapp/baileys/connect', {
          business_id: businessId
        });
        if (response.data.qr_code) {
          // Show QR code modal
          setShowQRModal(true);
          setQRCode(response.data.qr_code);
        }
      } else {
        // Twilio connection (already configured)
        setServiceType('twilio');
        setConnectionStatus('connected');
      }
    } catch (error) {
      console.error('Error connecting service:', error);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'active': 'bg-green-100 text-green-800',
      'pending': 'bg-yellow-100 text-yellow-800',
      'resolved': 'bg-blue-100 text-blue-800',
      'closed': 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color = "blue" }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 font-hebrew">{title}</p>
          <p className={`text-3xl font-bold text-${color}-600 font-hebrew`}>{value}</p>
          {subtitle && <p className="text-sm text-gray-500 font-hebrew">{subtitle}</p>}
        </div>
        <div className={`w-12 h-12 bg-${color}-100 rounded-lg flex items-center justify-center`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
    </div>
  );

  const ConversationItem = ({ conversation, isSelected, onClick }) => (
    <div 
      className={`p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 ${
        isSelected ? 'bg-blue-50 border-r-4 border-blue-500' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-green-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 font-hebrew truncate">
              {conversation.customer_name || conversation.phone_number}
            </p>
            <p className="text-sm text-gray-500 font-hebrew truncate">
              {conversation.last_message}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500 font-hebrew">
            {new Date(conversation.updated_at).toLocaleTimeString('he-IL', {
              hour: '2-digit',
              minute: '2-digit'
            })}
          </p>
          {conversation.unread_count > 0 && (
            <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full">
              {conversation.unread_count}
            </span>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium font-hebrew ${getStatusColor(conversation.status)}`}>
          {conversation.status_hebrew || conversation.status}
        </span>
        <div className="flex items-center text-xs text-gray-500">
          <Smartphone className="w-3 h-3 ml-1" />
          <span className="font-hebrew">{serviceType === 'baileys' ? 'Baileys' : 'Twilio'}</span>
        </div>
      </div>
    </div>
  );

  const MessageBubble = ({ message }) => {
    const isFromBusiness = message.direction === 'outbound';
    
    return (
      <div className={`flex ${isFromBusiness ? 'justify-end' : 'justify-start'} mb-4`}>
        <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
          isFromBusiness 
            ? 'bg-blue-500 text-white' 
            : 'bg-gray-200 text-gray-800'
        }`}>
          <p className="text-sm font-hebrew">{message.content}</p>
          <p className={`text-xs mt-1 ${
            isFromBusiness ? 'text-blue-100' : 'text-gray-500'
          } font-hebrew`}>
            {new Date(message.created_at).toLocaleTimeString('he-IL', {
              hour: '2-digit',
              minute: '2-digit'
            })}
          </p>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני WhatsApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 font-hebrew">ניהול WhatsApp</h1>
            <p className="text-gray-600 font-hebrew">ניהול שיחות ומסרים במערכת מתקדמת</p>
          </div>
          <div className="flex gap-3">
            <div className={`px-3 py-2 rounded-lg text-sm font-hebrew ${
              connectionStatus === 'connected' 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              {connectionStatus === 'connected' ? 'מחובר' : 'מנותק'}
            </div>
            <button 
              onClick={() => connectService('twilio')}
              className={`px-4 py-2 rounded-lg font-hebrew ${
                serviceType === 'twilio' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Twilio API
            </button>
            <button 
              onClick={() => connectService('baileys')}
              className={`px-4 py-2 rounded-lg font-hebrew ${
                serviceType === 'baileys' 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Baileys (WhatsApp Web)
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard 
            title="סך שיחות" 
            value={stats.total_conversations || 0}
            subtitle="כל השיחות"
            icon={MessageSquare} 
            color="green" 
          />
          <StatCard 
            title="מסרים היום" 
            value={stats.today_messages || 0}
            subtitle="מסרים היום"
            icon={Send} 
            color="blue" 
          />
          <StatCard 
            title="ממתינים למענה" 
            value={stats.pending_conversations || 0}
            subtitle="שיחות פתוחות"
            icon={Clock} 
            color="yellow" 
          />
          <StatCard 
            title="זמן מענה ממוצע" 
            value={`${stats.avg_response_time || 0} דק'`}
            subtitle="השבוע האחרון"
            icon={CheckCircle} 
            color="purple" 
          />
        </div>

        {/* Main Interface */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="flex h-[600px]">
            
            {/* Conversations List */}
            <div className="w-1/3 border-l border-gray-200">
              <div className="p-4 border-b border-gray-200">
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    placeholder="חיפוש שיחות..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent font-hebrew"
                  />
                </div>
                <div className="mt-3">
                  <select 
                    value={statusFilter} 
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 font-hebrew"
                  >
                    <option value="">כל הסטטוסים</option>
                    <option value="active">פעיל</option>
                    <option value="pending">ממתין</option>
                    <option value="resolved">נפתר</option>
                    <option value="closed">סגור</option>
                  </select>
                </div>
              </div>
              
              <div className="overflow-y-auto" style={{ height: 'calc(600px - 120px)' }}>
                {conversations.map((conversation) => (
                  <ConversationItem
                    key={conversation.id}
                    conversation={conversation}
                    isSelected={selectedConversation?.id === conversation.id}
                    onClick={() => {
                      setSelectedConversation(conversation);
                      fetchMessages(conversation.id);
                    }}
                  />
                ))}
                
                {conversations.length === 0 && (
                  <div className="text-center py-12">
                    <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 font-hebrew">אין שיחות</h3>
                    <p className="text-gray-500 font-hebrew">השיחות שלך יופיעו כאן</p>
                  </div>
                )}
              </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
              {selectedConversation ? (
                <>
                  {/* Chat Header */}
                  <div className="p-4 border-b border-gray-200 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                          <MessageSquare className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 font-hebrew">
                            {selectedConversation.customer_name || selectedConversation.phone_number}
                          </h3>
                          <p className="text-sm text-gray-500 font-hebrew">
                            {selectedConversation.phone_number}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100">
                          <Phone className="w-5 h-5" />
                        </button>
                        <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100">
                          <MoreHorizontal className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto p-4" style={{ height: 'calc(600px - 140px)' }}>
                    {messages.map((message) => (
                      <MessageBubble key={message.id} message={message} />
                    ))}
                  </div>

                  {/* Message Input */}
                  <div className="p-4 border-t border-gray-200">
                    <div className="flex items-center space-x-2">
                      <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100">
                        <Paperclip className="w-5 h-5" />
                      </button>
                      <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100">
                        <Image className="w-5 h-5" />
                      </button>
                      <div className="flex-1">
                        <input
                          type="text"
                          placeholder="הקלד הודעה..."
                          value={newMessage}
                          onChange={(e) => setNewMessage(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent font-hebrew"
                        />
                      </div>
                      <button className="p-2 text-gray-600 hover:text-gray-900 rounded-lg hover:bg-gray-100">
                        <Smile className="w-5 h-5" />
                      </button>
                      <button 
                        onClick={sendMessage}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-hebrew"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <MessageSquare className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 font-hebrew">בחר שיחה</h3>
                    <p className="text-gray-500 font-hebrew">בחר שיחה מהרשימה כדי להתחיל</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhatsAppManagement;