import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Users, 
  Phone,
  PlayCircle,
  UserPlus,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Search,
  Filter,
  Edit,
  Save,
  X
} from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Card } from '../../../shared/components/ui/Card';
import { Input } from '../../../shared/components/ui/Input';
import { MultiStatusSelect } from '../../../shared/components/ui/MultiStatusSelect';
import { StatusDropdownWithWebhook } from '../../../shared/components/ui/StatusDropdownWithWebhook';
import { formatDate } from '../../../shared/utils/format';
import { http } from '../../../services/http';
import type { LeadStatusConfig } from '../../../shared/types/status';

interface ProjectLead {
  id: number;
  full_name: string;
  phone_e164: string;
  status: string;
  call_attempts: number;
  last_call_at: string | null;
  last_call_status: string | null;
  total_call_duration: number;
  added_at: string;
}

interface ProjectDetailViewProps {
  projectId: number;
  onBack: () => void;
  onStartCalls: (leadIds: number[]) => void;
  statuses: LeadStatusConfig[];
  hasWebhook: boolean;
}

export function ProjectDetailView({
  projectId,
  onBack,
  onStartCalls,
  statuses,
  hasWebhook
}: ProjectDetailViewProps) {
  const navigate = useNavigate();
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [showAddLeads, setShowAddLeads] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [editingDescription, setEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState('');
  const [updatingStatusLeadId, setUpdatingStatusLeadId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  const loadProject = async () => {
    try {
      setLoading(true);
      const data = await http.get<any>(`/api/projects/${projectId}`);
      setProject(data.project);
      setEditedName(data.project.name);
      setEditedDescription(data.project.description || '');
    } catch (error) {
      console.error('Error loading project:', error);
      alert('שגיאה בטעינת הפרויקט');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateName = async () => {
    if (!editedName.trim()) {
      alert('שם פרויקט חובה');
      return;
    }
    try {
      await http.patch<any>(`/api/projects/${projectId}`, { name: editedName });
      setProject({ ...project, name: editedName });
      setEditingName(false);
    } catch (error) {
      console.error('Error updating project name:', error);
      alert('שגיאה בעדכון שם הפרויקט');
    }
  };

  const handleUpdateDescription = async () => {
    try {
      await http.patch<any>(`/api/projects/${projectId}`, { description: editedDescription });
      setProject({ ...project, description: editedDescription });
      setEditingDescription(false);
    } catch (error) {
      console.error('Error updating project description:', error);
      alert('שגיאה בעדכון התיאור');
    }
  };

  const handleStartProjectCalls = () => {
    if (selectedLeadIds.size === 0) {
      alert('יש לבחור לפחות ליד אחד');
      return;
    }
    onStartCalls(Array.from(selectedLeadIds));
  };

  const handleStartAllCalls = () => {
    if (!project?.leads || project.leads.length === 0) {
      alert('אין לידים בפרויקט');
      return;
    }
    onStartCalls(project.leads.map((l: ProjectLead) => l.id));
  };

  const handleToggleLead = (leadId: number) => {
    const newSet = new Set(selectedLeadIds);
    if (newSet.has(leadId)) {
      newSet.delete(leadId);
    } else {
      newSet.add(leadId);
    }
    setSelectedLeadIds(newSet);
  };

  const handleSelectAll = () => {
    const leadsToSelect = filteredLeads;
    if (selectedLeadIds.size === leadsToSelect.length) {
      setSelectedLeadIds(new Set());
    } else {
      setSelectedLeadIds(new Set(leadsToSelect.map((l: ProjectLead) => l.id)));
    }
  };

  const handleRemoveLeads = async () => {
    if (selectedLeadIds.size === 0) {
      alert('יש לבחור לידים להסרה');
      return;
    }
    
    if (!confirm(`האם למחוק ${selectedLeadIds.size} לידים מהפרויקט?`)) {
      return;
    }

    try {
      await http.post<any>(`/api/projects/${projectId}/remove-leads`, {
        lead_ids: Array.from(selectedLeadIds)
      });
      setSelectedLeadIds(new Set());
      await loadProject();
    } catch (error) {
      console.error('Error removing leads:', error);
      alert('שגיאה בהסרת לידים');
    }
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    setUpdatingStatusLeadId(leadId);
    try {
      await http.patch<any>(`/api/leads/${leadId}/status`, { status: newStatus });
      await loadProject();
    } catch (error) {
      console.error('Error updating lead status:', error);
      alert('שגיאה בעדכון סטטוס');
    } finally {
      setUpdatingStatusLeadId(null);
    }
  };

  const handleLeadClick = (leadId: number) => {
    const params = new URLSearchParams();
    params.set('from', 'project_detail');
    params.set('project_id', projectId.toString());
    navigate(`/app/leads/${leadId}?${params.toString()}`);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600';
      case 'completed': return 'text-blue-600';
      case 'paused': return 'text-yellow-600';
      case 'draft':
      default: return 'text-gray-600';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'completed': return 'הושלם';
      case 'paused': return 'מושהה';
      case 'draft':
      default: return 'טיוטה';
    }
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '0 דק\'';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} דק'`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours} שעה ${remainingMinutes} דק'`;
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-12 w-12 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <XCircle className="h-16 w-16 mx-auto mb-4 text-red-400" />
        <p className="text-gray-600">פרויקט לא נמצא</p>
        <Button onClick={onBack} className="mt-4">חזור</Button>
      </div>
    );
  }

  const hasStarted = project.stats !== null && project.stats !== undefined;

  // Filter leads by selected statuses
  const filteredLeads = project.leads.filter((lead: ProjectLead) => {
    if (statusFilter.length === 0) {
      return true; // No filter = show all
    }
    return statusFilter.includes(lead.status);
  });

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            onClick={onBack}
            className="min-h-[44px] min-w-[44px]"
            data-testid="button-back"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            {editingName ? (
              <div className="flex items-center gap-2">
                <Input
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  className="text-xl font-bold"
                  autoFocus
                  data-testid="input-edit-name"
                />
                <Button onClick={handleUpdateName} size="sm" className="min-h-[44px]">
                  <Save className="h-4 w-4" />
                </Button>
                <Button onClick={() => setEditingName(false)} variant="ghost" size="sm" className="min-h-[44px]">
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
                <Button onClick={() => setEditingName(true)} variant="ghost" size="sm" className="min-h-[44px]">
                  <Edit className="h-4 w-4" />
                </Button>
              </div>
            )}
            <div className="flex items-center gap-3 mt-1">
              <span className={`text-sm font-medium ${getStatusColor(project.status)}`}>
                {getStatusLabel(project.status)}
              </span>
              <span className="text-sm text-gray-500">•</span>
              <span className="text-sm text-gray-500">{project.total_leads} לידים</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          {selectedLeadIds.size > 0 && (
            <>
              <Button
                variant="primary"
                onClick={handleStartProjectCalls}
                className="flex-1 sm:flex-none min-h-[44px]"
                data-testid="button-call-selected"
              >
                <Phone className="h-5 w-5 ml-2" />
                התקשר לנבחרים ({selectedLeadIds.size})
              </Button>
              <Button
                variant="destructive"
                onClick={handleRemoveLeads}
                className="flex-1 sm:flex-none min-h-[44px]"
                data-testid="button-remove-selected"
              >
                <XCircle className="h-5 w-5 ml-2" />
                הסר ({selectedLeadIds.size})
              </Button>
            </>
          )}
          {selectedLeadIds.size === 0 && project.leads.length > 0 && (
            <Button
              variant="primary"
              onClick={handleStartAllCalls}
              className="flex-1 sm:flex-none min-h-[44px]"
              data-testid="button-call-all"
            >
              <PlayCircle className="h-5 w-5 ml-2" />
              התקשר לכולם
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => setShowAddLeads(true)}
            className="flex-1 sm:flex-none min-h-[44px]"
            data-testid="button-add-leads"
          >
            <UserPlus className="h-5 w-5 ml-2" />
            הוסף לידים
          </Button>
        </div>
      </div>

      {/* Description */}
      {editingDescription ? (
        <Card className="p-4">
          <textarea
            value={editedDescription}
            onChange={(e) => setEditedDescription(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md min-h-[80px]"
            placeholder="תיאור הפרויקט..."
            autoFocus
            data-testid="textarea-edit-description"
          />
          <div className="flex gap-2 mt-2">
            <Button onClick={handleUpdateDescription} size="sm">
              <Save className="h-4 w-4 ml-1" />
              שמור
            </Button>
            <Button onClick={() => setEditingDescription(false)} variant="ghost" size="sm">
              <X className="h-4 w-4 ml-1" />
              ביטול
            </Button>
          </div>
        </Card>
      ) : (
        <Card className="p-4 cursor-pointer hover:bg-gray-50" onClick={() => setEditingDescription(true)}>
          <p className="text-gray-700">
            {project.description || 'לחץ להוספת תיאור...'}
          </p>
        </Card>
      )}

      {/* Statistics - Only if project has started */}
      {hasStarted && project.stats && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">סטטיסטיקות פרויקט</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{project.stats.total_calls}</div>
              <div className="text-sm text-gray-600 mt-1">סה"כ שיחות</div>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-700">{project.stats.answered}</div>
              <div className="text-sm text-green-600 mt-1">נענו</div>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <div className="text-2xl font-bold text-yellow-700">{project.stats.no_answer}</div>
              <div className="text-sm text-yellow-600 mt-1">לא נענו</div>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-700">{project.stats.failed}</div>
              <div className="text-sm text-red-600 mt-1">נכשל</div>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-700">{formatDuration(project.stats.total_duration)}</div>
              <div className="text-sm text-blue-600 mt-1">זמן שיחה</div>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <div className="text-2xl font-bold text-purple-700">{formatDuration(project.stats.avg_duration)}</div>
              <div className="text-sm text-purple-600 mt-1">ממוצע</div>
            </div>
          </div>
        </Card>
      )}

      {/* Leads List */}
      <Card className="p-6">
        <div className="flex flex-col gap-4 mb-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Users className="h-5 w-5" />
              לידים בפרויקט ({selectedLeadIds.size}/{filteredLeads.length})
              {statusFilter.length > 0 && (
                <span className="text-sm text-gray-500 font-normal">
                  (מתוך {project.leads.length} סה"כ)
                </span>
              )}
            </h3>
            {project.leads.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAll}
                className="w-full sm:w-auto min-h-[44px]"
                data-testid="button-select-all"
              >
                {selectedLeadIds.size === filteredLeads.length && filteredLeads.length > 0 ? 'בטל בחירה' : 'בחר הכל'}
              </Button>
            )}
          </div>
          
          {/* Status Filter */}
          {project.leads.length > 0 && (
            <div className="flex items-center gap-3">
              <Filter className="h-5 w-5 text-gray-500 flex-shrink-0" />
              <div className="flex-1">
                <MultiStatusSelect
                  statuses={statuses}
                  selectedStatuses={statusFilter}
                  onChange={setStatusFilter}
                  placeholder="סנן לפי סטטוס..."
                />
              </div>
              {statusFilter.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setStatusFilter([])}
                  className="flex-shrink-0"
                >
                  נקה סינון
                </Button>
              )}
            </div>
          )}
        </div>

        {project.leads.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Users className="h-16 w-16 mx-auto mb-4 text-gray-400" />
            <p className="mb-4">אין לידים בפרויקט</p>
            <Button onClick={() => setShowAddLeads(true)}>
              <UserPlus className="h-5 w-5 ml-2" />
              הוסף לידים
            </Button>
          </div>
        ) : filteredLeads.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Filter className="h-16 w-16 mx-auto mb-4 text-gray-400" />
            <p className="mb-4">אין לידים התואמים לסינון</p>
            <Button onClick={() => setStatusFilter([])} variant="outline">
              נקה סינון
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredLeads.map((lead: ProjectLead) => (
              <div
                key={lead.id}
                className={`flex flex-col sm:flex-row items-start sm:items-center gap-4 p-4 rounded-lg border transition-colors ${
                  selectedLeadIds.has(lead.id) ? 'bg-blue-50 border-blue-300' : 'bg-white border-gray-200 hover:bg-gray-50'
                }`}
                data-testid={`lead-card-${lead.id}`}
              >
                <div
                  className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer"
                  onClick={() => handleLeadClick(lead.id)}
                >
                  <div className="flex-shrink-0">
                    {selectedLeadIds.has(lead.id) ? (
                      <CheckCircle2
                        className="h-5 w-5 text-blue-600 cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleLead(lead.id);
                        }}
                      />
                    ) : (
                      <div
                        className="h-5 w-5 border-2 border-gray-300 rounded cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleLead(lead.id);
                        }}
                      />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">{lead.full_name}</div>
                    <div className="text-sm text-gray-500 truncate" dir="ltr">{lead.phone_e164}</div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto" onClick={(e) => e.stopPropagation()}>
                  <StatusDropdownWithWebhook
                    leadId={lead.id}
                    currentStatus={lead.status}
                    statuses={statuses as any}
                    onStatusChange={async (newStatus) => await handleStatusChange(lead.id, newStatus)}
                    source="project_detail"
                    hasWebhook={hasWebhook}
                    size="sm"
                  />
                  {hasStarted && (
                    <>
                      <div className="text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                        {lead.call_attempts} ניסיונות
                      </div>
                      {lead.last_call_status && (
                        <div className={`text-xs px-2 py-1 rounded ${
                          lead.last_call_status === 'completed' ? 'bg-green-100 text-green-700' :
                          lead.last_call_status === 'no-answer' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {lead.last_call_status}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Add Leads Modal - Placeholder */}
      {showAddLeads && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">הוסף לידים לפרויקט</h3>
              <Button variant="ghost" onClick={() => setShowAddLeads(false)} className="min-h-[44px] min-w-[44px]">
                <X className="h-5 w-5" />
              </Button>
            </div>
            <p className="text-gray-600">
              ממשק הוספת לידים יבוא בקרוב - תוכל לבחור לידים מהמערכת או מרשימות ייבוא
            </p>
            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowAddLeads(false)}>
                סגור
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
