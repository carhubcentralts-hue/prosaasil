/**
 * AgentLocator v42 - Socket.IO Client
 * תמיכה בהודעות real-time ועדכונים חיים
 */

import { io, Socket } from 'socket.io-client';

interface ServerToClientEvents {
  'task:due': (data: { task_id: number; title: string; due_date: string }) => void;
  'call:incoming': (data: { call_id: string; customer_name: string; phone: string }) => void;
  'whatsapp:message': (data: { message_id: string; customer_name: string; content: string }) => void;
  'notification:general': (data: { title: string; message: string; type: 'info' | 'warning' | 'error' | 'success' }) => void;
  'customer:updated': (data: { customer_id: number; changes: Record<string, any> }) => void;
  'system:status': (data: { status: 'online' | 'offline' | 'maintenance'; message?: string }) => void;
}

interface ClientToServerEvents {
  'user:online': (data: { user_id: number; business_id?: number }) => void;
  'user:offline': (data: { user_id: number }) => void;
  'join_room': (room: string) => void;
  'leave_room': (room: string) => void;
}

class SocketManager {
  private socket: Socket<ServerToClientEvents, ClientToServerEvents> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000; // Start with 1 second
  private isConnecting = false;

  constructor() {
    this.initializeSocket();
  }

  private initializeSocket() {
    if (this.isConnecting || this.socket?.connected) {
      return;
    }

    this.isConnecting = true;

    const serverUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;
    
    this.socket = io(serverUrl, {
      transports: ['websocket', 'polling'],
      upgrade: true,
      rememberUpgrade: true,
      timeout: 5000,
      reconnection: true,
      reconnectionDelay: this.reconnectInterval,
      reconnectionAttempts: this.maxReconnectAttempts,
      forceNew: false
    });

    this.setupEventListeners();
    this.isConnecting = false;
  }

  private setupEventListeners() {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      ;
      this.reconnectAttempts = 0;
      this.reconnectInterval = 1000; // Reset interval
      
      // Join user-specific room if authenticated
      const user = this.getCurrentUser();
      if (user) {
        this.socket?.emit('user:online', { 
          user_id: user.id, 
          business_id: user.business_id 
        });
      }
    });

    this.socket.on('disconnect', (reason) => {
      ;
      
      if (reason === 'io server disconnect') {
        // Server initiated disconnect, reconnect manually
        setTimeout(() => this.reconnect(), 1000);
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ Socket connection error:', error);
      this.handleReconnect();
    });

    // Business events
    this.socket.on('task:due', (data) => {
      ;
      this.showNotification(`משימה דחופה: ${data.title}`, 'warning');
      
      // Show browser notification if permitted
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(`משימה דחופה`, {
          body: data.title,
          icon: '/logo-192.png',
          tag: `task-${data.task_id}`,
          dir: 'rtl',
          lang: 'he'
        });
      }
    });

    this.socket.on('call:incoming', (data) => {
      ;
      this.showNotification(`שיחה נכנסת מ-${data.customer_name}`, 'info');
      
      // Browser notification for incoming calls
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('שיחה נכנסת', {
          body: `${data.customer_name} - ${data.phone}`,
          icon: '/logo-192.png',
          tag: `call-${data.call_id}`,
          requireInteraction: true,
          dir: 'rtl',
          lang: 'he'
        });
      }
    });

    this.socket.on('whatsapp:message', (data) => {
      ;
      this.showNotification(`הודעת WhatsApp מ-${data.customer_name}`, 'info');
    });

    this.socket.on('notification:general', (data) => {
      ;
      this.showNotification(data.message, data.type);
    });

    this.socket.on('customer:updated', (data) => {
      ;
      // Trigger React state updates here if needed
      window.dispatchEvent(new CustomEvent('customer-updated', { 
        detail: data 
      }));
    });

    this.socket.on('system:status', (data) => {
      ;
      if (data.status === 'maintenance') {
        this.showNotification('המערכת נמצאת בתחזוקה', 'warning');
      }
    });
  }

  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      this.reconnectInterval = Math.min(this.reconnectInterval * 2, 10000); // Max 10 seconds
      
       in ${this.reconnectInterval}ms`);
      
      setTimeout(() => {
        this.reconnect();
      }, this.reconnectInterval);
    } else {
      console.error('❌ Maximum reconnection attempts reached');
      this.showNotification('החיבור למערכת נכשל', 'error');
    }
  }

  private reconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.initializeSocket();
  }

  private getCurrentUser() {
    // Get user from localStorage or context
    try {
      const userStr = localStorage.getItem('user');
      return userStr ? JSON.parse(userStr) : null;
    } catch {
      return null;
    }
  }

  private showNotification(message: string, type: 'info' | 'warning' | 'error' | 'success') {
    // Dispatch custom event for React components to handle
    window.dispatchEvent(new CustomEvent('socket-notification', {
      detail: { message, type }
    }));
  }

  // Public methods
  public connect() {
    if (!this.socket || !this.socket.connected) {
      this.initializeSocket();
    }
  }

  public disconnect() {
    if (this.socket) {
      const user = this.getCurrentUser();
      if (user) {
        this.socket.emit('user:offline', { user_id: user.id });
      }
      this.socket.disconnect();
    }
  }

  public joinRoom(room: string) {
    if (this.socket?.connected) {
      this.socket.emit('join_room', room);
      ;
    }
  }

  public leaveRoom(room: string) {
    if (this.socket?.connected) {
      this.socket.emit('leave_room', room);
      ;
    }
  }

  public isConnected(): boolean {
    return this.socket?.connected ?? false;
  }

  public getSocket(): Socket<ServerToClientEvents, ClientToServerEvents> | null {
    return this.socket;
  }

  // Cleanup
  public destroy() {
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
  }
}

// Singleton instance
export const socketManager = new SocketManager();

// React hook for easy integration
export function useSocket() {
  return {
    socket: socketManager.getSocket(),
    isConnected: socketManager.isConnected(),
    connect: () => socketManager.connect(),
    disconnect: () => socketManager.disconnect(),
    joinRoom: (room: string) => socketManager.joinRoom(room),
    leaveRoom: (room: string) => socketManager.leaveRoom(room)
  };
}

// Initialize socket on module load
socketManager.connect();

export default socketManager;