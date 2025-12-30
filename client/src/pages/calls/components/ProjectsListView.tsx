import React, { useState } from 'react';
import { 
  Folder, 
  FolderOpen,
  Users, 
  Phone,
  PlayCircle,
  Edit,
  Trash2,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  XCircle
} from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Card } from '../../../shared/components/ui/Card';
import { formatDate } from '../../../shared/utils/format';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: 'draft' | 'active' | 'completed' | 'paused';
  created_at: string;
  total_leads: number;
  stats?: {
    total_calls: number;
    answered: number;
    no_answer: number;
    failed: number;
    total_duration: number;
  } | null;
}

interface ProjectsListViewProps {
  projects: Project[];
  loading: boolean;
  onCreateProject: () => void;
  onOpenProject: (projectId: number) => void;
  onDeleteProject: (projectId: number) => void;
}

export function ProjectsListView({
  projects,
  loading,
  onCreateProject,
  onOpenProject,
  onDeleteProject
}: ProjectsListViewProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'completed': return 'bg-blue-100 text-blue-800';
      case 'paused': return 'bg-yellow-100 text-yellow-800';
      case 'draft':
      default: return 'bg-gray-100 text-gray-800';
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <PlayCircle className="h-4 w-4" />;
      case 'completed': return <CheckCircle className="h-4 w-4" />;
      case 'paused': return <AlertCircle className="h-4 w-4" />;
      case 'draft':
      default: return <Folder className="h-4 w-4" />;
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
      <div className="flex flex-col items-center justify-center py-20">
        <div className="relative">
          <Loader2 className="h-16 w-16 animate-spin text-blue-600 mb-4" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Folder className="h-8 w-8 text-blue-400 opacity-50" />
          </div>
        </div>
        <p className="text-base text-gray-600 font-medium mt-2">טוען פרויקטים...</p>
        <p className="text-sm text-gray-400 mt-1">אנא המתן</p>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-blue-50 to-blue-100 mb-6 shadow-sm">
          <FolderOpen className="h-12 w-12 text-blue-600" />
        </div>
        <h3 className="text-xl font-bold text-gray-900 mb-3">אין פרויקטים עדיין</h3>
        <p className="text-gray-600 mb-10 max-w-md mx-auto leading-relaxed">
          צור פרויקט חדש כדי לארגן לידים לקבוצות ולעקוב אחר התקדמות השיחות בצורה מסודרת ויעילה
        </p>
        <Button 
          onClick={onCreateProject} 
          size="lg" 
          data-testid="button-create-first-project"
          className="shadow-lg hover:shadow-xl transition-all duration-200 px-8 py-3"
        >
          <FolderOpen className="h-6 w-6 ml-2" />
          צור פרויקט ראשון
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Create Project Button */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">הפרויקטים שלי</h2>
          <p className="text-sm text-gray-500 mt-1">נהל וארגן את הלידים שלך בפרויקטים</p>
        </div>
        <Button 
          onClick={onCreateProject} 
          data-testid="button-create-project"
          className="shadow-md hover:shadow-lg transition-all duration-200"
        >
          <FolderOpen className="h-5 w-5 ml-2" />
          פרויקט חדש
        </Button>
      </div>

      {/* Projects Grid - Beautiful Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {projects.map((project) => {
          const hasStarted = project.stats !== null && project.stats !== undefined;
          const successRate = hasStarted && project.stats && project.stats.total_calls > 0
            ? Math.round((project.stats.answered / project.stats.total_calls) * 100)
            : 0;
          
          return (
            <Card 
              key={project.id} 
              className="p-6 hover:shadow-2xl transition-all duration-300 cursor-pointer border-2 hover:border-blue-300 bg-gradient-to-br from-white to-gray-50 group"
              data-testid={`project-card-${project.id}`}
            >
              {/* Header: Name + Status Badge */}
              <div className="flex items-start justify-between gap-3 mb-5">
                <div 
                  className="flex-1 min-w-0 cursor-pointer group-hover:scale-[1.02] transition-transform duration-200"
                  onClick={() => onOpenProject(project.id)}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Folder className="h-5 w-5 text-blue-600 flex-shrink-0" />
                    <h3 className="font-bold text-gray-900 truncate text-lg">
                      {project.name}
                    </h3>
                  </div>
                  {project.description && (
                    <p className="text-sm text-gray-600 line-clamp-2 mt-1 leading-relaxed">
                      {project.description}
                    </p>
                  )}
                </div>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap flex-shrink-0 shadow-sm ${getStatusColor(project.status)}`}>
                  {getStatusIcon(project.status)}
                  {getStatusLabel(project.status)}
                </span>
              </div>

              {/* Leads Count - Prominent Display */}
              <div className="flex items-center gap-3 text-sm mb-5 pb-5 border-b-2 border-gray-200">
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-blue-50 border-2 border-blue-100">
                  <Users className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <div className="font-bold text-2xl text-gray-900">{project.total_leads}</div>
                  <div className="text-xs text-gray-500 font-medium">לידים בפרויקט</div>
                </div>
              </div>

              {/* Statistics - Enhanced Display */}
              {hasStarted && project.stats && project.stats.total_calls > 0 ? (
                <div className="space-y-3 mb-5">
                  {/* Success Rate Bar */}
                  <div className="mb-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs font-semibold text-gray-700">אחוז הצלחה</span>
                      <span className="text-lg font-bold text-green-600">{successRate}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                      <div 
                        className="bg-gradient-to-r from-green-500 to-green-600 h-3 rounded-full transition-all duration-500 shadow-sm"
                        style={{ width: `${successRate}%` }}
                      />
                    </div>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="flex flex-col p-3 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border border-gray-200 shadow-sm">
                      <div className="flex items-center gap-1.5 mb-1">
                        <Phone className="h-3.5 w-3.5 text-gray-600" />
                        <span className="text-gray-600 font-medium">סה"כ שיחות</span>
                      </div>
                      <span className="font-bold text-xl text-gray-900">{project.stats.total_calls}</span>
                    </div>
                    <div className="flex flex-col p-3 bg-gradient-to-br from-green-50 to-green-100 rounded-xl border border-green-200 shadow-sm">
                      <div className="flex items-center gap-1.5 mb-1">
                        <CheckCircle className="h-3.5 w-3.5 text-green-700" />
                        <span className="text-green-700 font-medium">נענו</span>
                      </div>
                      <span className="font-bold text-xl text-green-700">{project.stats.answered}</span>
                    </div>
                    <div className="flex flex-col p-3 bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-xl border border-yellow-200 shadow-sm">
                      <div className="flex items-center gap-1.5 mb-1">
                        <AlertCircle className="h-3.5 w-3.5 text-yellow-700" />
                        <span className="text-yellow-700 font-medium">לא נענו</span>
                      </div>
                      <span className="font-bold text-xl text-yellow-700">{project.stats.no_answer}</span>
                    </div>
                    <div className="flex flex-col p-3 bg-gradient-to-br from-red-50 to-red-100 rounded-xl border border-red-200 shadow-sm">
                      <div className="flex items-center gap-1.5 mb-1">
                        <XCircle className="h-3.5 w-3.5 text-red-700" />
                        <span className="text-red-700 font-medium">נכשל</span>
                      </div>
                      <span className="font-bold text-xl text-red-700">{project.stats.failed}</span>
                    </div>
                  </div>

                  {/* Call Duration */}
                  <div className="flex items-center gap-2 text-sm p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 shadow-sm">
                    <Clock className="h-4 w-4 text-blue-600 flex-shrink-0" />
                    <span className="font-medium text-gray-700">זמן שיחה כולל:</span>
                    <span className="font-bold text-blue-700 mr-auto">{formatDuration(project.stats.total_duration)}</span>
                  </div>
                </div>
              ) : hasStarted ? (
                <div className="text-xs text-gray-500 italic mb-5 p-4 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl text-center border border-gray-200 shadow-sm">
                  <Clock className="h-5 w-5 text-gray-400 mx-auto mb-2" />
                  <div className="font-medium">הפרויקט התחיל אך אין שיחות עדיין</div>
                </div>
              ) : (
                <div className="text-xs text-gray-500 italic mb-5 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl text-center border border-blue-200 shadow-sm">
                  <PlayCircle className="h-5 w-5 text-blue-600 mx-auto mb-2" />
                  <div className="font-medium text-blue-700">טרם החלו שיחות</div>
                  <div className="text-xs text-gray-600 mt-1">סטטיסטיקות יופיעו לאחר תחילת שיחות</div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 mb-4">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => onOpenProject(project.id)}
                  className="flex-1 min-h-[48px] font-semibold shadow-md hover:shadow-lg transition-all duration-200 group-hover:scale-[1.02]"
                  data-testid={`button-open-project-${project.id}`}
                >
                  <FolderOpen className="h-4 w-4 ml-2" />
                  פתח פרויקט
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingId(project.id);
                    onDeleteProject(project.id);
                  }}
                  disabled={deletingId === project.id}
                  className="min-h-[48px] min-w-[48px] shadow-md hover:shadow-lg transition-all duration-200"
                  data-testid={`button-delete-project-${project.id}`}
                >
                  {deletingId === project.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Footer: Created Date + Status Indicator */}
              <div className="text-xs text-gray-500 pt-4 border-t border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3 w-3" />
                  <span>נוצר {formatDate(project.created_at)}</span>
                </div>
                {project.status === 'active' && (
                  <span className="inline-flex items-center gap-1.5 text-green-600 font-medium">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-lg shadow-green-500/50"></span>
                    פעיל כעת
                  </span>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
