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
  Loader2
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
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-sm text-gray-500">טוען פרויקטים...</p>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-blue-50 mb-6">
          <FolderOpen className="h-10 w-10 text-blue-600" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">אין פרויקטים עדיין</h3>
        <p className="text-gray-600 mb-8 max-w-md mx-auto">
          צור פרויקט חדש כדי לארגן לידים לקבוצות ולעקוב אחר התקדמות השיחות
        </p>
        <Button onClick={onCreateProject} size="lg" data-testid="button-create-first-project">
          <FolderOpen className="h-5 w-5 ml-2" />
          צור פרויקט ראשון
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Create Project Button */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">הפרויקטים שלי</h2>
        <Button onClick={onCreateProject} data-testid="button-create-project">
          <FolderOpen className="h-5 w-5 ml-2" />
          פרויקט חדש
        </Button>
      </div>

      {/* Projects Grid - Cards on mobile and desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((project) => {
          const hasStarted = project.stats !== null && project.stats !== undefined;
          
          return (
            <Card 
              key={project.id} 
              className="p-5 hover:shadow-lg transition-all duration-200 cursor-pointer border-2 hover:border-blue-200"
              data-testid={`project-card-${project.id}`}
            >
              {/* Header: Name + Status */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div 
                  className="flex-1 min-w-0 cursor-pointer"
                  onClick={() => onOpenProject(project.id)}
                >
                  <h3 className="font-semibold text-gray-900 truncate text-base mb-1">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-sm text-gray-500 line-clamp-2 mt-1">
                      {project.description}
                    </p>
                  )}
                </div>
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap flex-shrink-0 ${getStatusColor(project.status)}`}>
                  {getStatusIcon(project.status)}
                  {getStatusLabel(project.status)}
                </span>
              </div>

              {/* Leads Count */}
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-4 pb-4 border-b border-gray-100">
                <Users className="h-4 w-4 text-gray-400 flex-shrink-0" />
                <span className="font-semibold text-gray-900">{project.total_leads}</span>
                <span>לידים בפרויקט</span>
              </div>

              {/* Statistics - Only if project has started */}
              {hasStarted && project.stats ? (
                <div className="space-y-3 mb-4">
                  <div className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    סטטיסטיקות שיחות
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                      <span className="text-gray-600">סה"כ שיחות</span>
                      <span className="font-semibold text-gray-900">{project.stats.total_calls}</span>
                    </div>
                    <div className="flex items-center justify-between p-2.5 bg-green-50 rounded-lg border border-green-100">
                      <span className="text-green-700">נענו</span>
                      <span className="font-semibold text-green-700">{project.stats.answered}</span>
                    </div>
                    <div className="flex items-center justify-between p-2.5 bg-yellow-50 rounded-lg border border-yellow-100">
                      <span className="text-yellow-700">לא נענו</span>
                      <span className="font-semibold text-yellow-700">{project.stats.no_answer}</span>
                    </div>
                    <div className="flex items-center justify-between p-2.5 bg-red-50 rounded-lg border border-red-100">
                      <span className="text-red-700">נכשל</span>
                      <span className="font-semibold text-red-700">{project.stats.failed}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-700 p-2.5 bg-blue-50 rounded-lg border border-blue-100">
                    <Clock className="h-3 w-3 text-blue-600" />
                    <span className="font-medium">זמן שיחה:</span>
                    <span className="font-semibold text-blue-700">{formatDuration(project.stats.total_duration)}</span>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-gray-500 italic mb-4 p-3 bg-gray-50 rounded-lg text-center border border-gray-100">
                  💡 לא התחילו שיחות - סטטיסטיקות יופיעו לאחר תחילת שיחות
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => onOpenProject(project.id)}
                  className="flex-1 min-h-[44px] font-medium"
                  data-testid={`button-open-project-${project.id}`}
                >
                  <FolderOpen className="h-4 w-4 ml-1" />
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
                  className="min-h-[44px] min-w-[44px]"
                  data-testid={`button-delete-project-${project.id}`}
                >
                  {deletingId === project.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Created Date */}
              <div className="text-xs text-gray-400 mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                <span>נוצר {formatDate(project.created_at)}</span>
                {project.status === 'active' && (
                  <span className="inline-flex items-center gap-1 text-green-600">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    פעיל
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
