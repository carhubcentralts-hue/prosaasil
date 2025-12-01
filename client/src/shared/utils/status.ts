import { LeadStatus } from '../../features/statuses/hooks';

export interface StatusInfo {
  id: number;
  name: string;
  label: string;
  color: string;
}

const fallbackColors: Record<string, string> = {
  'new': 'bg-blue-100 text-blue-800',
  'attempting': 'bg-yellow-100 text-yellow-800',
  'contacted': 'bg-purple-100 text-purple-800',
  'qualified': 'bg-green-100 text-green-800',
  'won': 'bg-emerald-100 text-emerald-800',
  'lost': 'bg-red-100 text-red-800',
  'unqualified': 'bg-gray-100 text-gray-800',
};

const fallbackLabels: Record<string, string> = {
  'new': 'חדש',
  'attempting': 'מנסה ליצור קשר',
  'contacted': 'יצרנו קשר',
  'qualified': 'מתאים',
  'won': 'נצחנו',
  'lost': 'איבדנו',
  'unqualified': 'לא מתאים',
};

const dotColorMap: Record<string, string> = {
  'bg-blue-100': '#3B82F6',
  'bg-yellow-100': '#F59E0B',
  'bg-purple-100': '#8B5CF6',
  'bg-green-100': '#22C55E',
  'bg-emerald-100': '#10B981',
  'bg-red-100': '#EF4444',
  'bg-gray-100': '#6B7280',
  'bg-orange-100': '#F97316',
  'bg-pink-100': '#EC4899',
  'bg-indigo-100': '#6366F1',
  'bg-teal-100': '#14B8A6',
  'bg-cyan-100': '#06B6D4',
};

export function getStatusColor(status: string, statuses: StatusInfo[]): string {
  const normalizedStatus = status.toLowerCase();
  const foundStatus = statuses.find(s => s.name.toLowerCase() === normalizedStatus);
  if (foundStatus) {
    return foundStatus.color;
  }
  return fallbackColors[normalizedStatus] || 'bg-gray-100 text-gray-800';
}

export function getStatusLabel(status: string, statuses: StatusInfo[]): string {
  const normalizedStatus = status.toLowerCase();
  const foundStatus = statuses.find(s => s.name.toLowerCase() === normalizedStatus);
  if (foundStatus) {
    return foundStatus.label;
  }
  return fallbackLabels[normalizedStatus] || status;
}

export function getStatusDotColor(tailwindClass: string): string {
  for (const [key, color] of Object.entries(dotColorMap)) {
    if (tailwindClass.includes(key)) {
      return color;
    }
  }
  return '#6B7280';
}

export function parseStatusColorToHex(color: string): string {
  if (color.startsWith('#')) {
    return color;
  }
  for (const [key, hex] of Object.entries(dotColorMap)) {
    if (color.includes(key)) {
      return hex;
    }
  }
  return '#6B7280';
}
