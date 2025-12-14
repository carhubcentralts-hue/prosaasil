import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, User, Clock, MessageSquare, Loader2, Search } from 'lucide-react';
import { http } from '../../services/http';

// Simple UI components
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`border border-gray-200 rounded-lg bg-white shadow-sm ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline";
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center disabled:opacity-50";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
  };
  return (
    <button className={`${baseClasses} ${variantClasses[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
};

const Badge = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <span className={`px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800 ${className}`}>
    {children}
  </span>
);

// Lead interface
interface Lead {
  id: number;
  full_name: string;
  phone_e164: string;
  display_phone: string;
  status: string;
  summary?: string;
  last_contact_at: string;
  created_at: string;
}

export function InboundCallsPage() {
  const navigate = useNavigate();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 25;

  useEffect(() => {
    loadInboundLeads();
  }, [page, searchQuery]);

  const loadInboundLeads = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        direction: 'inbound',
        page: page.toString(),
        pageSize: pageSize.toString(),
      });
      
      if (searchQuery) {
        params.append('q', searchQuery);
      }

      const response = await http.get(`/api/leads?${params.toString()}`);
      
      if (response && typeof response === 'object') {
        const items = (response as any).items || [];
        setLeads(items);
        const total = (response as any).total || 0;
        setTotalPages(Math.ceil(total / pageSize));
      } else {
        setLeads([]);
        setTotalPages(1);
      }
    } catch (error) {
      console.error('Error loading inbound leads:', error);
      setLeads([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `לפני ${diffMins} דקות`;
    } else if (diffHours < 24) {
      return `לפני ${diffHours} שעות`;
    } else if (diffDays < 7) {
      return `לפני ${diffDays} ימים`;
    } else {
      return date.toLocaleDateString('he-IL', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
      });
    }
  };

  const handleLeadClick = (leadId: number) => {
    navigate(`/app/leads/${leadId}`);
  };

  if (loading && leads.length === 0) {
    return (
      <div className="flex items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-100 rounded-full">
            <Phone className="h-6 w-6 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">שיחות נכנסות</h1>
            <p className="text-slate-600 mt-1">לידים שנוצרו משיחות נכנסות למערכת</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="search"
            placeholder="חפש לפי שם או טלפון..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full pr-10 px-3 py-2 border border-slate-300 rounded-md"
            data-testid="input-search-inbound"
          />
        </div>
      </Card>

      {/* Leads List */}
      {leads.length === 0 ? (
        <Card className="p-12 text-center">
          <Phone className="h-12 w-12 mx-auto mb-4 text-slate-400" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">אין שיחות נכנסות</h3>
          <p className="text-slate-600">
            {searchQuery ? 'לא נמצאו לידים התואמים לחיפוש' : 'עדיין לא היו שיחות נכנסות במערכת'}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {leads.map((lead) => (
            <Card
              key={lead.id}
              className="p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => handleLeadClick(lead.id)}
              data-testid={`lead-card-${lead.id}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 flex-1">
                  <div className="p-2 bg-green-100 rounded-full">
                    <User className="h-5 w-5 text-green-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-slate-900 text-lg">
                        {lead.full_name || 'לקוח אלמוני'}
                      </h3>
                      <Badge>{lead.status}</Badge>
                    </div>
                    <p className="text-sm text-slate-600 mb-2" dir="ltr">
                      {lead.display_phone || lead.phone_e164}
                    </p>
                    {lead.summary && (
                      <div className="flex items-start gap-2 mb-2">
                        <MessageSquare className="h-4 w-4 text-slate-400 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-slate-700 line-clamp-2">
                          {lead.summary}
                        </p>
                      </div>
                    )}
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Clock className="h-3 w-3" />
                      <span>{formatDate(lead.last_contact_at || lead.created_at)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            data-testid="button-prev-page"
          >
            הקודם
          </Button>
          <span className="text-sm text-slate-600">
            עמוד {page} מתוך {totalPages}
          </span>
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            data-testid="button-next-page"
          >
            הבא
          </Button>
        </div>
      )}
    </div>
  );
}

export default InboundCallsPage;
