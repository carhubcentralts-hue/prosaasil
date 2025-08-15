import React, { useState, useEffect } from 'react';
import { 
  MessageCircle, 
  Send, 
  Image, 
  Paperclip,
  Search,
  Phone,
  User,
  Clock,
  Check,
  CheckCheck,
  Plus,
  Filter
} from 'lucide-react';

function WhatsAppPage({ business }) {
  const [contacts, setContacts] = useState([]);
  const [messages, setMessages] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({});
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchWhatsAppData();
  }, [business?.id]);

  useEffect(() => {
    if (selectedContact) {
      fetchMessages(selectedContact.id);
    }
  }, [selectedContact]);

  const fetchWhatsAppData = async () => {
    try {
      setLoading(true);
      const [contactsRes, statsRes] = await Promise.all([
        fetch(`/api/whatsapp/contacts?business_id=${business?.id}`),
        fetch(`/api/whatsapp/stats?business_id=${business?.id}`)
      ]);

      if (contactsRes.ok) {
        const contactsData = await contactsRes.json();
        setContacts(contactsData.contacts || []);
        if (contactsData.contacts?.length > 0) {
          setSelectedContact(contactsData.contacts[0]);
        }
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      console.error('Failed to fetch WhatsApp data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (contactId) => {
    try {
      const response = await fetch(`/api/whatsapp/messages?contact_id=${contactId}`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages || []);
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedContact) return;

    try {
      const response = await fetch('/api/whatsapp/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          to: selectedContact.phone_number,
          message: newMessage,
          business_id: business?.id
        }),
      });

      if (response.ok) {
        setNewMessage('');
        fetchMessages(selectedContact.id);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const getMessageStatus = (message) => {
    switch (message.status) {
      case 'sent':
        return <Check className="w-4 h-4 text-gray-400" />;
      case 'delivered':
        return <CheckCheck className="w-4 h-4 text-gray-400" />;
      case 'read':
        return <CheckCheck className="w-4 h-4 text-blue-500" />;
      default:
        return null;
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('he-IL', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const filteredContacts = contacts.filter(contact =>
    contact.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    contact.phone_number?.includes(searchTerm)
  );

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const whatsappStats = [
    {
      title: 'הודעות היום',
      value: stats.messages_today || 0,
      icon: MessageCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      title: 'שיחות פעילות',
      value: stats.active_chats || 0,
      icon: User,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      title: 'זמן תגובה ממוצע',
      value: `${stats.avg_response_time || 0} דק'`,
      icon: Clock,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          וואטסאפ עסקי
        </h1>
        <p className="text-gray-600 mt-1">
          ניהול שיחות והודעות וואטסאפ
        </p>
      </div>

      {/* WhatsApp Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {whatsappStats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600 mb-1">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">
                    {stat.value}
                  </p>
                </div>
                <div className={`${stat.bgColor} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Chat Interface */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="flex h-[600px]">
          {/* Contacts Sidebar */}
          <div className="w-1/3 border-l border-gray-200 flex flex-col">
            {/* Search */}
            <div className="p-4 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="חיפוש אנשי קשר..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pr-10 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500"
                />
              </div>
            </div>

            {/* Contacts List */}
            <div className="flex-1 overflow-y-auto">
              {filteredContacts.map((contact) => (
                <div
                  key={contact.id}
                  onClick={() => setSelectedContact(contact)}
                  className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${
                    selectedContact?.id === contact.id ? 'bg-green-50 border-l-4 border-green-500' : ''
                  }`}
                >
                  <div className="flex items-center">
                    <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center ml-3">
                      <User className="w-6 h-6 text-green-600" />
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-center">
                        <h4 className="text-sm font-medium text-gray-900">
                          {contact.name || contact.phone_number}
                        </h4>
                        <span className="text-xs text-gray-500">
                          {formatTime(contact.last_message_time)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 truncate mt-1">
                        {contact.last_message}
                      </p>
                    </div>
                    {contact.unread_count > 0 && (
                      <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                        <span className="text-xs text-white font-medium">
                          {contact.unread_count}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            {selectedContact ? (
              <>
                {/* Chat Header */}
                <div className="p-4 border-b border-gray-200 bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center ml-3">
                        <User className="w-5 h-5 text-green-600" />
                      </div>
                      <div>
                        <h3 className="text-lg font-medium text-gray-900">
                          {selectedContact.name || selectedContact.phone_number}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {selectedContact.phone_number}
                        </p>
                      </div>
                    </div>
                    <div className="flex space-x-2 space-x-reverse">
                      <button className="p-2 text-gray-400 hover:text-gray-600">
                        <Phone className="w-5 h-5" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-gray-600">
                        <Search className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          message.direction === 'outbound'
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p className="text-sm">{message.content}</p>
                        <div className={`flex items-center mt-1 text-xs ${
                          message.direction === 'outbound' ? 'text-green-100' : 'text-gray-500'
                        }`}>
                          <span>{formatTime(message.timestamp)}</span>
                          {message.direction === 'outbound' && (
                            <span className="mr-1">
                              {getMessageStatus(message)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Message Input */}
                <div className="p-4 border-t border-gray-200">
                  <div className="flex items-center space-x-2 space-x-reverse">
                    <button className="p-2 text-gray-400 hover:text-gray-600">
                      <Paperclip className="w-5 h-5" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-gray-600">
                      <Image className="w-5 h-5" />
                    </button>
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="הקלד הודעה..."
                      className="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:ring-1 focus:ring-green-500"
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!newMessage.trim()}
                      className="p-2 bg-green-500 text-white rounded-full hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <MessageCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    בחר שיחה
                  </h3>
                  <p className="text-gray-500">
                    בחר איש קשר מהרשימה כדי להתחיל לשוחח
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-6 bg-green-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-green-900 mb-4">
          פעולות מהירות
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="flex items-center justify-center p-4 bg-white rounded-lg hover:shadow-md transition-shadow">
            <Plus className="w-5 h-5 text-green-600 ml-2" />
            <span className="text-green-800 font-medium">שיחה חדשה</span>
          </button>
          <button className="flex items-center justify-center p-4 bg-white rounded-lg hover:shadow-md transition-shadow">
            <MessageCircle className="w-5 h-5 text-green-600 ml-2" />
            <span className="text-green-800 font-medium">הודעה קבוצתית</span>
          </button>
          <button className="flex items-center justify-center p-4 bg-white rounded-lg hover:shadow-md transition-shadow">
            <Filter className="w-5 h-5 text-green-600 ml-2" />
            <span className="text-green-800 font-medium">סינון הודעות</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default WhatsAppPage;