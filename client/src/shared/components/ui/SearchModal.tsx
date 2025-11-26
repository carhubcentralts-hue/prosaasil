import React from 'react'; // ✅ Classic JSX runtime
import { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  X, 
  User, 
  FileText, 
  DollarSign, 
  Phone, 
  Building2, 
  Calendar, 
  Settings,
  MessageCircle,
  ChevronRight,
  Clock
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { useAuth } from '../../../features/auth/hooks';

export interface SearchResult {
  id: string;
  type: 'client' | 'invoice' | 'call' | 'whatsapp' | 'meeting' | 'function' | 'business';
  title: string;
  subtitle?: string;
  description?: string;
  metadata?: {
    amount?: number;
    date?: string;
    status?: string;
    priority?: 'low' | 'medium' | 'high' | 'urgent';
    businessId?: number;
    businessName?: string;
    phone?: string;
    email?: string;
    lastActivity?: string;
  };
}

// Mock search data generator
function generateSearchResults(query: string, userRole: string, businessId?: number): SearchResult[] {
  if (!query || query.length < 2) return [];

  const allResults: SearchResult[] = [
    // Clients
    {
      id: 'client-1',
      type: 'client',
      title: 'לאה בן דוד',
      subtitle: '054-123-4567',
      description: 'מעוניינת בדירה 3 חדרים בתל אביב',
      metadata: {
        businessId: 1,
        businessName: 'ProSaaS',
        phone: '054-123-4567',
        email: 'leah@email.com',
        lastActivity: 'לפני 2 שעות',
        status: 'פעיל'
      }
    },
    {
      id: 'client-2',
      type: 'client',
      title: 'משה כהן',
      subtitle: '053-999-8888',
      description: 'מחפש משרד להשכרה במרכז',
      metadata: {
        businessId: 1,
        businessName: 'ProSaaS',
        phone: '053-999-8888',
        email: 'moshe@email.com',
        lastActivity: 'לפני יום',
        status: 'מעקב'
      }
    },
    {
      id: 'client-3',
      type: 'client',
      title: 'שרה לוי',
      subtitle: '052-777-6666',
      description: 'קניית דירה ברמת גן',
      metadata: {
        businessId: 2,
        businessName: 'נדלן טופ',
        phone: '052-777-6666',
        email: 'sarah@email.com',
        lastActivity: 'לפני 3 ימים',
        status: 'פוטנציאלי'
      }
    },
    // ⚠️ BILLING DISABLED - Invoices hidden until payments feature is activated
    // {
    //   id: 'invoice-1',
    //   type: 'invoice',
    //   title: 'חשבונית #1001',
    //   subtitle: 'לאה בן דוד',
    //   description: 'עמלת תיווך דירה',
    //   metadata: {
    //     businessId: 1,
    //     businessName: 'ProSaaS',
    //     amount: 25000,
    //     date: '15/12/2024',
    //     status: 'שולם'
    //   }
    // },
    // {
    //   id: 'invoice-2',
    //   type: 'invoice',
    //   title: 'חשבונית #1002',
    //   subtitle: 'דוד גרין',
    //   description: 'שכירות משרד',
    //   metadata: {
    //     businessId: 1,
    //     businessName: 'ProSaaS',
    //     amount: 15000,
    //     date: '20/12/2024',
    //     status: 'ממתין'
    //   }
    // },
    // Calls
    {
      id: 'call-1',
      type: 'call',
      title: 'שיחה עם לאה בן דוד',
      subtitle: '054-123-4567',
      description: 'שיחה של 3:45 דקות על דירה בתל אביב',
      metadata: {
        businessId: 1,
        businessName: 'ProSaaS',
        date: '25/12/2024',
        lastActivity: 'לפני שעתיים',
        status: 'הושלמה'
      }
    },
    // WhatsApp
    {
      id: 'whatsapp-1',
      type: 'whatsapp',
      title: 'הודעת WhatsApp ממשה כהן',
      subtitle: '053-999-8888',
      description: 'שאילתה על משרדים זמינים',
      metadata: {
        businessId: 1,
        businessName: 'ProSaaS',
        date: '25/12/2024',
        lastActivity: 'לפני שעה',
        status: 'נענה'
      }
    },
    // Meetings
    {
      id: 'meeting-1',
      type: 'meeting',
      title: 'פגישה עם שרה לוי',
      subtitle: 'יום ראשון 16:00',
      description: 'צפייה בדירה ברמת גן',
      metadata: {
        businessId: 1,
        businessName: 'ProSaaS',
        date: '29/12/2024',
        status: 'מתוכננת'
      }
    },
    // Functions (for admin/manager)
    {
      id: 'function-1',
      type: 'function',
      title: 'ניהול משתמשים',
      subtitle: 'מערכת',
      description: 'הוספה, עריכה ומחיקה של משתמשים',
      metadata: {
        lastActivity: 'זמין',
        status: 'פעיל'
      }
    },
    {
      id: 'function-2',
      type: 'function',
      title: 'דוחות מכירות',
      subtitle: 'מערכת',
      description: 'צפייה וייצוא דוחות מכירות',
      metadata: {
        lastActivity: 'זמין',
        status: 'פעיל'
      }
    },
    // Businesses (admin only)
    {
      id: 'business-1',
      type: 'business',
      title: 'ProSaaS CRM',
      subtitle: 'עסק פעיל',
      description: '8 משתמשים, 45 לקוחות פעילים',
      metadata: {
        businessId: 1,
        status: 'פעיל',
        lastActivity: 'לפני דקה'
      }
    },
    {
      id: 'business-2',
      type: 'business',
      title: 'נדלן טופ',
      subtitle: 'עסק פעיל',
      description: '3 משתמשים, 22 לקוחות פעילים',
      metadata: {
        businessId: 2,
        status: 'פעיל',
        lastActivity: 'לפני 5 דקות'
      }
    }
  ];

  // Filter by search query
  const queryLower = query.toLowerCase();
  let filteredResults = allResults.filter(result => 
    result.title.toLowerCase().includes(queryLower) ||
    result.subtitle?.toLowerCase().includes(queryLower) ||
    result.description?.toLowerCase().includes(queryLower)
  );

  // Apply role-based filtering
  if (userRole === 'admin' && businessId) {
    // Business admins only see their own business data
    filteredResults = filteredResults.filter(result => 
      result.type === 'function' || // Functions are available to all
      result.metadata?.businessId === businessId
    );
    // Remove business management for business admins
    filteredResults = filteredResults.filter(result => result.type !== 'business');
  } else if (userRole === 'agent' && businessId) {
    // Agents only see their own business data
    filteredResults = filteredResults.filter(result => 
      result.type === 'function' || // Functions are available to all
      result.metadata?.businessId === businessId
    );
    // Remove business management for agents
    filteredResults = filteredResults.filter(result => result.type !== 'business');
  } else if (userRole === 'owner' && businessId) {
    // Owners see all their business data plus management of their own business only
    filteredResults = filteredResults.filter(result => 
      result.type === 'function' || 
      (result.type === 'business' && result.metadata?.businessId === businessId) || // Only own business
      result.metadata?.businessId === businessId
    );
  } else if (userRole === 'system_admin') {
    // System admins see everything across all businesses
    // No filtering needed
  }

  return filteredResults.slice(0, 8); // Limit results
}

interface SearchResultItemProps {
  result: SearchResult;
  onClick: () => void;
}

function SearchResultItem({ result, onClick }: SearchResultItemProps) {
  const getIcon = () => {
    switch (result.type) {
      case 'client': return <User className="h-4 w-4" />;
      case 'invoice': return <FileText className="h-4 w-4" />;
      case 'call': return <Phone className="h-4 w-4" />;
      case 'whatsapp': return <MessageCircle className="h-4 w-4" />;
      case 'meeting': return <Calendar className="h-4 w-4" />;
      case 'function': return <Settings className="h-4 w-4" />;
      case 'business': return <Building2 className="h-4 w-4" />;
      default: return <Search className="h-4 w-4" />;
    }
  };

  const getIconColor = () => {
    switch (result.type) {
      case 'client': return 'text-purple-600';
      case 'invoice': return 'text-green-600';
      case 'call': return 'text-blue-600';
      case 'whatsapp': return 'text-emerald-600';
      case 'meeting': return 'text-orange-600';
      case 'function': return 'text-gray-600';
      case 'business': return 'text-indigo-600';
      default: return 'text-gray-600';
    }
  };

  const getTypeLabel = () => {
    switch (result.type) {
      case 'client': return 'לקוח';
      case 'invoice': return 'חשבונית';
      case 'call': return 'שיחה';
      case 'whatsapp': return 'WhatsApp';
      case 'meeting': return 'פגישה';
      case 'function': return 'פונקציה';
      case 'business': return 'עסק';
      default: return '';
    }
  };

  const getStatusColor = () => {
    switch (result.metadata?.status) {
      case 'פעיל': return 'bg-green-100 text-green-800';
      case 'שולם': return 'bg-green-100 text-green-800';
      case 'מתוכננת': return 'bg-blue-100 text-blue-800';
      case 'הושלמה': return 'bg-gray-100 text-gray-800';
      case 'ממתין': return 'bg-yellow-100 text-yellow-800';
      case 'מעקב': return 'bg-orange-100 text-orange-800';
      case 'פוטנציאלי': return 'bg-purple-100 text-purple-800';
      case 'נענה': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div 
      className="flex items-center gap-3 p-3 hover:bg-slate-50 transition-colors cursor-pointer rounded-lg group"
      onClick={onClick}
    >
      <div className={cn('p-2 rounded-lg bg-slate-100', getIconColor())}>
        {getIcon()}
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h4 className="font-medium text-slate-900 truncate">{result.title}</h4>
          <span className="text-xs bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full shrink-0">
            {getTypeLabel()}
          </span>
          {result.metadata?.status && (
            <span className={cn('text-xs px-2 py-0.5 rounded-full shrink-0', getStatusColor())}>
              {result.metadata.status}
            </span>
          )}
        </div>
        
        {result.subtitle && (
          <p className="text-sm text-slate-600 mb-1">{result.subtitle}</p>
        )}
        
        {result.description && (
          <p className="text-xs text-slate-500 line-clamp-2">{result.description}</p>
        )}
        
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
          {result.metadata?.amount && (
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {result.metadata.amount.toLocaleString()} ₪
            </span>
          )}
          {result.metadata?.date && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {result.metadata.date}
            </span>
          )}
          {result.metadata?.lastActivity && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {result.metadata.lastActivity}
            </span>
          )}
        </div>
      </div>
      
      <ChevronRight className="h-4 w-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
    </div>
  );
}

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SearchModal({ isOpen, onClose }: SearchModalProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Search with debouncing
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    const timeoutId = setTimeout(() => {
      const searchResults = generateSearchResults(query, user?.role || 'business', user?.business_id);
      setResults(searchResults);
      setIsLoading(false);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query, user?.role, user?.business_id]);

  // Handle keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleResultClick = (result: SearchResult) => {
    // In a real app, this would navigate to the specific item
    console.log('Clicked result:', result);
    alert(`פתיחת ${result.title} - ${getTypeLabel(result.type)}`);
    onClose();
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'client': return 'לקוח';
      case 'invoice': return 'חשבונית';
      case 'call': return 'שיחה';
      case 'whatsapp': return 'WhatsApp';
      case 'meeting': return 'פגישה';
      case 'function': return 'פונקציה';
      case 'business': return 'עסק';
      default: return '';
    }
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    inputRef.current?.focus();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-start justify-center z-50 p-4 pt-20">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[70vh] overflow-hidden shadow-xl">
        {/* Search Header */}
        <div className="flex items-center gap-3 p-4 border-b border-slate-200">
          <Search className="h-5 w-5 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            placeholder="חפש לקוחות, חשבוניות, פונקציות..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 text-lg placeholder-slate-400 bg-transparent outline-none"
            dir="rtl"
          />
          {query && (
            <button
              onClick={clearSearch}
              className="p-1 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <X className="h-4 w-4 text-slate-400" />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-slate-400" />
          </button>
        </div>

        {/* Search Results */}
        <div className="overflow-y-auto max-h-[50vh]">
          {!query.trim() ? (
            <div className="p-8 text-center text-slate-500">
              <Search className="h-12 w-12 mx-auto mb-3 text-slate-300" />
              <p className="text-lg font-medium mb-2">חיפוש מהיר</p>
              <p className="text-sm">
                חפש לקוחות, חשבוניות, שיחות, פגישות ופונקציות מערכת
              </p>
              {(user?.role === 'system_admin' || user?.role === 'owner') && (
                <p className="text-xs text-slate-400 mt-2">
                  כמנהל, אתה יכול לחפש בכל העסקים במערכת
                </p>
              )}
            </div>
          ) : isLoading ? (
            <div className="p-8 text-center text-slate-500">
              <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3"></div>
              <p>מחפש...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              <Search className="h-12 w-12 mx-auto mb-3 text-slate-300" />
              <p className="text-lg font-medium mb-2">לא נמצאו תוצאות</p>
              <p className="text-sm">
                נסה חיפוש אחר או בדוק את האיות
              </p>
            </div>
          ) : (
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-slate-600">
                  נמצאו {results.length} תוצאות עבור "{query}"
                </p>
                {(user?.role === 'system_admin' || user?.role === 'owner') && (
                  <span className="text-xs text-slate-400">
                    חיפוש גלובלי
                  </span>
                )}
              </div>
              {results.map((result) => (
                <SearchResultItem
                  key={result.id}
                  result={result}
                  onClick={() => handleResultClick(result)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Search Footer */}
        {query.trim() && !isLoading && (
          <div className="p-4 border-t border-slate-200 bg-slate-50">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>השתמש במקשי החצים לניווט</span>
              <span>Enter לפתיחה • Esc לסגירה</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}