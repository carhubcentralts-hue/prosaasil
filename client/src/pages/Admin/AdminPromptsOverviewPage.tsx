import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Bot, 
  Phone, 
  MessageSquare, 
  Edit3,
  History,
  Building2,
  Calendar,
  Loader2,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';
import { Card } from '../../shared/components/ui/Card';
import { Badge } from '../../shared/components/Badge';
import { http } from '../../services/http';

interface BusinessPrompt {
  business_id: number;
  business_name: string;
  calls_prompt: string;
  whatsapp_prompt: string;
  last_updated: string;
  version: number;
  calls_prompt_length: number;
  whatsapp_prompt_length: number;
  has_calls_prompt: boolean;
  has_whatsapp_prompt: boolean;
}

export function AdminPromptsOverviewPage() {
  const navigate = useNavigate();
  const [businesses, setBusinesses] = useState<BusinessPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBusinessPrompts();
  }, []);

  const loadBusinessPrompts = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await http.get<{ businesses: BusinessPrompt[] }>('/api/admin/businesses/prompts');
      setBusinesses(response.businesses);
    } catch (err) {
      console.error('❌ Failed to load business prompts:', err);
      setError('שגיאה בטעינת נתוני prompts');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'לא עודכן';
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getPromptStatus = (hasPrompt: boolean, length: number) => {
    if (!hasPrompt) return { variant: 'error' as const, text: 'לא הוגדר', icon: <AlertTriangle className="h-3 w-3" /> };
    if (length < 50) return { variant: 'warning' as const, text: 'קצר', icon: <AlertTriangle className="h-3 w-3" /> };
    return { variant: 'success' as const, text: 'מוגדר', icon: <CheckCircle className="h-3 w-3" /> };
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-slate-600">טוען נתוני AI Prompts של כל העסקים...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card className="p-6 bg-red-50 border-red-200 max-w-md mx-auto">
          <div className="flex items-center gap-3 text-red-700">
            <AlertTriangle className="h-5 w-5" />
            <div>
              <p className="font-medium">שגיאה בטעינת הנתונים</p>
              <p className="text-sm text-red-600">{error}</p>
              <button 
                onClick={loadBusinessPrompts}
                className="text-sm underline hover:no-underline mt-1"
              >
                נסה שוב
              </button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <Bot className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-slate-900">ניהול AI Prompts</h1>
        </div>
        
        <div className="flex items-center justify-between">
          <p className="text-slate-600">נהל את הגדרות ה-AI Agent של כל העסקים במערכת</p>
          
          <div className="flex items-center gap-4">
            <Badge variant="neutral">{businesses.length} עסקים</Badge>
            <button
              onClick={loadBusinessPrompts}
              data-testid="refresh-prompts"
              className="flex items-center gap-2 px-3 py-1.5 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm"
            >
              <History className="h-4 w-4" />
              רענן
            </button>
          </div>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">סה״כ עסקים</p>
              <p className="text-2xl font-bold text-slate-900">{businesses.length}</p>
            </div>
            <Building2 className="h-8 w-8 text-blue-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">Prompts שיחות</p>
              <p className="text-2xl font-bold text-green-600">
                {businesses.filter(b => b.has_calls_prompt).length}
              </p>
            </div>
            <Phone className="h-8 w-8 text-green-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">Prompts WhatsApp</p>
              <p className="text-2xl font-bold text-green-600">
                {businesses.filter(b => b.has_whatsapp_prompt).length}
              </p>
            </div>
            <MessageSquare className="h-8 w-8 text-green-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">ללא prompts</p>
              <p className="text-2xl font-bold text-red-600">
                {businesses.filter(b => !b.has_calls_prompt && !b.has_whatsapp_prompt).length}
              </p>
            </div>
            <AlertTriangle className="h-8 w-8 text-red-500" />
          </div>
        </Card>
      </div>

      {/* Businesses List */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">עסקים ו-Prompts</h3>
        
        {businesses.length > 0 ? businesses.map((business) => {
          const callsStatus = getPromptStatus(business.has_calls_prompt, business.calls_prompt_length);
          const whatsappStatus = getPromptStatus(business.has_whatsapp_prompt, business.whatsapp_prompt_length);
          
          return (
            <Card key={business.business_id} className="p-6 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <Building2 className="h-5 w-5 text-slate-400" />
                    <h4 className="text-lg font-semibold text-slate-900">{business.business_name}</h4>
                    <Badge variant="neutral" className="text-xs">ID: {business.business_id}</Badge>
                  </div>
                  
                  {/* Prompts Status */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                      <Phone className="h-4 w-4 text-blue-600" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-slate-900">פרומפט שיחות</span>
                          <Badge variant={callsStatus.variant} className="text-xs">
                            {callsStatus.icon}
                            {callsStatus.text}
                          </Badge>
                        </div>
                        <p className="text-xs text-slate-600">
                          {business.has_calls_prompt 
                            ? `${business.calls_prompt_length} תווים`
                            : 'לא הוגדר prompt לשיחות'
                          }
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                      <MessageSquare className="h-4 w-4 text-green-600" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-slate-900">פרומפט WhatsApp</span>
                          <Badge variant={whatsappStatus.variant} className="text-xs">
                            {whatsappStatus.icon}
                            {callsStatus.text === 'מוגדר' ? 'זהה לשיחות' : whatsappStatus.text}
                          </Badge>
                        </div>
                        <p className="text-xs text-slate-600">
                          {business.has_whatsapp_prompt 
                            ? 'משתמש באותו prompt כמו שיחות'
                            : 'לא הוגדר prompt ל-WhatsApp'
                          }
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Meta Info */}
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <div className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      עדכון אחרון: {formatDate(business.last_updated)}
                    </div>
                    {business.version > 1 && (
                      <div className="flex items-center gap-1">
                        <History className="h-3 w-3" />
                        גרסה {business.version}
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/app/admin/businesses/${business.business_id}/agent`)}
                    data-testid={`edit-prompts-${business.business_id}`}
                    className="flex items-center gap-2 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
                  >
                    <Edit3 className="h-4 w-4" />
                    ערוך Prompts
                  </button>
                </div>
              </div>
            </Card>
          );
        }) : (
          <Card className="p-12 text-center">
            <Bot className="h-12 w-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-900 mb-2">אין עסקים במערכת</h3>
            <p className="text-slate-600">כאשר יתווספו עסקים, תוכל לנהל את ה-AI Prompts שלהם כאן.</p>
          </Card>
        )}
      </div>
    </div>
  );
}