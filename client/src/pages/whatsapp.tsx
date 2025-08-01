import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import TopBar from "../components/layout/topbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WhatsappMessage } from "../../../shared/schema";
import { MessageCircle, Send, Clock, CheckCheck } from "lucide-react";

export default function WhatsApp() {
  const { data: messages = [], isLoading } = useQuery<WhatsappMessage[]>({
    queryKey: ["/api/whatsapp/messages"],
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "sent":
        return <Clock className="w-4 h-4" />;
      case "delivered":
        return <CheckCheck className="w-4 h-4" />;
      case "read":
        return <CheckCheck className="w-4 h-4 text-blue-500" />;
      case "failed":
        return <span className="text-red-500">✗</span>;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "sent":
        return "bg-yellow-100 text-yellow-800";
      case "delivered":
        return "bg-green-100 text-green-800";
      case "read":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <>
      <TopBar title="WhatsApp" />
      <div className="flex-1 overflow-auto p-6">
        <div className="space-y-6">
          {/* Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">כל הההודעות</CardTitle>
                <MessageCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{messages.length}</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">נשלחו היום</CardTitle>
                <Send className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {messages.filter(m => 
                    m.direction === "outbound" && 
                    new Date(m.timestamp).toDateString() === new Date().toDateString()
                  ).length}
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">התקבלו היום</CardTitle>
                <MessageCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {messages.filter(m => 
                    m.direction === "inbound" && 
                    new Date(m.timestamp).toDateString() === new Date().toDateString()
                  ).length}
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">שיעור הצלחה</CardTitle>
                <CheckCheck className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {messages.length > 0 
                    ? Math.round((messages.filter(m => m.status !== "failed").length / messages.length) * 100)
                    : 0}%
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Messages List */}
          <Card>
            <CardHeader>
              <CardTitle>הודעות אחרונות</CardTitle>
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
              ) : messages.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <MessageCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>אין הודעות WhatsApp עדיין</p>
                  <p className="text-sm">ההודעות יופיעו כאן לאחר השליחה הראשונה</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div key={message.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2 space-x-reverse">
                          <span className="font-medium">{message.customerPhone}</span>
                          <Badge variant={message.direction === "outbound" ? "default" : "secondary"}>
                            {message.direction === "outbound" ? "יוצא" : "נכנס"}
                          </Badge>
                          <Badge className={getStatusColor(message.status)}>
                            <div className="flex items-center space-x-1 space-x-reverse">
                              {getStatusIcon(message.status)}
                              <span>{message.status === "sent" ? "נשלח" : 
                                     message.status === "delivered" ? "נמסר" :
                                     message.status === "read" ? "נקרא" : "נכשל"}</span>
                            </div>
                          </Badge>
                        </div>
                        <span className="text-sm text-gray-500">
                          {new Date(message.timestamp).toLocaleString('he-IL')}
                        </span>
                      </div>
                      <p className="text-gray-700">{message.message}</p>
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
