import { useEffect, useState } from 'react';

interface TaskState {
  taskId: number;
  taskType: string;
  // ✅ CRITICAL FIX: Removed status and progress fields from localStorage
  // Progress bars must ALWAYS fetch state from server, never from cache
  // This prevents stuck progress bars when runs are stale/completed
  timestamp: number;
}

export function useLongTaskPersistence(businessId: number, taskType: string) {
  const storageKey = `longTask_${businessId}_${taskType}`;
  
  // ✅ FIX: Only restore taskId reference, not status/progress
  // Status must always come from server to prevent stale state
  const [activeTask, setActiveTask] = useState<TaskState | null>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Only restore if less than 1 hour old
        if (Date.now() - parsed.timestamp < 3600000) {
          // Return only the taskId reference, server will provide status
          return {
            taskId: parsed.taskId,
            taskType: parsed.taskType,
            timestamp: parsed.timestamp
          };
        }
      }
    } catch (e) {
      console.error('Failed to parse stored task state from localStorage:', e);
    }
    return null;
  });
  
  // ✅ FIX: Only save taskId reference, not progress/status
  const saveTask = (task: Omit<TaskState, 'timestamp'>) => {
    const state: TaskState = {
      taskId: task.taskId,
      taskType: task.taskType,
      timestamp: Date.now()
    };
    setActiveTask(state);
    localStorage.setItem(storageKey, JSON.stringify(state));
  };
  
  const clearTask = () => {
    setActiveTask(null);
    localStorage.removeItem(storageKey);
  };
  
  // ✅ FIX: Auto-clear task reference after 1 hour (not status-dependent)
  // Status is always fetched from server, so we just clear the reference
  useEffect(() => {
    if (activeTask) {
      const age = Date.now() - activeTask.timestamp;
      if (age > 3600000) { // 1 hour
        clearTask();
      }
    }
  }, [activeTask]);
  
  return { activeTask, saveTask, clearTask };
}
