import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Customer, WhatsappMessage } from "../../../../shared/schema";
import { MessageCircle, Send } from "lucide-react";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

interface WhatsAppModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customer: Customer | null;
}

export default function WhatsAppModal({ open, onOpenChange, customer }: WhatsAppModalProps) {
  const [message, setMessage] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: messages = [] } = useQuery<WhatsappMessage[]>({
    queryKey: ["/api/whatsapp/messages", customer?.id],
    enabled: !!customer && open,
  });

  const sendMessageMutation = useMutation({
    mutationFn: (data: { customerId: number; customerPhone: string; message: string }) => 
      apiRequest("/api/whatsapp/send", {
        method: "POST",
        body: {
          ...data,
          direction: "outbound",
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/whatsapp/messages"] });
      queryClient.invalidateQueries({ queryKey: ["/api/activities"] });
      
      toast({
        title: "נשלח בהצלחה",
        description: "ההודעה נשלחה ב-WhatsApp",
      });
      
      setMessage("");
    },
    onError: (error: any) => {
      toast({
        title: "שגיאה בשליחה",
        description: error.message || "שגיאה בשליחת ההודעה",
        variant: "destructive",
      });
    },
  });

  const handleSendMessage = () => {
    if (!message.trim() || !customer) return;
    
    sendMessageMutation.mutate({
      customerId: customer.id,
      customerPhone: customer.phone,
      message: message.trim(),
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const customerMessages = messages.filter(m => m.customerId === customer?.id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md h-[600px] flex flex-col">
        <DialogHeader className="bg-green-500 text-white rounded-t-lg -m-6 p-6 mb-4">
          <div className="flex items-center space-x-3 space-x-reverse">
            <MessageCircle className="h-6 w-6" />
            <div>
              <DialogTitle className="text-white">
                {customer?.name || "לקוח"}
              </DialogTitle>
              <p className="text-green-100 text-sm">{customer?.phone}</p>
            </div>
          </div>
        </DialogHeader>
        
        {/* Chat Messages */}
        <ScrollArea className="flex-1 p-4 bg-gray-50 rounded">
          <div className="space-y-4">
            {customerMessages.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <MessageCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>אין הודעות עדיין</p>
                <p className="text-sm">השיחה תתחיל כאן</p>
              </div>
            ) : (
              customerMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-xs px-4 py-2 rounded-lg text-sm ${
                      msg.direction === "outbound"
                        ? "chat-bubble-sent text-white"
                        : "chat-bubble-received text-gray-700"
                    }`}
                  >
                    <p>{msg.message}</p>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs opacity-75">
                        {new Date(msg.timestamp).toLocaleTimeString('he-IL', {
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                      {msg.direction === "outbound" && (
                        <Badge variant="secondary" className="text-xs">
                          {msg.status === "sent" ? "נשלח" :
                           msg.status === "delivered" ? "נמסר" :
                           msg.status === "read" ? "נקרא" : "נכשל"}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
        
        {/* Message Input */}
        <div className="flex space-x-2 space-x-reverse pt-4 border-t">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="הקלד הודעה..."
            className="flex-1"
            disabled={sendMessageMutation.isPending}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!message.trim() || sendMessageMutation.isPending}
            className="bg-green-500 hover:bg-green-600"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
