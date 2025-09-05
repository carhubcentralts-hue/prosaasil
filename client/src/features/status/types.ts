export interface SystemStatus {
  twilio: boolean;
  baileys: boolean;
  db: boolean;
  latency: {
    stt: number;
    ai: number;
    tts: number;
  };
}

export interface KPIData {
  calls: {
    today: number;
    last7d: number;
    avgHandleSec: number;
  };
  whatsapp: {
    today: number;
    last7d: number;
    unread: number;
  };
  revenue: {
    thisMonth: number;
    ytd: number;
  };
}

export interface RecentActivity {
  ts: string;
  type: 'whatsapp' | 'call';
  tenant: string;
  preview: string;
  provider?: string;
}