import React from 'react';
import { Clock, CheckCircle2, XCircle, Loader2, AlertTriangle, X } from 'lucide-react';
import { Card } from '../../../shared/components/ui/Card';
import { Button } from '../../../shared/components/ui/Button';

interface QueueStatusCardProps {
  jobId: number;
  status: string;
  total: number;
  processed: number;
  success: number;
  failed: number;
  inProgress: number;
  queued: number;
  progressPct: number;
  canCancel: boolean;
  cancelRequested: boolean;
  onCancel: () => void;
  onDismiss?: () => void;
}

export function QueueStatusCard({
  jobId,
  status,
  total,
  processed,
  success,
  failed,
  inProgress,
  queued,
  progressPct,
  canCancel,
  cancelRequested,
  onCancel,
  onDismiss
}: QueueStatusCardProps) {
  // Determine status color and icon
  const getStatusDisplay = () => {
    if (cancelRequested) {
      return {
        color: 'orange',
        icon: <AlertTriangle className="w-5 h-5" />,
        text: 'מבטל...',
        bgClass: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
      };
    }
    
    switch (status) {
      case 'running':
        return {
          color: 'blue',
          icon: <Loader2 className="w-5 h-5 animate-spin" />,
          text: 'מבצע שיחות',
          bgClass: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
        };
      case 'completed':
        return {
          color: 'green',
          icon: <CheckCircle2 className="w-5 h-5" />,
          text: 'הושלם',
          bgClass: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
        };
      case 'cancelled':
        return {
          color: 'orange',
          icon: <XCircle className="w-5 h-5" />,
          text: 'בוטל',
          bgClass: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
        };
      case 'failed':
        return {
          color: 'red',
          icon: <AlertTriangle className="w-5 h-5" />,
          text: 'נכשל',
          bgClass: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        };
      default:
        return {
          color: 'gray',
          icon: <Clock className="w-5 h-5" />,
          text: 'בתור',
          bgClass: 'bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-800'
        };
    }
  };

  const statusDisplay = getStatusDisplay();
  const isActive = status === 'running' && !cancelRequested;
  const canDismiss = status in ['completed', 'cancelled', 'failed'] && onDismiss;

  return (
    <Card className={`p-6 border-2 ${statusDisplay.bgClass} transition-all duration-300`}>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`text-${statusDisplay.color}-600 dark:text-${statusDisplay.color}-400`}>
              {statusDisplay.icon}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                תור שיחות יוצאות
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {statusDisplay.text}
              </p>
            </div>
          </div>
          
          {/* Cancel button */}
          {isActive && canCancel && (
            <Button
              onClick={onCancel}
              variant="destructive"
              size="sm"
              disabled={cancelRequested}
            >
              {cancelRequested ? 'מבטל...' : 'בטל תור'}
            </Button>
          )}
          
          {/* Dismiss button for completed queues */}
          {canDismiss && (
            <Button
              onClick={onDismiss}
              variant="ghost"
              size="sm"
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-700 dark:text-gray-300 font-medium">
              התקדמות: {processed} מתוך {total}
            </span>
            <span className="text-gray-600 dark:text-gray-400">
              {progressPct.toFixed(1)}%
            </span>
          </div>
          
          {/* Progress bar */}
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ease-out ${
                cancelRequested 
                  ? 'bg-orange-500' 
                  : status === 'completed' 
                    ? 'bg-green-500' 
                    : 'bg-blue-500'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-3">
          {/* In Progress */}
          {isActive && inProgress > 0 && (
            <div className="bg-blue-100 dark:bg-blue-900/30 rounded-lg p-3 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
              <div className="text-xl font-bold text-blue-700 dark:text-blue-300">
                {inProgress}
              </div>
              <div className="text-xs text-blue-600 dark:text-blue-400">
                מבצע עכשיו
              </div>
            </div>
          )}
          
          {/* Queued */}
          {isActive && queued > 0 && (
            <div className="bg-gray-100 dark:bg-gray-800/50 rounded-lg p-3 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Clock className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              </div>
              <div className="text-xl font-bold text-gray-700 dark:text-gray-300">
                {queued}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                בתור
              </div>
            </div>
          )}
          
          {/* Success */}
          <div className="bg-green-100 dark:bg-green-900/30 rounded-lg p-3 text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
            </div>
            <div className="text-xl font-bold text-green-700 dark:text-green-300">
              {success}
            </div>
            <div className="text-xs text-green-600 dark:text-green-400">
              הצליחו
            </div>
          </div>
          
          {/* Failed */}
          {failed > 0 && (
            <div className="bg-red-100 dark:bg-red-900/30 rounded-lg p-3 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
              </div>
              <div className="text-xl font-bold text-red-700 dark:text-red-300">
                {failed}
              </div>
              <div className="text-xs text-red-600 dark:text-red-400">
                נכשלו
              </div>
            </div>
          )}
        </div>

        {/* Real-time status text */}
        {isActive && (
          <div className="text-center text-sm text-gray-600 dark:text-gray-400">
            {inProgress > 0 ? (
              <span>מבצע {inProgress} שיחות במקביל</span>
            ) : (
              <span>ממתין לסלוט פנוי...</span>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
