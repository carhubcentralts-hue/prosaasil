import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Activity } from "../../../shared/schema";
import { 
  MessageCircle, 
  Phone, 
  UserPlus, 
  Download, 
  Users,
  Bot
} from "lucide-react";

export default function ActivityPanel() {
  const { data: activities = [], isLoading } = useQuery<Activity[]>({
    queryKey: ["/api/activities"],
  });

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "customer_added":
        return <UserPlus className="h-4 w-4 text-blue-500" />;
      case "whatsapp_sent":
        return <MessageCircle className="h-4 w-4 text-green-500" />;
      case "ai_call_started":
        return <Phone className="h-4 w-4 text-purple-500" />;
      case "ai_call_ended":
        return <Phone className="h-4 w-4 text-gray-500" />;
      default:
        return <div className="h-4 w-4 bg-gray-400 rounded-full" />;
    }
  };

  const formatTimeAgo = (timestamp: string | Date) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now.getTime() - time.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return "לפני רגע";
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `לפני ${minutes} דקות`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `לפני ${hours} שעות`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `לפני ${days} ימים`;
    }
  };

  return (
    <div className="space-y-6">
      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>פעילות אחרונה</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center space-x-3 space-x-reverse">
                  <Skeleton className="h-8 w-8 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
              ))}
            </div>
          ) : activities.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <div className="w-6 h-6 bg-gray-300 rounded-full"></div>
              </div>
              <p>אין פעילות עדיין</p>
              <p className="text-sm">הפעילות תופיע כאן כשתתחיל לעבוד במערכת</p>
            </div>
          ) : (
            <div className="flow-root">
              <ul className="-mb-8">
                {activities.slice(0, 10).map((activity, index) => (
                  <li key={activity.id}>
                    <div className="relative pb-8">
                      {index < activities.length - 1 && (
                        <span
                          className="absolute top-4 right-4 -ml-px h-full w-0.5 bg-gray-200"
                          aria-hidden="true"
                        />
                      )}
                      <div className="relative flex space-x-3 space-x-reverse">
                        <div>
                          <span className="h-8 w-8 rounded-full bg-white border-2 border-gray-200 flex items-center justify-center">
                            {getActivityIcon(activity.type)}
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5">
                          <div>
                            <p className="text-sm text-gray-500">
                              {activity.description}
                            </p>
                            <p className="mt-0.5 text-xs text-gray-400">
                              {formatTimeAgo(activity.timestamp)}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>פעולות מהירות</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="outline" className="w-full justify-start">
            <UserPlus className="ml-3 h-4 w-4 text-blue-500" />
            הוסף לקוח חדש
          </Button>
          <Button variant="outline" className="w-full justify-start">
            <MessageCircle className="ml-3 h-4 w-4 text-green-500" />
            שלח הודעה קבוצתית
          </Button>
          <Button variant="outline" className="w-full justify-start">
            <Bot className="ml-3 h-4 w-4 text-purple-500" />
            מרכז שיחות AI
          </Button>
          <Button variant="outline" className="w-full justify-start">
            <Download className="ml-3 h-4 w-4 text-orange-500" />
            ייצא רשימת לקוחות
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
