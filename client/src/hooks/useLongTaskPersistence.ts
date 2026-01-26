import { useEffect, useState } from 'react';

interface TaskState {
  taskId: number;
  taskType: string;
  status: string;
  timestamp: number;
}

export function useLongTaskPersistence(businessId: number, taskType: string) {
  const storageKey = `longTask_${businessId}_${taskType}`;
  
  const [activeTask, setActiveTask] = useState<TaskState | null>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Only restore if less than 1 hour old
        if (Date.now() - parsed.timestamp < 3600000) {
          return parsed;
        }
      }
    } catch (e) {
      console.error('Failed to parse stored task state from localStorage:', e);
    }
    return null;
  });
  
  const saveTask = (task: Omit<TaskState, 'timestamp'>) => {
    const state: TaskState = {
      ...task,
      timestamp: Date.now()
    };
    setActiveTask(state);
    localStorage.setItem(storageKey, JSON.stringify(state));
  };
  
  const clearTask = () => {
    setActiveTask(null);
    localStorage.removeItem(storageKey);
  };
  
  // Auto-clear completed tasks after 5 minutes
  useEffect(() => {
    if (activeTask && ['completed', 'failed', 'cancelled'].includes(activeTask.status)) {
      const timer = setTimeout(clearTask, 300000); // 5 minutes
      return () => clearTimeout(timer);
    }
  }, [activeTask]);
  
  return { activeTask, saveTask, clearTask };
}
