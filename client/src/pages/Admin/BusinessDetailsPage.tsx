import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Building2, 
  ArrowRight, 
  Globe, 
  Phone, 
  MessageCircle, 
  Clock, 
  MapPin, 
  Users, 
  Settings, 
  Activity, 
  Eye,
  Edit,
  Key,
  UserX,
  Pause,
  Play,
  Trash2,
  CheckCircle,
  XCircle,
  User,
  Calendar,
  Shield,
  Wifi,
  WifiOff
} from 'lucide-react';
import { cn } from '../../shared/utils/cn';

interface BusinessDetails {
  id: number;
  name: string;
  domain: string;
  defaultPhoneE164: string;
  whatsappJid: string;
  timezone: string;
  businessHours: {
    [key: string]: Array<{ from: string; to: string; }>;
  };
  address: string;
  stats: {
    users: number;
    leads: number;
    unread: number;
    callsToday: number;
    waToday: number;
  };
  status: 'active' | 'suspended';
  createdAt: string;
  updatedAt: string;
}

interface BusinessUser {
  id: number;
  name: string;
  email: string;
  role: string;
  lastLogin: string;
}

interface AuditEntry {
  ts: string;
  actor: string;
  action: string;
  ip: string;
}

// Mock data - In real app this would come from API
const mockBusinessDetails: BusinessDetails = {
  id: 1,
  name: 'שי דירות ומשרדים בע״מ',
  domain: 'shai-realestate.co.il',
  defaultPhoneE164: '+972-3-376-3805',
  whatsappJid: '972501234567@s.whatsapp.net',
  timezone: 'Asia/Jerusalem',
  businessHours: {
    sun: [{ from: '09:00', to: '18:00' }],
    mon: [{ from: '09:00', to: '18:00' }],
    tue: [{ from: '09:00', to: '18:00' }],
    wed: [{ from: '09:00', to: '18:00' }],
    thu: [{ from: '09:00', to: '17:00' }],
    fri: [{ from: '09:00', to: '14:00' }],
    sat: []
  },
  address: 'רחוב הרצל 45, תל אביב-יפו 6511503',
  stats: {
    users: 8,
    leads: 248,
    unread: 7,
    callsToday: 12,
    waToday: 19
  },
  status: 'active',
  createdAt: '2024-08-01T10:22:00Z',
  updatedAt: '2024-12-25T08:11:00Z'
};

const mockUsers: BusinessUser[] = [
  {
    id: 2,
    name: 'מנהל העסק',
    email: 'business@shai-offices.co.il',
    role: 'business',
    lastLogin: '2024-12-25T09:30:00Z'
  },
  {
    id: 3,
    name: 'מנהל שי דירות', 
    email: 'manager@shai-realestate.co.il',
    role: 'manager',
    lastLogin: '2024-12-25T08:15:00Z'
  },
  {
    id: 4,
    name: 'סוכן 1',
    email: 'agent1@shai-offices.co.il',
    role: 'agent',
    lastLogin: '2024-12-24T16:45:00Z'
  }
];

const mockAuditEntries: AuditEntry[] = [
  {
    ts: '2024-12-25T09:12:10Z',
    actor: 'admin@system.co.il',
    action: 'business.view',
    ip: '192.168.1.100'
  },
  {
    ts: '2024-12-24T14:55:22Z',
    actor: 'manager@shai-realestate.co.il',
    action: 'settings.update',
    ip: '10.0.0.15'
  },
  {
    ts: '2024-12-24T11:30:15Z',
    actor: 'admin@system.co.il',
    action: 'user.reset_password',
    ip: '192.168.1.100'
  }
];

type TabType = 'overview' | 'users' | 'integrations' | 'audit';

export function BusinessDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [business, setBusiness] = useState<BusinessDetails | null>(null);
  const [users, setUsers] = useState<BusinessUser[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Load business details
  useEffect(() => {
    if (!id) return;
    
    // Simulate API call
    setTimeout(() => {
      setBusiness(mockBusinessDetails);
      setUsers(mockUsers);
      setAuditEntries(mockAuditEntries);
      setIsLoading(false);
    }, 500);
  }, [id]);

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const handleAction = (action: string) => {
    if (!business) return;
    
    switch (action) {
      case 'edit':
        console.log(`עריכת עסק: ${business.name}`);
        // TODO: Open edit form modal or navigate to edit page
        alert(`עריכת פרטי עסק "${business.name}" - טופס עריכה יפתח כאן`);
        break;
      case 'impersonate':
        console.log(`התחזות לעסק: ${business.name}`);
        if (confirm(`האם אתה בטוח שאתה רוצה להתחזות לעסק "${business.name}"?`)) {
          alert(`מתחזה לעסק "${business.name}" - יש לבצע כאן אינטגרציה עם השרת`);
        }
        break;
      case 'suspend':
        console.log(`השעיית עסק: ${business.name}`);
        if (confirm(`האם אתה בטוח שאתה רוצה להשעות את העסק "${business.name}"?`)) {
          setBusiness({...business, status: 'suspended'});
          alert(`העסק "${business.name}" הושעה`);
        }
        break;
      case 'resume':
        console.log(`הפעלת עסק: ${business.name}`);
        if (confirm(`האם אתה בטוח שאתה רוצה להפעיל מחדש את העסק "${business.name}"?`)) {
          setBusiness({...business, status: 'active'});
          alert(`העסק "${business.name}" הופעל מחדש`);
        }
        break;
      case 'delete':
        console.log(`מחיקת עסק: ${business.name}`);
        const confirmDelete = prompt(`לאישור מחיקה, הקלד את שם העסק: "${business.name}"`);
        if (confirmDelete === business.name) {
          alert(`העסק "${business.name}" נמחק (מחיקה רכה) - יש לבצע קריאה לשרת`);
          navigate('/app/admin/businesses');
        } else {
          alert('מחיקה בוטלה - שם העסק לא תואם');
        }
        break;
      default:
        break;
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-slate-200 rounded w-1/3 mb-6"></div>
            <div className="h-64 bg-slate-200 rounded-xl"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
        <div className="max-w-7xl mx-auto text-center py-20">
          <Building2 className="h-16 w-16 mx-auto mb-4 text-slate-300" />
          <h2 className="text-xl font-semibold text-slate-900 mb-2">עסק לא נמצא</h2>
          <p className="text-slate-600 mb-6">העסק שחיפשת לא קיים במערכת</p>
          <button
            onClick={() => navigate('/app/admin/businesses')}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors"
          >
            חזור לרשימת העסקים
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Navigation & Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/app/admin/businesses')}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 transition-colors mb-4"
          >
            <ArrowRight className="h-4 w-4" />
            חזור לניהול עסקים
          </button>

          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Building2 className="h-8 w-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-semibold text-slate-900">
                  {business.name}
                </h1>
                <div className="flex items-center gap-3 mt-1">
                  <span className={cn(
                    'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
                    business.status === 'active' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  )}>
                    {business.status === 'active' ? (
                      <>
                        <CheckCircle className="h-4 w-4 ml-1" />
                        פעיל
                      </>
                    ) : (
                      <>
                        <XCircle className="h-4 w-4 ml-1" />
                        מושעה
                      </>
                    )}
                  </span>
                  <span className="text-sm text-slate-500">ID: {business.id}</span>
                </div>
              </div>
            </div>

            {/* Primary Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleAction('edit')}
                className="flex items-center gap-2 px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
              >
                <Edit className="h-4 w-4" />
                עריכה
              </button>
              <button
                onClick={() => handleAction('impersonate')}
                className="flex items-center gap-2 px-4 py-2 text-blue-700 hover:bg-blue-50 rounded-xl transition-colors"
              >
                <UserX className="h-4 w-4" />
                התחזות
              </button>
              {business.status === 'active' ? (
                <button
                  onClick={() => handleAction('suspend')}
                  className="flex items-center gap-2 px-4 py-2 text-orange-700 hover:bg-orange-50 rounded-xl transition-colors"
                >
                  <Pause className="h-4 w-4" />
                  השעה
                </button>
              ) : (
                <button
                  onClick={() => handleAction('resume')}
                  className="flex items-center gap-2 px-4 py-2 text-green-700 hover:bg-green-50 rounded-xl transition-colors"
                >
                  <Play className="h-4 w-4" />
                  הפעל
                </button>
              )}
              <button
                onClick={() => handleAction('delete')}
                className="flex items-center gap-2 px-4 py-2 text-red-700 hover:bg-red-50 rounded-xl transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                מחק
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="border-b border-slate-200">
            <nav className="flex">
              {[
                { key: 'overview', label: 'סקירה כללית', icon: Eye },
                { key: 'users', label: 'משתמשים', icon: Users },
                { key: 'integrations', label: 'אינטגרציות', icon: Settings },
                { key: 'audit', label: 'יומן ביקורת', icon: Shield }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as TabType)}
                  className={cn(
                    'flex items-center gap-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors',
                    activeTab === tab.key
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Stats Cards */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Users className="h-5 w-5 text-blue-600" />
                      <span className="text-sm font-medium text-slate-700">משתמשים</span>
                    </div>
                    <p className="text-2xl font-semibold text-slate-900">{business.stats.users}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <User className="h-5 w-5 text-purple-600" />
                      <span className="text-sm font-medium text-slate-700">לידים</span>
                    </div>
                    <p className="text-2xl font-semibold text-slate-900">{business.stats.leads}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Phone className="h-5 w-5 text-green-600" />
                      <span className="text-sm font-medium text-slate-700">שיחות היום</span>
                    </div>
                    <p className="text-2xl font-semibold text-slate-900">{business.stats.callsToday}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <MessageCircle className="h-5 w-5 text-emerald-600" />
                      <span className="text-sm font-medium text-slate-700">WhatsApp היום</span>
                    </div>
                    <p className="text-2xl font-semibold text-slate-900">{business.stats.waToday}</p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Activity className="h-5 w-5 text-orange-600" />
                      <span className="text-sm font-medium text-slate-700">לא נקראו</span>
                    </div>
                    <p className="text-2xl font-semibold text-slate-900">{business.stats.unread}</p>
                  </div>
                </div>

                {/* Business Details */}
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold text-slate-900">פרטי עסק</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-sm font-medium text-slate-700">דומיין</label>
                        <div className="flex items-center gap-2 mt-1">
                          <Globe className="h-4 w-4 text-slate-400" />
                          <span className="text-slate-600 direction-ltr">{business.domain}</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-slate-700">טלפון ראשי</label>
                        <div className="flex items-center gap-2 mt-1">
                          <Phone className="h-4 w-4 text-slate-400" />
                          <span className="text-slate-600 direction-ltr">{business.defaultPhoneE164}</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-slate-700">WhatsApp JID</label>
                        <div className="flex items-center gap-2 mt-1">
                          <MessageCircle className="h-4 w-4 text-slate-400" />
                          <span className="text-slate-600 direction-ltr text-sm">{business.whatsappJid}</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-slate-700">אזור זמן</label>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="h-4 w-4 text-slate-400" />
                          <span className="text-slate-600">{business.timezone}</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-sm font-medium text-slate-700">כתובת</label>
                        <div className="flex items-center gap-2 mt-1">
                          <MapPin className="h-4 w-4 text-slate-400" />
                          <span className="text-slate-600">{business.address}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold text-slate-900">שעות פעילות</h3>
                    <div className="space-y-2">
                      {Object.entries(business.businessHours).map(([day, hours]) => {
                        const dayNames: { [key: string]: string } = {
                          sun: 'ראשון',
                          mon: 'שני',
                          tue: 'שלישי',
                          wed: 'רביעי',
                          thu: 'חמישי',
                          fri: 'שישי',
                          sat: 'שבת'
                        };
                        
                        return (
                          <div key={day} className="flex justify-between items-center py-2 border-b border-slate-100">
                            <span className="text-sm font-medium text-slate-700">{dayNames[day]}</span>
                            <span className="text-sm text-slate-600">
                              {hours.length === 0 
                                ? 'סגור' 
                                : hours.map(h => `${h.from}-${h.to}`).join(', ')
                              }
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    
                    <div className="mt-6 pt-4 border-t border-slate-200">
                      <div className="text-sm text-slate-500 space-y-1">
                        <p>נוצר: {formatDate(business.createdAt)}</p>
                        <p>עודכן לאחרונה: {formatDate(business.updatedAt)}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Users Tab */}
            {activeTab === 'users' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-slate-900">משתמשי העסק</h3>
                  <span className="text-sm text-slate-500">{users.length} משתמשים</span>
                </div>
                
                <div className="space-y-3">
                  {users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
                          <User className="h-5 w-5 text-white" />
                        </div>
                        <div>
                          <h4 className="font-medium text-slate-900">{user.name}</h4>
                          <p className="text-sm text-slate-600">{user.email}</p>
                          <div className="flex items-center gap-4 mt-1">
                            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
                              {user.role}
                            </span>
                            <span className="text-xs text-slate-500">
                              התחבר לאחרונה: {formatDateTime(user.lastLogin)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => alert(`איפוס סיסמה עבור ${user.name} - בפיתוח`)}
                        className="flex items-center gap-2 px-3 py-1.5 text-orange-600 hover:bg-orange-50 rounded-lg transition-colors text-sm"
                      >
                        <Key className="h-4 w-4" />
                        איפוס סיסמה
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Integrations Tab */}
            {activeTab === 'integrations' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-slate-900">סטטוס אינטגרציות</h3>
                
                <div className="grid md:grid-cols-2 gap-6">
                  {/* Twilio */}
                  <div className="bg-slate-50 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <Phone className="h-6 w-6 text-blue-600" />
                        <h4 className="font-semibold text-slate-900">Twilio</h4>
                      </div>
                      <div className="flex items-center gap-2">
                        <Wifi className="h-4 w-4 text-green-600" />
                        <span className="text-sm font-medium text-green-600">מחובר</span>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">מספר ראשי:</span>
                        <span className="font-medium direction-ltr">{business.defaultPhoneE164}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Webhook בריאות:</span>
                        <span className="text-green-600">פעיל</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">שגיאה אחרונה:</span>
                        <span className="text-slate-500">אין</span>
                      </div>
                    </div>
                  </div>

                  {/* WhatsApp/Baileys */}
                  <div className="bg-slate-50 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <MessageCircle className="h-6 w-6 text-green-600" />
                        <h4 className="font-semibold text-slate-900">WhatsApp (Baileys)</h4>
                      </div>
                      <div className="flex items-center gap-2">
                        <Wifi className="h-4 w-4 text-green-600" />
                        <span className="text-sm font-medium text-green-600">מחובר</span>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">JID:</span>
                        <span className="font-medium direction-ltr text-xs">{business.whatsappJid}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">סטטוס סשן:</span>
                        <span className="text-green-600">פעיל</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">שגיאה אחרונה:</span>
                        <span className="text-slate-500">אין</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Audit Tab */}
            {activeTab === 'audit' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-slate-900">יומן ביקורת</h3>
                  <span className="text-sm text-slate-500">{auditEntries.length} פעולות אחרונות</span>
                </div>
                
                <div className="space-y-3">
                  {auditEntries.map((entry, index) => (
                    <div key={index} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900">{entry.actor}</span>
                            <span className="text-sm text-slate-600">ביצע</span>
                            <span className="text-sm font-medium text-slate-700">{entry.action}</span>
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-slate-500">
                            <span>{formatDateTime(entry.ts)}</span>
                            <span>IP: {entry.ip}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}