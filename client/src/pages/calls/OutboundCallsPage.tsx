import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Phone, 
  PhoneOutgoing, 
  Users, 
  Loader2, 
  AlertTriangle, 
  CheckCircle2,
  XCircle,
  Search,
  PlayCircle
} from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { http } from '../../services/http';

interface Lead {
  id: number;
  full_name: string;
  phone_e164: string;
  status: string;
  created_at: string;
}

interface CallCounts {
  active_total: number;
  active_outbound: number;
  max_total: number;
  max_outbound: number;
}

interface CallResult {
  lead_id: number;
  lead_name: string;
  call_sid?: string;
  status: string;
  error?: string;
}

export function OutboundCallsPage() {
  const queryClient = useQueryClient();
  const [selectedLeads, setSelectedLeads] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [callResults, setCallResults] = useState<CallResult[]>([]);

  const { data: counts, isLoading: countsLoading, refetch: refetchCounts, error: countsError } = useQuery<CallCounts>({
    queryKey: ['/api/outbound_calls/counts'],
    refetchInterval: 10000,
    retry: 1,
  });

  const { data: leadsData, isLoading: leadsLoading, error: leadsError } = useQuery<{ leads: Lead[] }>({
    queryKey: ['/api/leads', searchQuery],
    enabled: true,
    select: (data: any) => {
      if (!data) return { leads: [] };
      if (Array.isArray(data)) return { leads: data };
      if (data.items && Array.isArray(data.items)) return { leads: data.items };
      if (data.leads && Array.isArray(data.leads)) return { leads: data.leads };
      return { leads: [] };
    },
    retry: 1,
  });

  const leads = Array.isArray(leadsData?.leads) ? leadsData.leads : [];

  const startCallsMutation = useMutation({
    mutationFn: async (data: { lead_ids: number[] }) => {
      return await http.post<any>('/api/outbound_calls/start', data);
    },
    onSuccess: (data) => {
      setCallResults(data.calls || []);
      setShowResults(true);
      refetchCounts();
      queryClient.invalidateQueries({ queryKey: ['/api/calls'] });
    },
    onError: (error: any) => {
      const errorMessage = error?.message || error?.error || 'שגיאה בהפעלת השיחות';
      setCallResults([{ 
        lead_id: 0, 
        lead_name: 'שגיאה', 
        status: 'failed', 
        error: errorMessage 
      }]);
      setShowResults(true);
    },
  });

  const handleToggleLead = (leadId: number) => {
    setSelectedLeads(prev => {
      if (prev.includes(leadId)) {
        return prev.filter(id => id !== leadId);
      }
      const maxSelectable = Math.min(3, availableSlots);
      if (prev.length >= maxSelectable) {
        return prev;
      }
      return [...prev, leadId];
    });
  };

  const handleStartCalls = () => {
    if (selectedLeads.length === 0) return;
    
    startCallsMutation.mutate({
      lead_ids: selectedLeads,
    });
  };

  const filteredLeads = (Array.isArray(leads) ? leads : []).filter((lead: Lead) => {
    if (!lead) return false;
    if (!searchQuery) return lead.phone_e164;
    const query = searchQuery.toLowerCase();
    return (
      lead.phone_e164 && (
        (lead.full_name && lead.full_name.toLowerCase().includes(query)) ||
        lead.phone_e164.includes(query)
      )
    );
  });

  const canStartCalls = counts 
    ? (counts.active_outbound < counts.max_outbound && counts.active_total < counts.max_total)
    : true;

  const availableSlots = counts 
    ? Math.min(counts.max_outbound - counts.active_outbound, counts.max_total - counts.active_total)
    : 3;

  return (
    <div className="p-6 space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PhoneOutgoing className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">שיחות יוצאות</h1>
            <p className="text-sm text-gray-500">בחר לידים והפעל שיחות AI יוצאות</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {counts && (
            <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">
              <Phone className="h-4 w-4" />
              <span>
                שיחות פעילות: {counts.active_total}/{counts.max_total}
              </span>
              <span className="mx-2">|</span>
              <PhoneOutgoing className="h-4 w-4" />
              <span>
                יוצאות: {counts.active_outbound}/{counts.max_outbound}
              </span>
            </div>
          )}
        </div>
      </div>

      {(leadsError || countsError) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <XCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">
            שגיאה בטעינת נתונים. נסה לרענן את הדף.
          </span>
        </div>
      )}

      {!canStartCalls && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <span className="text-yellow-800">
            כרגע יש יותר מדי שיחות פעילות. המתן לסיום חלק מהשיחות ונסה שוב.
          </span>
        </div>
      )}

      {showResults && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">תוצאות השיחות</h3>
          <div className="space-y-2">
            {callResults.map((result) => (
              <div 
                key={result.lead_id}
                className={`flex items-center justify-between p-3 rounded-lg ${
                  result.status === 'initiated' ? 'bg-green-50' : 'bg-red-50'
                }`}
              >
                <div className="flex items-center gap-2">
                  {result.status === 'initiated' ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-600" />
                  )}
                  <span>{result.lead_name}</span>
                </div>
                <span className="text-sm text-gray-500">
                  {result.status === 'initiated' ? 'השיחה הופעלה' : result.error}
                </span>
              </div>
            ))}
          </div>
          <Button 
            variant="secondary"
            className="mt-4"
            onClick={() => {
              setShowResults(false);
              setSelectedLeads([]);
              setCallResults([]);
            }}
            data-testid="button-new-calls"
          >
            הפעל שיחות נוספות
          </Button>
        </Card>
      )}

      {!showResults && (
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Users className="h-5 w-5" />
                בחירת לידים ({selectedLeads.length}/{Math.min(3, availableSlots)})
              </h3>
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="חיפוש לפי שם או טלפון..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pr-10 w-64"
                  data-testid="input-lead-search"
                />
              </div>
            </div>

            {leadsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {searchQuery ? 'לא נמצאו לידים מתאימים' : 'אין לידים עם מספר טלפון'}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
                {filteredLeads.slice(0, 50).map((lead: Lead) => {
                  const maxSelectable = Math.min(3, availableSlots);
                  const isDisabled = selectedLeads.length >= maxSelectable && !selectedLeads.includes(lead.id);
                  
                  return (
                  <div
                    key={lead.id}
                    className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedLeads.includes(lead.id)
                        ? 'bg-blue-50 border-blue-300'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    onClick={() => !isDisabled && handleToggleLead(lead.id)}
                    data-testid={`lead-select-${lead.id}`}
                  >
                    <div>
                      <div className="font-medium">{lead.full_name || 'ללא שם'}</div>
                      <div className="text-sm text-gray-500" dir="ltr">{lead.phone_e164}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-gray-100 px-2 py-1 rounded">{lead.status}</span>
                      {selectedLeads.includes(lead.id) && (
                        <CheckCircle2 className="h-5 w-5 text-blue-600" />
                      )}
                    </div>
                  </div>
                );})}
              </div>
            )}
          </Card>

          <div className="flex justify-center">
            <Button
              size="lg"
              disabled={
                selectedLeads.length === 0 ||
                !canStartCalls ||
                startCallsMutation.isPending
              }
              onClick={handleStartCalls}
              className="px-8"
              data-testid="button-start-calls"
            >
              {startCallsMutation.isPending ? (
                <>
                  <Loader2 className="h-5 w-5 ml-2 animate-spin" />
                  מתחיל שיחות...
                </>
              ) : (
                <>
                  <PlayCircle className="h-5 w-5 ml-2" />
                  הפעל {selectedLeads.length} שיחות
                </>
              )}
            </Button>
          </div>

          <p className="text-sm text-gray-500 text-center">
            ה-AI ישתמש בפרומפט שיחות יוצאות מהגדרות המערכת
          </p>

          {selectedLeads.length > availableSlots && availableSlots > 0 && (
            <div className="text-sm text-yellow-600 text-center">
              ניתן להפעיל רק {availableSlots} שיחות כרגע
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default OutboundCallsPage;
