import { Card, CardContent, CardHeader } from './Card';
import { ActivityItemSkeleton } from './Skeleton';
import { formatDate } from '../utils/format';
import { ActivityItem } from '../../types/api';
import { MessageCircle, Phone } from 'lucide-react';

interface ActivityFeedProps {
  activities: ActivityItem[] | null;
  isLoading: boolean;
  title?: string;
}

export function ActivityFeed({ 
  activities, 
  isLoading, 
  title = 'פעילות אחרונה' 
}: ActivityFeedProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        </CardHeader>
        <CardContent className="p-0">
          {[...Array(5)].map((_, index) => (
            <ActivityItemSkeleton key={index} />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!activities || activities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-gray-500">אין פעילות אחרונה</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-gray-100">
          {activities.map((activity, index) => (
            <div key={index} className="flex items-center space-x-3 p-4 hover:bg-gray-50">
              <div className="flex-shrink-0">
                {activity.type === 'whatsapp' ? (
                  <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                    <MessageCircle className="h-4 w-4 text-green-600" />
                  </div>
                ) : (
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <Phone className="h-4 w-4 text-blue-600" />
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-gray-900">
                    {activity.type === 'whatsapp' ? 'הודעת WhatsApp' : 'שיחה'}
                  </p>
                  <p className="text-xs text-gray-500" dir="ltr">
                    {formatDate(activity.ts)}
                  </p>
                </div>
                <p className="text-sm text-gray-600 truncate mt-1">
                  {activity.tenant}
                </p>
                <p className="text-sm text-gray-500 truncate">
                  {activity.preview}
                </p>
                {activity.provider && (
                  <p className="text-xs text-gray-400 mt-1">
                    {activity.provider}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}