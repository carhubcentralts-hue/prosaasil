import React, { useState, useEffect } from 'react';
import { MessageCircle, ArrowLeft, Send, Phone, Clock, User, CheckCircle } from 'lucide-react';

const WhatsAppPage = () => {
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // טוען רשימת צ'אטים
    const fetchChats = () => {
      // נתונים לדוגמה
      const demoChatData = [
        {
          id: 1,
          customerName: 'יוסי כהן',
          phone: '+972-50-123-4567',
          lastMessage: 'תודה על המידע, אני אחזור אליכם',
          timestamp: '14:30',
          unread: 0,
          status: 'active',
          messages: [
            { id: 1, sender: 'customer', text: 'שלום, אני מעוניין במידע על השירותים שלכם', time: '14:25', read: true },
            { id: 2, sender: 'business', text: 'שלום יוסי! אשמח לעזור. איזה שירות מעניין אותך?', time: '14:26', read: true },
            { id: 3, sender: 'customer', text: 'אני מחפש פתרון CRM למשרד שלי', time: '14:28', read: true },
            { id: 4, sender: 'business', text: 'מצוין! יש לנו פתרונות CRM מתקדמים. כמה עובדים יש במשרד?', time: '14:29', read: true },
            { id: 5, sender: 'customer', text: 'תודה על המידע, אני אחזור אליכם', time: '14:30', read: false }
          ]
        },
        {
          id: 2,
          customerName: 'שרה לוי',
          phone: '+972-54-987-6543',
          lastMessage: 'מתי אפשר לקבוע פגישה?',
          timestamp: '13:45',
          unread: 2,
          status: 'pending',
          messages: [
            { id: 1, sender: 'customer', text: 'היי, שמעתי שאתם מציעים פתרונות AI', time: '13:40', read: true },
            { id: 2, sender: 'business', text: 'שלום שרה! כן, אנחנו מתמחים בפתרונות AI. איך אפשר לעזור?', time: '13:42', read: true },
            { id: 3, sender: 'customer', text: 'מתי אפשר לקבוע פגישה?', time: '13:45', read: false }
          ]
        },
        {
          id: 3,
          customerName: 'דוד ישראלי',
          phone: '+972-52-111-2222',
          lastMessage: 'אוקיי, תודה רבה!',
          timestamp: '12:15',
          unread: 0,
          status: 'completed',
          messages: [
            { id: 1, sender: 'customer', text: 'שלום, יש לי שאלה על המחירים', time: '12:10', read: true },
            { id: 2, sender: 'business', text: 'שלום דוד! בוודאי, מה השאלה?', time: '12:12', read: true },
            { id: 3, sender: 'customer', text: 'אוקיי, תודה רבה!', time: '12:15', read: true }
          ]
        }
      ];
      
      setChats(demoChatData);
      setSelectedChat(demoChatData[0]);
      setLoading(false);
    };

    fetchChats();
  }, []);

  const handleBackToDashboard = () => {
    window.location.href = '/business/dashboard';
  };

  const handleSendMessage = () => {
    if (!newMessage.trim() || !selectedChat) return;

    const message = {
      id: selectedChat.messages.length + 1,
      sender: 'business',
      text: newMessage,
      time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
      read: false
    };

    const updatedChats = chats.map(chat => {
      if (chat.id === selectedChat.id) {
        return {
          ...chat,
          messages: [...chat.messages, message],
          lastMessage: newMessage,
          timestamp: message.time
        };
      }
      return chat;
    });

    setChats(updatedChats);
    setSelectedChat({
      ...selectedChat,
      messages: [...selectedChat.messages, message],
      lastMessage: newMessage,
      timestamp: message.time
    });
    setNewMessage('');
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'pending': return 'text-orange-600 bg-orange-100';
      case 'completed': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'active': return 'פעיל';
      case 'pending': return 'ממתין';
      case 'completed': return 'הושלם';
      default: return 'לא ידוע';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <MessageCircle className="w-8 h-8 text-green-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-600">טוען צ'אטים...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 font-hebrew rtl">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={handleBackToDashboard}
                className="flex items-center px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors ml-4"
              >
                <ArrowLeft className="w-4 h-4 ml-2" />
                <span>חזרה לדשבורד</span>
              </button>
              <h1 className="text-3xl font-bold text-gray-900">מערכת WhatsApp</h1>
            </div>
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-medium">
                {chats.reduce((acc, chat) => acc + chat.unread, 0)} הודעות חדשות
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <MessageCircle className="w-8 h-8 text-green-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{chats.length}</p>
                <p className="text-gray-600">סה"כ צ'אטים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <User className="w-8 h-8 text-blue-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{chats.filter(c => c.status === 'active').length}</p>
                <p className="text-gray-600">צ'אטים פעילים</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <Clock className="w-8 h-8 text-orange-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{chats.filter(c => c.status === 'pending').length}</p>
                <p className="text-gray-600">ממתינים למענה</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <div className="flex items-center">
              <CheckCircle className="w-8 h-8 text-purple-500" />
              <div className="mr-4">
                <p className="text-2xl font-bold text-gray-900">{chats.filter(c => c.status === 'completed').length}</p>
                <p className="text-gray-600">צ'אטים שהושלמו</p>
              </div>
            </div>
          </div>
        </div>

        {/* Chat Interface */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Chat List */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b">
                <h2 className="text-lg font-bold text-gray-900">צ'אטים</h2>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {chats.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => setSelectedChat(chat)}
                    className={`p-4 border-b cursor-pointer hover:bg-gray-50 ${
                      selectedChat?.id === chat.id ? 'bg-blue-50 border-blue-200' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <h3 className="font-bold text-gray-900 ml-2">{chat.customerName}</h3>
                          {chat.unread > 0 && (
                            <span className="bg-red-500 text-white text-xs rounded-full px-2 py-1">
                              {chat.unread}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{chat.phone}</p>
                        <p className="text-sm text-gray-500 mt-1 line-clamp-2">{chat.lastMessage}</p>
                        <div className="flex items-center justify-between mt-2">
                          <span className="text-xs text-gray-400">{chat.timestamp}</span>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(chat.status)}`}>
                            {getStatusText(chat.status)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Chat Window */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow h-full flex flex-col">
              {selectedChat ? (
                <>
                  {/* Chat Header */}
                  <div className="p-4 border-b">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="font-bold text-gray-900">{selectedChat.customerName}</h2>
                        <p className="text-sm text-gray-600">{selectedChat.phone}</p>
                      </div>
                      <div className="flex items-center space-x-2 space-x-reverse">
                        <button className="p-2 text-green-600 hover:bg-green-50 rounded-lg">
                          <Phone className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="flex-1 p-4 overflow-y-auto max-h-96">
                    <div className="space-y-4">
                      {selectedChat.messages.map((message) => (
                        <div
                          key={message.id}
                          className={`flex ${message.sender === 'business' ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`max-w-xs px-4 py-2 rounded-lg ${
                              message.sender === 'business'
                                ? 'bg-blue-500 text-white'
                                : 'bg-gray-200 text-gray-900'
                            }`}
                          >
                            <p className="text-sm">{message.text}</p>
                            <p className={`text-xs mt-1 ${
                              message.sender === 'business' ? 'text-blue-100' : 'text-gray-500'
                            }`}>
                              {message.time}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Message Input */}
                  <div className="p-4 border-t">
                    <div className="flex items-center space-x-4 space-x-reverse">
                      <input
                        type="text"
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                        className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="הקלד הודעה..."
                      />
                      <button
                        onClick={handleSendMessage}
                        className="bg-blue-500 text-white p-3 rounded-lg hover:bg-blue-600 transition-colors"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <MessageCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">בחר צ'אט כדי להתחיל</p>
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

export default WhatsAppPage;