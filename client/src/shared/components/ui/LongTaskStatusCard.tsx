import React, { useEffect, useState } from 'react';
import { Clock, CheckCircle2, XCircle, Loader2, AlertTriangle, X } from 'lucide-react';
import { Card } from './Card';
import { Button } from './Button';

interface LongTaskStatusCardProps {
  taskId: number;
  taskType: 'broadcast' | 'receipt_delete' | 'receipt_sync';
  status: string;
  total?: number;
  processed?: number;
  success?: number;
  failed?: number;
  cancelled?: number;
  progressPct?: number;
  canCancel: boolean;
  cancelRequested?: boolean;
  onCancel: () => void;
  onDismiss?: () => void;
  onRefresh?: () => void;  // Callback for refreshing status
  autoRefresh?: boolean;  // Auto-poll every 2-3 seconds
  refreshInterval?: number; // Milliseconds (default 2500)
}

export function LongTaskStatusCard({
  taskId,
  taskType,
  status,
  total = 0,
  processed = 0,
  success = 0,
  failed = 0,
  cancelled = 0,
  progressPct,
  canCancel,
  cancelRequested = false,
  onCancel,
  onDismiss,
  onRefresh,
  autoRefresh = false,
  refreshInterval = 2500
}: LongTaskStatusCardProps) {
  const [polling, setPolling] = useState(autoRefresh);
  
  // Auto-refresh polling
  useEffect(() => {
    if (!polling || ['completed', 'failed', 'cancelled'].includes(status) || !onRefresh) {
      return;
    }
    
    const interval = setInterval(() => {
      onRefresh();
    }, refreshInterval);
    
    return () => clearInterval(interval);
  }, [polling, status, onRefresh, refreshInterval]);
  
  // Stop polling on final status
  useEffect(() => {
    if (['completed', 'failed', 'cancelled'].includes(status)) {
      setPolling(false);
    }
  }, [status]);
  
  const getStatusDisplay = () => {
    if (cancelRequested) {
      return {
        progressBarClass: 'bg-orange-600',
        icon: <AlertTriangle className="w-5 h-5" />,
        text: 'מבטל...',
        bgClass: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
      };
    }
    
    switch (status) {
      case 'running':
        return {
          progressBarClass: 'bg-blue-600',
          icon: <Loader2 className="w-5 h-5 animate-spin" />,
          text: 'מבצע',
          bgClass: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
        };
      case 'completed':
        return {
          progressBarClass: 'bg-green-600',
          icon: <CheckCircle2 className="w-5 h-5" />,
          text: 'הושלם',
          bgClass: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
        };
      case 'cancelled':
        return {
          progressBarClass: 'bg-orange-600',
          icon: <XCircle className="w-5 h-5" />,
          text: 'בוטל',
          bgClass: 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
        };
      case 'failed':
        return {
          progressBarClass: 'bg-red-600',
          icon: <AlertTriangle className="w-5 h-5" />,
          text: 'נכשל',
          bgClass: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        };
      default:
        return {
          progressBarClass: 'bg-gray-600',
          icon: <Clock className="w-5 h-5" />,
          text: 'ממתין',
          bgClass: 'bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-800'
        };
    }
  };
  
  const statusDisplay = getStatusDisplay();
  const calculatedProgressPct = progressPct !== undefined ? progressPct : 
    (total > 0 ? (processed / total) * 100 : 0);
  
  return (
    <Card className={`p-4 ${statusDisplay.bgClass} border-2`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {statusDisplay.icon}
          <span className="font-semibold text-lg">{statusDisplay.text}</span>
        </div>
        {onDismiss && (
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
      
      {/* Progress bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mb-3">
        <div 
          className={`${statusDisplay.progressBarClass} h-2.5 rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(100, calculatedProgressPct)}%` }}
        />
      </div>
      
      {/* Counters */}
      <div className="grid grid-cols-4 gap-2 text-sm mb-3">
        <div className="text-center">
          <div className="font-semibold">{processed}</div>
          <div className="text-gray-600 dark:text-gray-400">מעובדים</div>
        </div>
        {success > 0 && (
          <div className="text-center">
            <div className="font-semibold text-green-600">{success}</div>
            <div className="text-gray-600 dark:text-gray-400">הצליחו</div>
          </div>
        )}
        {failed > 0 && (
          <div className="text-center">
            <div className="font-semibold text-red-600">{failed}</div>
            <div className="text-gray-600 dark:text-gray-400">נכשלו</div>
          </div>
        )}
        {cancelled > 0 && (
          <div className="text-center">
            <div className="font-semibold text-orange-600">{cancelled}</div>
            <div className="text-gray-600 dark:text-gray-400">בוטלו</div>
          </div>
        )}
        <div className="text-center">
          <div className="font-semibold">{total}</div>
          <div className="text-gray-600 dark:text-gray-400">סה"כ</div>
        </div>
      </div>
      
      {/* Actions */}
      {canCancel && !cancelRequested && status === 'running' && (
        <Button variant="outline" size="sm" onClick={onCancel} className="w-full">
          ביטול משימה
        </Button>
      )}
    </Card>
  );
}
