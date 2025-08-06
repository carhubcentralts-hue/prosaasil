import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  X, 
  MessageSquare, 
  Phone, 
  Mail, 
  Calendar, 
  FileText,
  CreditCard,
  PenTool,
  CheckSquare,
  MessageCircle,
  PhoneCall,
  User,
  Building2,
  Tag,
  Clock,
  Plus,
  Send
} from 'lucide-react';

const CustomerDetailsModal = ({ customer, isOpen, onClose, businessId }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [customerData, setCustomerData] = useState(customer);
  const [loading, setLoading] = useState(false);
  const [whatsappMessage, setWhatsappMessage] = useState('');
  
  const tabs = [
    { id: 'overview', name: 'סקירה', icon: User },
    { id: 'contracts', name: 'חוזים', icon: FileText },
    { id: 'invoices', name: 'חשבוניות', icon: CreditCard },
    { id: 'signatures', name: 'חתימות', icon: PenTool },
    { id: 'tasks', name: 'משימות', icon: CheckSquare },
    { id: 'notes', name: 'תיעוד', icon: MessageCircle },
    { id: 'whatsapp', name: 'WhatsApp', icon: MessageSquare },
    { id: 'calls', name: 'שיחות', icon: PhoneCall }
  ];

  const sendWhatsAppMessage = async () => {
    if (!whatsappMessage.trim()) return;
    
    try {
      setLoading(true);
      const response = await axios.post('/api/whatsapp/send', {
        business_id: businessId,
        phone_number: customerData.phone,
        message: whatsappMessage,
        customer_id: customerData.id
      });
      
      if (response.data.success) {
        alert('הודעה נשלחה בהצלחה!');
        setWhatsappMessage('');
      }
    } catch (error) {
      console.error('Error sending WhatsApp:', error);
      alert('שגיאה בשליחת הודעה');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !customer) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b bg-gradient-to-r from-blue-50 to-indigo-50">
          <div className="flex items-center gap-4">
            <div className="bg-blue-100 p-3 rounded-full">
              <User className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900 font-hebrew">{customerData.name}</h2>
              <p className="text-gray-600 font-hebrew">לקוח #{customerData.id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => sendWhatsAppMessage()}
              disabled={!whatsappMessage.trim() || loading}
              className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 flex items-center gap-2 font-hebrew"
            >
              <MessageSquare className="w-4 h-4" />
              שוחח ב-WhatsApp
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Customer Info Cards */}
        <div className="p-6 border-b bg-gray-50">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 text-blue-600 mb-2">
                <Phone className="w-4 h-4" />
                <span className="text-sm font-hebrew">טלפון</span>
              </div>
              <p className="font-medium">{customerData.phone}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 text-green-600 mb-2">
                <Mail className="w-4 h-4" />
                <span className="text-sm font-hebrew">אימייל</span>
              </div>
              <p className="font-medium">{customerData.email}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 text-purple-600 mb-2">
                <Tag className="w-4 h-4" />
                <span className="text-sm font-hebrew">סטטוס</span>
              </div>
              <p className="font-medium font-hebrew">{customerData.status || 'פעיל'}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <div className="flex items-center gap-2 text-orange-600 mb-2">
                <Clock className="w-4 h-4" />
                <span className="text-sm font-hebrew">תאריך יצירה</span>
              </div>
              <p className="font-medium">{new Date(customerData.created_at || Date.now()).toLocaleDateString('he-IL')}</p>
            </div>
          </div>
        </div>

        {/* Quick WhatsApp */}
        <div className="p-6 border-b">
          <div className="flex gap-2">
            <input
              type="text"
              value={whatsappMessage}
              onChange={(e) => setWhatsappMessage(e.target.value)}
              placeholder="הקלד הודעה מהירה ל-WhatsApp..."
              className="flex-1 px-4 py-2 border rounded-lg font-hebrew"
            />
            <button
              onClick={sendWhatsAppMessage}
              disabled={!whatsappMessage.trim() || loading}
              className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 disabled:opacity-50 flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              {loading ? 'שולח...' : 'שלח'}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b">
          <div className="flex overflow-x-auto">
            {tabs.map((tab) => {
              const IconComponent = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-6 py-3 font-hebrew whitespace-nowrap border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600 bg-blue-50'
                      : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                  }`}
                >
                  <IconComponent className="w-4 h-4" />
                  {tab.name}
                </button>
              );
            })}
          </div>
        </div>

        {/* Tab Content */}
        <div className="p-6 min-h-[400px]">
          {activeTab === 'overview' && <OverviewTab customer={customerData} />}
          {activeTab === 'contracts' && <ContractsTab customer={customerData} />}
          {activeTab === 'invoices' && <InvoicesTab customer={customerData} />}
          {activeTab === 'signatures' && <SignaturesTab customer={customerData} />}
          {activeTab === 'tasks' && <TasksTab customer={customerData} />}
          {activeTab === 'notes' && <NotesTab customer={customerData} />}
          {activeTab === 'whatsapp' && <WhatsAppTab customer={customerData} />}
          {activeTab === 'calls' && <CallsTab customer={customerData} />}
        </div>
      </div>
    </div>
  );
};

// Tab Components
const OverviewTab = ({ customer }) => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-6 rounded-lg">
        <h3 className="text-lg font-bold text-blue-900 font-hebrew mb-4">מידע כללי</h3>
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-blue-700 font-hebrew">שם מלא:</span>
            <span className="font-medium">{customer.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-blue-700 font-hebrew">טלפון:</span>
            <span className="font-medium">{customer.phone}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-blue-700 font-hebrew">אימייל:</span>
            <span className="font-medium">{customer.email}</span>
          </div>
        </div>
      </div>
      
      <div className="bg-gradient-to-br from-green-50 to-green-100 p-6 rounded-lg">
        <h3 className="text-lg font-bold text-green-900 font-hebrew mb-4">סטטיסטיקות</h3>
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-green-700 font-hebrew">חוזים פעילים:</span>
            <span className="font-bold text-green-600">3</span>
          </div>
          <div className="flex justify-between">
            <span className="text-green-700 font-hebrew">חשבוניות:</span>
            <span className="font-bold text-green-600">7</span>
          </div>
          <div className="flex justify-between">
            <span className="text-green-700 font-hebrew">שיחות:</span>
            <span className="font-bold text-green-600">12</span>
          </div>
        </div>
      </div>
    </div>
  </div>
);

const ContractsTab = ({ customer }) => (
  <div className="space-y-4">
    <div className="flex justify-between items-center">
      <h3 className="text-lg font-bold font-hebrew">חוזים</h3>
      <button className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 flex items-center gap-2">
        <Plus className="w-4 h-4" />
        חוזה חדש
      </button>
    </div>
    <div className="bg-yellow-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין חוזים זמינים כרגע
    </div>
  </div>
);

const InvoicesTab = ({ customer }) => (
  <div className="space-y-4">
    <div className="flex justify-between items-center">
      <h3 className="text-lg font-bold font-hebrew">חשבוניות</h3>
      <button className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 flex items-center gap-2">
        <Plus className="w-4 h-4" />
        חשבונית חדשה
      </button>
    </div>
    <div className="bg-yellow-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין חשבוניות זמינות כרגע
    </div>
  </div>
);

const SignaturesTab = ({ customer }) => (
  <div className="space-y-4">
    <h3 className="text-lg font-bold font-hebrew">חתימות דיגיטליות</h3>
    <div className="bg-yellow-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין חתימות זמינות כרגע
    </div>
  </div>
);

const TasksTab = ({ customer }) => (
  <div className="space-y-4">
    <div className="flex justify-between items-center">
      <h3 className="text-lg font-bold font-hebrew">משימות</h3>
      <button className="bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 flex items-center gap-2">
        <Plus className="w-4 h-4" />
        משימה חדשה
      </button>
    </div>
    <div className="bg-yellow-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין משימות זמינות כרגע
    </div>
  </div>
);

const NotesTab = ({ customer }) => (
  <div className="space-y-4">
    <h3 className="text-lg font-bold font-hebrew">תיעוד פנימי</h3>
    <div className="bg-yellow-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין תיעוד זמין כרגע
    </div>
  </div>
);

const WhatsAppTab = ({ customer }) => (
  <div className="space-y-4">
    <h3 className="text-lg font-bold font-hebrew">שיחות WhatsApp</h3>
    <div className="bg-green-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין שיחות WhatsApp זמינות כרגע
    </div>
  </div>
);

const CallsTab = ({ customer }) => (
  <div className="space-y-4">
    <h3 className="text-lg font-bold font-hebrew">שיחות מוקלטות</h3>
    <div className="bg-blue-50 p-4 rounded-lg text-center font-hebrew text-gray-600">
      אין שיחות מוקלטות זמינות כרגע
    </div>
  </div>
);

export default CustomerDetailsModal;