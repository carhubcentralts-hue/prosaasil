/**
 * AgentLocator v39 - Real-time Socket Connection
 * חיבור Socket עבור התראות זמן־אמת
 */

import { io, Socket } from "socket.io-client";

// Initialize socket connection
export const socket: Socket = io("/", { 
    path: "/ws",
    transports: ['websocket'],
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

// Connection event handlers
socket.on('connect', () => {
    console.log('🔌 Connected to server via WebSocket');
});

socket.on('disconnect', () => {
    console.log('🔌 Disconnected from server');
});

socket.on('reconnect', () => {
    console.log('🔌 Reconnected to server');
});

socket.on('connect_error', (error) => {
    console.error('🚫 WebSocket connection error:', error);
});

// Task event types
export interface TaskDueEvent {
    task_id: number;
    customer_id: number;
    customer_name: string;
    customer_phone: string;
    task_title: string;
    due_at: string;
    priority: 'low' | 'medium' | 'high' | 'urgent';
    channel: 'call' | 'whatsapp' | 'meeting' | 'email' | 'sms';
}

// Notification event types
export interface NotificationEvent {
    id: number;
    type: string;
    title: string;
    message: string;
    data: any;
    created_at: string;
}

// Socket event listeners with proper TypeScript types
export const socketEvents = {
    // Task due notifications
    onTaskDue: (callback: (data: TaskDueEvent) => void) => {
        socket.on('task:due', callback);
        return () => socket.off('task:due', callback);
    },
    
    // General notifications
    onNotification: (callback: (data: NotificationEvent) => void) => {
        socket.on('notification', callback);
        return () => socket.off('notification', callback);
    },
    
    // WhatsApp message notifications
    onWhatsAppMessage: (callback: (data: any) => void) => {
        socket.on('whatsapp:message', callback);
        return () => socket.off('whatsapp:message', callback);
    },
    
    // Call notifications
    onCallUpdate: (callback: (data: any) => void) => {
        socket.on('call:update', callback);
        return () => socket.off('call:update', callback);
    },
    
    // Customer timeline updates
    onTimelineUpdate: (callback: (data: { customer_id: number, event_type: string }) => void) => {
        socket.on('timeline:update', callback);
        return () => socket.off('timeline:update', callback);
    }
};

// Helper functions for socket operations
export const socketUtils = {
    // Join customer room for real-time updates
    joinCustomerRoom: (customerId: number) => {
        socket.emit('join_customer_room', { customer_id: customerId });
    },
    
    // Leave customer room
    leaveCustomerRoom: (customerId: number) => {
        socket.emit('leave_customer_room', { customer_id: customerId });
    },
    
    // Subscribe to notifications for current user
    subscribeToNotifications: () => {
        socket.emit('subscribe_notifications');
    },
    
    // Unsubscribe from notifications
    unsubscribeFromNotifications: () => {
        socket.emit('unsubscribe_notifications');
    },
    
    // Send read receipt for notification
    markNotificationRead: (notificationId: number) => {
        socket.emit('notification:read', { notification_id: notificationId });
    },
    
    // Request task snooze
    snoozeTask: (taskId: number, minutes: number) => {
        socket.emit('task:snooze', { task_id: taskId, minutes });
    },
    
    // Mark task as completed via socket
    completeTask: (taskId: number) => {
        socket.emit('task:complete', { task_id: taskId });
    }
};

export default socket;