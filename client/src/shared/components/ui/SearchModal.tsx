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
import { useNavigate } from 'react-router-dom';
import { cn } from '../../utils/cn';
import { useAuth } from '../../../features/auth/hooks';
import { http } from '../../../services/http';

export interface SearchResult {
  id: string | number;
  type: 'lead' | 'call' | 'whatsapp' | 'contact' | 'client' | 'invoice' | 'meeting' | 'function' | 'business';
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
    created_at?: string;
    lead_id?: number;
  };
}

interface SearchResultItemProps {
  result: SearchResult;
  onClick: () => void;
}

function SearchResultItem({ result, onClick }: SearchResultItemProps) {
  const getIcon = () => {
    const type = result.type;
    switch (type) {
      case 'lead':
      case 'client': return <User className="h-4 w-4" />;
      case 'contact': return <User className="h-4 w-4" />;
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
    const type = result.type;
    switch (type) {
      case 'lead':
      case 'client': return 'text-purple-600';
      case 'contact': return 'text-indigo-600';
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
    const type = result.type;
    switch (type) {
      case 'lead': return 'ליד';
      case 'client': return 'לקוח';
      case 'contact': return 'איש קשר';
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
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Search with debouncing and real API
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    const timeoutId = setTimeout(async () => {
      try {
        const response = await http.get<{
          query: string;
          results: {
            leads: SearchResult[];
            calls: SearchResult[];
            whatsapp: SearchResult[];
            contacts: SearchResult[];
          };
          total: number;
        }>(`/api/search?q=${encodeURIComponent(query)}&types=leads,calls,whatsapp,contacts&limit=5`);
        
        // Flatten all results into a single array
        const allResults: SearchResult[] = [
          ...response.results.leads,
          ...response.results.calls,
          ...response.results.whatsapp,
          ...response.results.contacts
        ];
        
        setResults(allResults);
      } catch (error) {
        console.error('Search error:', error);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 250); // 250ms debounce as specified

    return () => clearTimeout(timeoutId);
  }, [query]);

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
    // Navigate to the appropriate page based on result type
    onClose();
    
    switch (result.type) {
      case 'lead':
        navigate(`/app/leads`); // Navigate to leads page - could add lead detail if exists
        break;
      case 'call':
        navigate(`/app/calls`);
        break;
      case 'whatsapp':
        navigate(`/app/whatsapp`);
        break;
      case 'contact':
        navigate(`/app/users`);
        break;
      default:
        console.log('Navigation not configured for type:', result.type);
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'lead': return 'ליד';
      case 'client': return 'לקוח';
      case 'contact': return 'איש קשר';
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
            placeholder="חפש לידים, שיחות, WhatsApp, אנשי קשר..."
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
                חפש לידים, שיחות, WhatsApp ואנשי קשר
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