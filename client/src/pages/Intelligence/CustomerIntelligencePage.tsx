import type * as React from 'react';
import { useState, useEffect } from 'react';
import { 
  Brain, 
  Phone, 
  MessageSquare, 
  Users, 
  TrendingUp, 
  Clock, 
  Bot, 
  Zap,
  FileText,
  User,
  Calendar,
  PlayCircle,
  Eye,
  Target,
  Activity
} from 'lucide-react';
import { http } from '../../services/http';

// Temporary UI components
const Card = ({ children, className = "", onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`} onClick={onClick}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50", 
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive" | "info";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800",
    info: "bg-blue-100 text-blue-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Interface definitions
interface IntelligentCustomer {
  id: number;
  name: string;
  phone_e164: string;
  source: 'call' | 'whatsapp' | 'manual';
  created_at: string;
  last_interaction: string;
  leads_count: number;
  calls_count: number;
  whatsapp_count: number;
  latest_lead?: {
    id: number;
    status: string;
    area?: string;
    property_type?: string;
    notes?: string;
    ai_summary?: string;
    intent?: string;
    next_action?: string;
  };
  recent_activity: Array<{
    type: 'call' | 'whatsapp' | 'lead_update';
    timestamp: string;
    content: string;
    ai_summary?: string;
  }>;
}

interface IntelligenceStats {
  total_customers: number;
  new_customers_today: number;
  total_leads: number;
  new_leads_today: number;
  call_conversion_rate: number;
  whatsapp_conversion_rate: number;
  ai_processed_interactions: number;
  meeting_ready_leads: number;
}

export default function CustomerIntelligencePage() {
  const [customers, setCustomers] = useState<IntelligentCustomer[]>([]);
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState<IntelligentCustomer | null>(null);
  const [filterSource, setFilterSource] = useState<'all' | 'call' | 'whatsapp'>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'leads' | 'name'>('recent');

  useEffect(() => {
    loadIntelligenceData();
  }, [filterSource, sortBy]);

  const loadIntelligenceData = async () => {
    try {
      setLoading(true);
      
      // Load customers with intelligence data
      const customersResponse = await http.get(`/api/intelligence/customers?source=${filterSource}&sort=${sortBy}`);
      setCustomers((customersResponse as any).data || []);
      
      // Load intelligence statistics  
      const statsResponse = await http.get('/api/intelligence/stats');
      setStats((statsResponse as any).data || null);
      
    } catch (error) {
      console.error('Failed to load intelligence data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'call': return <Phone className="h-4 w-4" />;
      case 'whatsapp': return <MessageSquare className="h-4 w-4" />;
      default: return <User className="h-4 w-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'חדש': return 'info';
      case 'בניסיון קשר': return 'warning';
      case 'נוצר קשר': return 'default';
      case 'מוכשר': return 'success';
      case 'זכיה': return 'success';
      case 'אובדן': return 'destructive';
      default: return 'default';
    }
  };

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now.getTime() - time.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffHours < 1) return 'לפני פחות משעה';
    if (diffHours < 24) return `לפני ${diffHours} שעות`;
    return `לפני ${diffDays} ימים`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center space-x-2">
          <Bot className="h-6 w-6 animate-spin text-blue-600" />
          <span>טוען מערכת אינטליגנציה...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <Brain className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">מערכת אינטליגנציה לקוחות</h1>
            <p className="text-gray-600">זיהוי אוטומטי ועיבוד חכם של שיחות ו-WhatsApp</p>
          </div>
        </div>
        <Button onClick={loadIntelligenceData} variant="outline" size="sm">
          <Activity className="h-4 w-4 ml-2" />
          רענן נתונים
        </Button>
      </div>

      {/* Statistics Dashboard */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">סה״כ לקוחות</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_customers}</p>
                <p className="text-xs text-green-600">+{stats.new_customers_today} היום</p>
              </div>
              <Users className="h-8 w-8 text-blue-600" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">סה״כ לידים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_leads}</p>
                <p className="text-xs text-green-600">+{stats.new_leads_today} היום</p>
              </div>
              <Target className="h-8 w-8 text-green-600" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">המרת שיחות</p>
                <p className="text-2xl font-bold text-gray-900">{stats.call_conversion_rate}%</p>
                <p className="text-xs text-blue-600">WhatsApp: {stats.whatsapp_conversion_rate}%</p>
              </div>
              <TrendingUp className="h-8 w-8 text-purple-600" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">עיבוד AI</p>
                <p className="text-2xl font-bold text-gray-900">{stats.ai_processed_interactions}</p>
                <p className="text-xs text-orange-600">מוכנים לפגישה: {stats.meeting_ready_leads}</p>
              </div>
              <Bot className="h-8 w-8 text-orange-600" />
            </div>
          </Card>
        </div>
      )}

      {/* Filters and Controls */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">מקור:</label>
            <select 
              value={filterSource} 
              onChange={(e) => setFilterSource(e.target.value as any)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="all">הכל</option>
              <option value="call">שיחות טלפון</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>
          
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">מיון:</label>
            <select 
              value={sortBy} 
              onChange={(e) => setSortBy(e.target.value as any)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="recent">אחרונים</option>
              <option value="leads">לפי לידים</option>
              <option value="name">לפי שם</option>
            </select>
          </div>
        </div>
        
        <div className="text-sm text-gray-600">
          {customers.length} לקוחות נמצאו
        </div>
      </div>

      {/* Customers Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {customers.map((customer) => (
          <Card key={customer.id} className="p-6 hover:shadow-md transition-shadow cursor-pointer" 
                onClick={() => setSelectedCustomer(customer)}>
            {/* Customer Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                {getSourceIcon(customer.source)}
                <div>
                  <h3 className="font-semibold text-gray-900">{customer.name}</h3>
                  <p className="text-sm text-gray-600">{customer.phone_e164}</p>
                </div>
              </div>
              {customer.latest_lead && (
                <Badge variant={getStatusColor(customer.latest_lead.status)}>
                  {customer.latest_lead.status}
                </Badge>
              )}
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-3 gap-4 mb-4 text-center">
              <div>
                <p className="text-lg font-bold text-blue-600">{customer.leads_count}</p>
                <p className="text-xs text-gray-600">לידים</p>
              </div>
              <div>
                <p className="text-lg font-bold text-green-600">{customer.calls_count}</p>
                <p className="text-xs text-gray-600">שיחות</p>
              </div>
              <div>
                <p className="text-lg font-bold text-purple-600">{customer.whatsapp_count}</p>
                <p className="text-xs text-gray-600">WhatsApp</p>
              </div>
            </div>

            {/* Latest Lead Info */}
            {customer.latest_lead && (
              <div className="mb-4 p-3 bg-gray-50 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">ליד אחרון:</span>
                  {customer.latest_lead.intent && (
                    <Badge variant="info" className="text-xs">
                      {customer.latest_lead.intent}
                    </Badge>
                  )}
                </div>
                
                {customer.latest_lead.area && (
                  <p className="text-sm text-gray-600 mb-1">
                    📍 {customer.latest_lead.area}
                    {customer.latest_lead.property_type && ` • ${customer.latest_lead.property_type}`}
                  </p>
                )}
                
                {customer.latest_lead.ai_summary && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500 mb-1">סיכום AI:</p>
                    <p className="text-sm text-gray-700 bg-white p-2 rounded border">
                      {customer.latest_lead.ai_summary}
                    </p>
                  </div>
                )}

                {customer.latest_lead.next_action && (
                  <div className="mt-2 flex items-center text-sm text-orange-600">
                    <Zap className="h-3 w-3 ml-1" />
                    {customer.latest_lead.next_action}
                  </div>
                )}
              </div>
            )}

            {/* Last Activity */}
            <div className="border-t pt-3">
              <p className="text-xs text-gray-500 mb-1">פעילות אחרונה:</p>
              <p className="text-sm text-gray-700">{formatTimeAgo(customer.last_interaction)}</p>
              
              {customer.recent_activity.length > 0 && (
                <div className="mt-2">
                  {customer.recent_activity.slice(0, 2).map((activity, idx) => (
                    <div key={idx} className="flex items-center text-xs text-gray-600 mb-1">
                      {activity.type === 'call' && <Phone className="h-3 w-3 ml-1" />}
                      {activity.type === 'whatsapp' && <MessageSquare className="h-3 w-3 ml-1" />}
                      {activity.type === 'lead_update' && <FileText className="h-3 w-3 ml-1" />}
                      <span className="truncate">{activity.content}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between mt-4 pt-3 border-t">
              <Button variant="outline" size="sm" onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                // Navigate to customer details
              }}>
                <Eye className="h-3 w-3 ml-1" />
                פרטים
              </Button>
              
              {customer.latest_lead?.next_action?.includes('פגישה') && (
                <Button variant="default" size="sm" onClick={(e: React.MouseEvent) => {
                  e.stopPropagation();
                  // Schedule meeting
                }}>
                  <Calendar className="h-3 w-3 ml-1" />
                  תאום פגישה
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {customers.length === 0 && !loading && (
        <div className="text-center py-12">
          <Brain className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">אין נתוני אינטליגנציה</h3>
          <p className="text-gray-600 mb-4">
            המערכת החכמה תתחיל לעקוב אחרי לקוחות ברגע שיהיו שיחות או הודעות WhatsApp
          </p>
        </div>
      )}

      {/* Customer Detail Modal */}
      {selectedCustomer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-2xl w-full mx-4 max-h-96 overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold">פרטי לקוח - {selectedCustomer.name}</h2>
                <Button variant="ghost" onClick={() => setSelectedCustomer(null)}>
                  ✕
                </Button>
              </div>
              
              {/* Detailed customer information would go here */}
              <div className="space-y-4">
                <p><strong>טלפון:</strong> {selectedCustomer.phone_e164}</p>
                <p><strong>מקור:</strong> {selectedCustomer.source}</p>
                <p><strong>נוצר:</strong> {new Date(selectedCustomer.created_at).toLocaleDateString('he-IL')}</p>
                
                {selectedCustomer.latest_lead && (
                  <div>
                    <h4 className="font-semibold mb-2">ליד אחרון:</h4>
                    <p><strong>סטטוס:</strong> {selectedCustomer.latest_lead.status}</p>
                    {selectedCustomer.latest_lead.notes && (
                      <p><strong>הערות:</strong> {selectedCustomer.latest_lead.notes}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}