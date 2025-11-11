import { Badge } from './Badge';
import { Card, CardContent } from './Card';
import { Skeleton } from './Skeleton';
import { StatusResponse } from '../../types/api';

interface ProviderStatusProps {
  status: StatusResponse | null;
  isLoading: boolean;
}

export function ProviderStatus({ status, isLoading }: ProviderStatusProps) {
  if (isLoading) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-5 w-24" />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardContent>
          <h3 className="text-lg font-medium text-gray-900 mb-4">סטטוס ספקים</h3>
          <div className="text-center py-4">
            <p className="text-gray-500">שגיאה בטעינת סטטוס ספקים</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const providers = [
    { 
      name: 'Twilio', 
      status: status.twilio.up, 
      latency: null 
    },
    { 
      name: 'Baileys', 
      status: status.baileys.up, 
      latency: null 
    },
    { 
      name: 'Database', 
      status: status.db.up, 
      latency: null 
    },
  ];

  return (
    <Card>
      <CardContent>
        <h3 className="text-lg font-medium text-gray-900 mb-4">סטטוס ספקים</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {providers.map((provider) => (
            <div key={provider.name} className="text-center p-4 border rounded-lg">
              <p className="text-sm font-medium text-gray-700 mb-2">{provider.name}</p>
              <Badge
                variant={provider.status ? 'success' : 'error'}
                size="md"
                className="mb-2"
              >
                {provider.status ? 'פעיל' : 'לא פעיל'}
              </Badge>
            </div>
          ))}
        </div>
        
        {/* Latency information */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">זמני תגובה</h4>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="text-center">
              <p className="text-gray-500">STT</p>
              <p className="font-medium" dir="ltr">{status.latency.stt}ms</p>
            </div>
            <div className="text-center">
              <p className="text-gray-500">AI</p>
              <p className="font-medium" dir="ltr">{status.latency.ai}ms</p>
            </div>
            <div className="text-center">
              <p className="text-gray-500">TTS</p>
              <p className="font-medium" dir="ltr">{status.latency.tts}ms</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}