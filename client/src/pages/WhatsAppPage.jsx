import React from 'react';
import { ArrowLeft, MessageCircle, Send, Phone, Users } from 'lucide-react';

const WhatsAppPage = () => {
  const conversations = [
    {
      id: 1,
      customerName: 'דוד כהן',
      phone: '+972-50-123-4567',
      lastMessage: 'תודה על ההצעה, אחזור אליכם בקרוב',
      timestamp: '14:15',
      unread: 0,
      status: 'delivered'
    },
    {
      id: 2,
      customerName: 'שרה לוי',
      phone: '+972-54-987-6543',
      lastMessage: 'האם אפשר לקבל עוד פרטים על השירות?',
      timestamp: '13:30',
      unread: 2,
      status: 'unread'
    },
    {
      id: 3,
      customerName: 'מיכאל אברהם',
      phone: '+972-52-555-1234',
      lastMessage: 'מעולה! אנחנו ממשיכים עם הפרויקט',
      timestamp: '12:45',
      unread: 0,
      status: 'read'
    }
  ];

  const stats = {
    totalConversations: conversations.length,
    unreadMessages: conversations.reduce((sum, conv) => sum + conv.unread, 0),
    activeToday: conversations.filter(conv => conv.timestamp.includes('2025-08-03')).length,
    responseRate: 95
  };

  const goBack = () => {
    window.location.href = '/admin/dashboard';
  };

  const handleConversationClick = (conversationId) => {
    alert(`פתיחת שיחה ${conversationId} - יושם בעתיד`);
  };

  const handleSendMessage = () => {
    alert('שליחת הודעה - יושם בעתיד');
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'delivered':
        return '✓✓';
      case 'read':
        return '✓✓';
      case 'unread':
        return '✓';
      default:
        return '⏳';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'delivered':
        return 'text-gray-500';
      case 'read':
        return 'text-blue-500';
      case 'unread':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={goBack}
                className="ml-4 p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                title="חזרה לדשבורד"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">💬 WhatsApp כלל־מערכתי</h1>
                <p className="text-gray-600 mt-1">ניהול הודעות WhatsApp לכל העסקים</p>
              </div>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">{stats.responseRate}%</p>
                <p className="text-sm text-gray-600">אחוז מענה</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-purple-600">{stats.unreadMessages}</p>
                <p className="text-sm text-gray-600">הודעות חדשות</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* סיכום WhatsApp */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <MessageCircle className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.totalConversations}</p>
                <p className="text-gray-600">שיחות פעילות</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Send className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.unreadMessages}</p>
                <p className="text-gray-600">הודעות ממתינות</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.activeToday}</p>
                <p className="text-gray-600">פעילים היום</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-xl shadow">
            <div className="flex items-center">
              <Phone className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{stats.responseRate}%</p>
                <p className="text-gray-600">אחוז מענה</p>
              </div>
            </div>
          </div>
        </div>

        {/* רשימת שיחות WhatsApp */}
        <div className="bg-white rounded-xl shadow">
          <div className="p-6 border-b">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">שיחות WhatsApp</h2>
              <button
                onClick={handleSendMessage}
                className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 flex items-center transition-colors"
              >
                <Send className="w-5 h-5 ml-2" />
                הודעה חדשה
              </button>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  onClick={() => handleConversationClick(conversation.id)}
                  className="flex items-center p-4 bg-gray-50 hover:bg-gray-100 rounded-lg cursor-pointer transition-colors"
                >
                  <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center text-white font-bold ml-4">
                    {conversation.customerName.charAt(0)}
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="font-medium text-gray-900">{conversation.customerName}</h3>
                      <div className="flex items-center">
                        <span className="text-sm text-gray-500 ml-2">{conversation.timestamp}</span>
                        <span className={`text-sm ${getStatusColor(conversation.status)}`}>
                          {getStatusIcon(conversation.status)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-gray-600 truncate max-w-md">{conversation.lastMessage}</p>
                      <div className="flex items-center">
                        <span className="text-xs text-gray-500 ml-2" dir="ltr">{conversation.phone}</span>
                        {conversation.unread > 0 && (
                          <span className="bg-green-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                            {conversation.unread}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhatsAppPage;