import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Phone, 
  PhoneOutgoing, 
  Users, 
  Loader2, 
  AlertTriangle, 
  CheckCircle2,
  XCircle,
  Plus,
  Search,
  PlayCircle
} from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { http } from '../../services/http';

interface OutboundTemplate {
  id: number;
  name: string;
  description: string;
  prompt_text: string;
  greeting_template: string;
}

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
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [callResults, setCallResults] = useState<CallResult[]>([]);

  const { data: templates = [], isLoading: templatesLoading } = useQuery<OutboundTemplate[]>({
    queryKey: ['/api/outbound_calls/templates'],
    select: (data: any) => data.templates || [],
  });

  const { data: counts, isLoading: countsLoading, refetch: refetchCounts } = useQuery<CallCounts>({
    queryKey: ['/api/outbound_calls/counts'],
    refetchInterval: 10000,
  });

  const { data: leadsData, isLoading: leadsLoading } = useQuery<{ leads: Lead[] }>({
    queryKey: ['/api/leads', searchQuery],
    enabled: true,
    select: (data: any) => ({ leads: data.leads || data || [] }),
  });

  const leads = leadsData?.leads || [];

  const startCallsMutation = useMutation({
    mutationFn: async (data: { lead_ids: number[], template_id?: number, custom_prompt?: string }) => {
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
      template_id: selectedTemplate || undefined,
      custom_prompt: customPrompt || undefined,
    });
  };

  const filteredLeads = leads.filter((lead: Lead) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      (lead.full_name && lead.full_name.toLowerCase().includes(query)) ||
      (lead.phone_e164 && lead.phone_e164.includes(query))
    );
  }).filter((lead: Lead) => lead.phone_e164);

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
          <h1 className="text-2xl font-bold text-gray-900">שיחות יוצאות</h1>
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  בחירת לידים ({selectedLeads.length}/3)
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
                <div className="space-y-2 max-h-96 overflow-y-auto">
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
          </div>

          <div className="space-y-4">
            <Card className="p-4">
              <h3 className="font-semibold mb-4">תבנית שיחה</h3>
              
              {templatesLoading ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-4 text-gray-500 text-sm">
                  אין תבניות מוגדרות
                </div>
              ) : (
                <div className="space-y-2">
                  {templates.map((template) => (
                    <div
                      key={template.id}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedTemplate === template.id
                          ? 'bg-blue-50 border-blue-300'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedTemplate(template.id)}
                      data-testid={`template-select-${template.id}`}
                    >
                      <div className="font-medium">{template.name}</div>
                      {template.description && (
                        <div className="text-sm text-gray-500 mt-1">{template.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  או הזן הנחיות מותאמות אישית:
                </label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="הזן הנחיות לבוט..."
                  className="w-full h-24 p-3 border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  dir="rtl"
                  data-testid="input-custom-prompt"
                />
              </div>
            </Card>

            <Button
              className="w-full"
              size="lg"
              disabled={
                selectedLeads.length === 0 ||
                (!selectedTemplate && !customPrompt) ||
                !canStartCalls ||
                startCallsMutation.isPending
              }
              onClick={handleStartCalls}
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

            {selectedLeads.length > availableSlots && availableSlots > 0 && (
              <div className="text-sm text-yellow-600 text-center">
                ניתן להפעיל רק {availableSlots} שיחות כרגע
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default OutboundCallsPage;
