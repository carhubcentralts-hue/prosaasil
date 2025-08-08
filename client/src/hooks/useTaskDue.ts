/**
 * AgentLocator v39 - Task Due Hook
 * Hook עבור התראות משימות במועד
 */

import { useEffect, useCallback } from 'react';
import { socketEvents, type TaskDueEvent } from '@/lib/socket';

interface UseTaskDueOptions {
    enabled?: boolean;
    onTaskDue?: (task: TaskDueEvent) => void;
    onError?: (error: Error) => void;
}

export function useTaskDue(options: UseTaskDueOptions = {}) {
    const { enabled = true, onTaskDue, onError } = options;
    
    const handleTaskDue = useCallback((taskData: TaskDueEvent) => {
        try {
            ;
            
            // Validate task data
            if (!taskData.task_id || !taskData.customer_id) {
                throw new Error('Invalid task due data received');
            }
            
            // Call the provided callback
            onTaskDue?.(taskData);
            
            // Log for debugging
            ;
            
        } catch (error) {
            console.error('Error handling task due event:', error);
            onError?.(error as Error);
        }
    }, [onTaskDue, onError]);
    
    useEffect(() => {
        if (!enabled) return;
        
        // Subscribe to task due events
        const unsubscribe = socketEvents.onTaskDue(handleTaskDue);
        
        ;
        
        // Cleanup on unmount
        return () => {
            ;
            unsubscribe();
        };
    }, [enabled, handleTaskDue]);
    
    return {
        // Could add additional functionality here if needed
        isEnabled: enabled
    };
}

// Hook for general notifications
export function useNotifications() {
    const handleNotification = useCallback((notificationData: any) => {
        ;
        
        // Could trigger toast notifications here
        // toast.info(notificationData.message);
    }, []);
    
    useEffect(() => {
        const unsubscribe = socketEvents.onNotification(handleNotification);
        return unsubscribe;
    }, [handleNotification]);
}

// Hook for WhatsApp message notifications
export function useWhatsAppNotifications() {
    const handleWhatsAppMessage = useCallback((messageData: any) => {
        ;
        
        // Could update UI state or show notification
        // updateWhatsAppConversation(messageData);
    }, []);
    
    useEffect(() => {
        const unsubscribe = socketEvents.onWhatsAppMessage(handleWhatsAppMessage);
        return unsubscribe;
    }, [handleWhatsAppMessage]);
}

// Hook for call updates
export function useCallNotifications() {
    const handleCallUpdate = useCallback((callData: any) => {
        ;
        
        // Could update call status in UI
        // updateCallStatus(callData);
    }, []);
    
    useEffect(() => {
        const unsubscribe = socketEvents.onCallUpdate(handleCallUpdate);
        return unsubscribe;
    }, [handleCallUpdate]);
}