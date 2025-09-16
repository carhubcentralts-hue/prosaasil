import React, { useState, useEffect } from 'react';
// Temporary simple components until we add proper UI lib
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: any) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: any) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    secondary: "bg-gray-100 text-gray-800", 
    destructive: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};
import { MessageSquare, Users, Settings, Phone } from 'lucide-react';

export function WhatsAppPage() {
  const [loading, setLoading] = useState(true);
  const [threads, setThreads] = useState<any[]>([]);
  const [selectedThread, setSelectedThread] = useState<any>(null);

  useEffect(() => {
    // Simulate loading
    setTimeout(() => {
      setLoading(false);
      // Mock data
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
    }, 500);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען WhatsApp...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-green-600" />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                WhatsApp
              </h1>
            </div>
            <Badge variant="secondary">
              {threads.length} שיחות
            </Badge>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <Settings className="w-4 h-4 mr-2" />
              הגדרות
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Thread List - Left Side */}
        <div className={`${
          selectedThread ? 'hidden lg:flex' : 'flex'
        } w-full lg:w-80 xl:w-96 flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700`}>
          
          {/* Search */}
          <div className="p-4 border-b">
            <input
              type="text"
              placeholder="חיפוש שיחות..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Threads */}
          <div className="flex-1 overflow-y-auto">
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${
                  selectedThread?.id === thread.id ? 'bg-blue-50' : ''
                }`}
                onClick={() => setSelectedThread(thread)}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-gray-900">{thread.name}</h3>
                  <span className="text-xs text-gray-500">{thread.time}</span>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-600 truncate flex-1">{thread.lastMessage}</p>
                  {thread.unread > 0 && (
                    <Badge variant="destructive" className="ml-2 h-5 w-5 p-0 text-xs">
                      {thread.unread}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1" dir="ltr">{thread.phone}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Chat Area - Right Side */}
        <div className={`${
          selectedThread ? 'flex' : 'hidden lg:flex'
        } flex-1 flex-col`}>
          {selectedThread ? (
            <>
              {/* Chat Header */}
              <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="lg:hidden"
                      onClick={() => setSelectedThread(null)}
                    >
                      ←
                    </Button>
                    <div>
                      <h2 className="font-semibold text-gray-900 dark:text-white">
                        {selectedThread.name}
                      </h2>
                      <p className="text-sm text-gray-500 dark:text-gray-400" dir="ltr">
                        {selectedThread.phone}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <Phone className="w-4 h-4 mr-2" />
                      התקשר
                    </Button>
                    <Button variant="outline" size="sm">
                      <Users className="w-4 h-4 mr-2" />
                      פתח ליד
                    </Button>
                  </div>
                </div>
              </div>

              {/* Messages Area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                {/* Example messages */}
                <div className="flex justify-end">
                  <div className="bg-blue-500 text-white px-4 py-2 rounded-lg max-w-xs">
                    שלום! איך אוכל לעזור לך?
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="bg-white px-4 py-2 rounded-lg max-w-xs border">
                    {selectedThread.lastMessage}
                  </div>
                </div>
              </div>

              {/* Message Input */}
              <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-white">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="כתוב הודעה..."
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <Button>שלח</Button>
                </div>
              </div>
            </>
          ) : (
            // Empty State
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                  בחר שיחה
                </h3>
                <p className="text-gray-500 dark:text-gray-400">
                  בחר שיחה מהרשימה כדי להתחיל לצאט
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}