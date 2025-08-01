import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import TopBar from "../components/layout/topbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AiCall } from "../../../shared/schema";
import { Phone, Clock, PhoneCall, PhoneOff } from "lucide-react";

export default function AICalls() {
  const { data: calls = [], isLoading } = useQuery<AiCall[]>({
    queryKey: ["/api/ai-calls"],
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case "initiated":
        return "bg-yellow-100 text-yellow-800";
      case "connecting":
        return "bg-blue-100 text-blue-800";
      case "active":
        return "bg-green-100 text-green-800";
      case "ended":
        return "bg-gray-100 text-gray-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "initiated":
        return "הוזמן";
      case "connecting":
        return "מתחבר";
      case "active":
        return "פעיל";
      case "ended":
        return "הסתיים";
      case "failed":
        return "נכשל";
      default:
        return status;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "-";
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  return (
    <>
      <TopBar title="שיחות AI" />
      <div className="flex-1 overflow-auto p-6">
        <div className="space-y-6">
          {/* Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">כל השיחות</CardTitle>
                <PhoneCall className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{calls.length}</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">שיחות היום</CardTitle>
                <Phone className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {calls.filter(c => 
                    new Date(c.timestamp).toDateString() === new Date().toDateString()
                  ).length}
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">שיחות פעילות</CardTitle>
                <div className="w-4 h-4 bg-green-500 rounded-full animate-pulse"></div>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {calls.filter(c => c.status === "active").length}
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">זמן ממוצע</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {calls.filter(c => c.duration).length > 0
                    ? formatDuration(
                        Math.round(
                          calls.filter(c => c.duration).reduce((sum, c) => sum + (c.duration || 0), 0) /
                          calls.filter(c => c.duration).length
                        )
                      )
                    : "-"}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Calls List */}
          <Card>
            <CardHeader>
              <CardTitle>שיחות אחרונות</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="animate-pulse">
                      <div className="h-16 bg-gray-200 rounded"></div>
                    </div>
                  ))}
                </div>
              ) : calls.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <PhoneCall className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>אין שיחות AI עדיין</p>
                  <p className="text-sm">השיחות יופיעו כאן לאחר ביצוע השיחה הראשונה</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {calls.map((call) => (
                    <div key={call.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-3 space-x-reverse">
                          <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                            <Phone className="w-5 h-5 text-purple-600" />
                          </div>
                          <div>
                            <span className="font-medium">{call.customerPhone}</span>
                            <div className="flex items-center space-x-2 space-x-reverse mt-1">
                              <Badge className={getStatusColor(call.status)}>
                                {getStatusText(call.status)}
                              </Badge>
                              {call.duration && (
                                <span className="text-sm text-gray-500">
                                  משך: {formatDuration(call.duration)}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <span className="text-sm text-gray-500">
                          {new Date(call.timestamp).toLocaleString('he-IL')}
                        </span>
                      </div>
                      {call.notes && (
                        <p className="text-gray-700 mt-2">{call.notes}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
