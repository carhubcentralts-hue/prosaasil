import React, { useState, useEffect, useRef } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  MessageSquare, Send, Search, Phone, User, Paperclip,
  Smile, MoreVertical, Check, CheckCheck, Clock,
  Star, Filter, Archive, Settings, Download,
  Image, File, Mic, Video, Circle, Activity
} from 'lucide-react';

export default function ModernWhatsApp() {
  const [userRole, setUserRole] = useState('business');
  const [selectedChat, setSelectedChat] = useState(null);
  const [message, setMessage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [chats, setChats] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadChats();
    loadMessages();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadChats = () => {
    // Demo chat data
    const demoChats = [
      {
        id: 1,
        name: 'יוסי כהן',
        phone: '050-1234567',
        lastMessage: 'תודה על השירות המעולה!',
        timestamp: '14:30',
        unread: 2,
        status: 'read',
        avatar: null,
        isOnline: true
      },
      {
        id: 2,
        name: 'רחל לוי',
        phone: '052-9876543',
        lastMessage: 'מתי אפשר לקבוע פגישה?',
        timestamp: '13:45',
        unread: 0,
        status: 'delivered',
        avatar: null,
        isOnline: false
      },
      {
        id: 3,
        name: 'דני אברהם',
        phone: '053-5555555',
        lastMessage: 'אני מעוניין במידע נוסף',
        timestamp: '12:15',
        unread: 1,
        status: 'sent',
        avatar: null,
        isOnline: true
      }
    ];
    setChats(demoChats);
    setSelectedChat(demoChats[0]);
    setLoading(false);
  };

  const loadMessages = () => {
    // Demo messages for selected chat
    const demoMessages = [
      {
        id: 1,
        text: 'שלום, אני מעוניין לקבל מידע על השירותים שלכם',
        sender: 'customer',
        timestamp: '14:25',
        status: 'read'
      },
      {
        id: 2,
        text: 'שלום! בכיף נשמח לעזור. איזה סוג שירות מעניין אותך?',
        sender: 'business',
        timestamp: '14:26',
        status: 'read'
      },
      {
        id: 3,
        text: 'אני מחפש ייעוץ עסקי לחברה שלי',
        sender: 'customer',
        timestamp: '14:27',
        status: 'read'
      },
      {
        id: 4,
        text: 'מעולה! נוכל לקבוע פגישת ייעוץ. באיזה יום נוח לך?',
        sender: 'business',
        timestamp: '14:28',
        status: 'read'
      },
      {
        id: 5,
        text: 'יום רביעי יהיה מושלם',
        sender: 'customer',
        timestamp: '14:29',
        status: 'read'
      },
      {
        id: 6,
        text: 'נהדר! נקבע ליום רביעי בשעה 10:00. תקבל אישור במייל',
        sender: 'business',
        timestamp: '14:30',
        status: 'delivered'
      }
    ];
    setMessages(demoMessages);
  };

  const handleSendMessage = () => {
    if (!message.trim()) return;

    const newMessage = {
      id: messages.length + 1,
      text: message,
      sender: 'business',
      timestamp: new Date().toLocaleTimeString('he-IL', { 
        hour: '2-digit', 
        minute: '2-digit' 
      }),
      status: 'sent'
    };

    setMessages([...messages, newMessage]);
    setMessage('');

    // Simulate message delivery
    setTimeout(() => {
      setMessages(prev => prev.map(msg => 
        msg.id === newMessage.id ? { ...msg, status: 'delivered' } : msg
      ));
    }, 1000);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'sent': return <Check className="w-4 h-4 text-gray-400" />;
      case 'delivered': return <CheckCheck className="w-4 h-4 text-gray-400" />;
      case 'read': return <CheckCheck className="w-4 h-4 text-blue-500" />;
      default: return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const filteredChats = chats.filter(chat =>
    chat.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    chat.phone.includes(searchTerm)
  );

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-green-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען שיחות WhatsApp...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-green-600 to-emerald-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <MessageSquare className="w-10 h-10" />
                💬 WhatsApp עסקי
              </h1>
              <p className="text-green-100 text-lg">
                ניהול שיחות וקשר ישיר עם לקוחות
              </p>
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold">{chats.length}</div>
              <div className="text-green-100">שיחות פעילות</div>
            </div>
          </div>
        </div>

        {/* WhatsApp Interface */}
        <div className="bg-white rounded-3xl shadow-2xl border border-gray-100 overflow-hidden h-[700px]">
          <div className="flex h-full">
            {/* Chat List Sidebar */}
            <div className="w-1/3 border-l border-gray-200 bg-gray-50">
              {/* Sidebar Header */}
              <div className="p-6 border-b border-gray-200 bg-white">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-gray-900">שיחות</h2>
                  <div className="flex gap-2">
                    <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-xl">
                      <Settings className="w-5 h-5" />
                    </button>
                    <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-xl">
                      <MoreVertical className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                
                {/* Search */}
                <div className="relative">
                  <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="חיפוש שיחות..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-gray-100 border-0 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
              </div>

              {/* Chat List */}
              <div className="overflow-y-auto h-full">
                {filteredChats.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => setSelectedChat(chat)}
                    className={`p-4 cursor-pointer transition-all duration-200 border-b border-gray-100 hover:bg-white ${
                      selectedChat?.id === chat.id ? 'bg-white border-l-4 border-l-green-500' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                          {chat.name.charAt(0)}
                        </div>
                        {chat.isOnline && (
                          <div className="absolute -bottom-1 -left-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white"></div>
                        )}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h3 className="font-semibold text-gray-900 truncate">{chat.name}</h3>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">{chat.timestamp}</span>
                            {chat.unread > 0 && (
                              <span className="bg-green-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                                {chat.unread}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm text-gray-600 truncate flex-1">{chat.lastMessage}</p>
                          {getStatusIcon(chat.status)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Chat Content */}
            <div className="flex-1 flex flex-col">
              {selectedChat ? (
                <>
                  {/* Chat Header */}
                  <div className="p-6 border-b border-gray-200 bg-white">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="relative">
                          <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                            {selectedChat.name.charAt(0)}
                          </div>
                          {selectedChat.isOnline && (
                            <div className="absolute -bottom-1 -left-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white"></div>
                          )}
                        </div>
                        <div>
                          <h3 className="font-bold text-gray-900">{selectedChat.name}</h3>
                          <p className="text-sm text-gray-600 flex items-center gap-2">
                            <Phone className="w-4 h-4" />
                            {selectedChat.phone}
                            {selectedChat.isOnline && (
                              <span className="text-green-600 font-medium">• מחובר</span>
                            )}
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <button className="p-2 text-green-600 hover:bg-green-50 rounded-xl">
                          <Phone className="w-5 h-5" />
                        </button>
                        <button className="p-2 text-blue-600 hover:bg-blue-50 rounded-xl">
                          <Video className="w-5 h-5" />
                        </button>
                        <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-xl">
                          <MoreVertical className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
                    <div className="space-y-4">
                      {messages.map((msg) => (
                        <div
                          key={msg.id}
                          className={`flex ${msg.sender === 'business' ? 'justify-start' : 'justify-end'}`}
                        >
                          <div
                            className={`max-w-xs px-4 py-3 rounded-2xl ${
                              msg.sender === 'business'
                                ? 'bg-white text-gray-900 shadow-sm'
                                : 'bg-green-500 text-white'
                            }`}
                          >
                            <p className="text-sm">{msg.text}</p>
                            <div className={`flex items-center gap-1 mt-2 justify-end ${
                              msg.sender === 'business' ? 'text-gray-500' : 'text-green-100'
                            }`}>
                              <span className="text-xs">{msg.timestamp}</span>
                              {msg.sender === 'business' && getStatusIcon(msg.status)}
                            </div>
                          </div>
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  </div>

                  {/* Message Input */}
                  <div className="p-6 border-t border-gray-200 bg-white">
                    <div className="flex items-center gap-4">
                      <button className="p-3 text-gray-600 hover:bg-gray-100 rounded-xl">
                        <Paperclip className="w-5 h-5" />
                      </button>
                      
                      <div className="flex-1 relative">
                        <input
                          type="text"
                          value={message}
                          onChange={(e) => setMessage(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                          placeholder="הקלד הודעה..."
                          className="w-full bg-gray-100 border-0 rounded-xl pr-4 pl-12 py-3 focus:outline-none focus:ring-2 focus:ring-green-500"
                        />
                        <button className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-600 hover:text-gray-800">
                          <Smile className="w-5 h-5" />
                        </button>
                      </div>
                      
                      <button className="p-3 text-gray-600 hover:bg-gray-100 rounded-xl">
                        <Mic className="w-5 h-5" />
                      </button>
                      
                      <button
                        onClick={handleSendMessage}
                        disabled={!message.trim()}
                        className="p-3 bg-green-500 text-white rounded-xl hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                      >
                        <Send className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center bg-gray-50">
                  <div className="text-center">
                    <div className="w-24 h-24 bg-gradient-to-br from-green-100 to-green-200 rounded-2xl flex items-center justify-center mx-auto mb-6">
                      <MessageSquare className="w-12 h-12 text-green-600" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">בחר שיחה</h3>
                    <p className="text-gray-500">בחר שיחה מהרשימה כדי להתחיל לשוחח</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-green-600" />
              סטטיסטיקות היום
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600">הודעות נשלחו</span>
                <span className="font-bold text-green-600">24</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">הודעות התקבלו</span>
                <span className="font-bold text-blue-600">18</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">זמן תגובה ממוצע</span>
                <span className="font-bold text-purple-600">2.3 דק'</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Star className="w-5 h-5 text-yellow-600" />
              הודעות מהירות
            </h3>
            <div className="space-y-2">
              <button className="w-full text-right p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-all text-sm">
                שלום! איך אפשר לעזור?
              </button>
              <button className="w-full text-right p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-all text-sm">
                תודה על הפנייה, נחזור אליך בהקדם
              </button>
              <button className="w-full text-right p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-all text-sm">
                נקבע פגישה השבוע?
              </button>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Filter className="w-5 h-5 text-blue-600" />
              סינון שיחות
            </h3>
            <div className="space-y-2">
              <button className="w-full text-right p-2 bg-blue-50 rounded-lg hover:bg-blue-100 transition-all text-sm text-blue-700">
                הודעות לא נקראו (3)
              </button>
              <button className="w-full text-right p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-all text-sm">
                שיחות מהיום
              </button>
              <button className="w-full text-right p-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-all text-sm">
                לקוחות VIP
              </button>
            </div>
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}