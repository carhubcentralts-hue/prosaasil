import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Customer } from "../../../../shared/schema";
import { Phone, PhoneOff, MicOff, User } from "lucide-react";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

interface AICallModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customer: Customer | null;
}

type CallStatus = "initiated" | "connecting" | "active" | "ended" | "failed";

export default function AICallModal({ open, onOpenChange, customer }: AICallModalProps) {
  const [callStatus, setCallStatus] = useState<CallStatus>("initiated");
  const [notes, setNotes] = useState("");
  const [currentCallId, setCurrentCallId] = useState<number | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const startCallMutation = useMutation({
    mutationFn: (data: { customerId: number; customerPhone: string }) => 
      apiRequest("/api/ai-calls/start", {
        method: "POST",
        body: data,
      }),
    onSuccess: (data: any) => {
      setCurrentCallId(data.id);
      toast({
        title: "שיחה החלה",
        description: "שיחת AI החלה בהצלחה",
      });
    },
    onError: (error: any) => {
      toast({
        title: "שגיאה",
        description: error.message || "שגיאה בהתחלת השיחה",
        variant: "destructive",
      });
      setCallStatus("failed");
    },
  });

  const endCallMutation = useMutation({
    mutationFn: (data: { callId: number; notes: string }) => 
      apiRequest(`/api/ai-calls/${data.callId}/end`, {
        method: "POST",
        body: { notes: data.notes },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/ai-calls"] });
      queryClient.invalidateQueries({ queryKey: ["/api/activities"] });
      
      toast({
        title: "השיחה הסתיימה",
        description: "שיחת AI הסתיימה בהצלחה",
      });
      
      setCallStatus("ended");
      setTimeout(() => {
        onOpenChange(false);
        resetModal();
      }, 2000);
    },
    onError: (error: any) => {
      toast({
        title: "שגיאה",
        description: error.message || "שגיאה בסיום השיחה",
        variant: "destructive",
      });
    },
  });

  const resetModal = () => {
    setCallStatus("initiated");
    setNotes("");
    setCurrentCallId(null);
  };

  useEffect(() => {
    if (open && customer) {
      // Start call automatically when modal opens
      startCallMutation.mutate({
        customerId: customer.id,
        customerPhone: customer.phone,
      });
      
      // Simulate call progression
      const timer1 = setTimeout(() => setCallStatus("connecting"), 1000);
      const timer2 = setTimeout(() => setCallStatus("active"), 3000);
      
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
      };
    }
    
    if (!open) {
      resetModal();
    }
  }, [open, customer]);

  const handleEndCall = () => {
    if (currentCallId) {
      endCallMutation.mutate({
        callId: currentCallId,
        notes,
      });
    }
  };

  const getStatusInfo = (status: CallStatus) => {
    switch (status) {
      case "initiated":
        return {
          text: "מתחיל שיחה...",
          color: "bg-yellow-100 text-yellow-800",
          description: "מכין את המערכת"
        };
      case "connecting":
        return {
          text: "מתחבר...",
          color: "bg-blue-100 text-blue-800",
          description: "השיחה החלה - AI מתחבר..."
        };
      case "active":
        return {
          text: "שיחה פעילה",
          color: "bg-green-100 text-green-800",
          description: "השיחה פעילה"
        };
      case "ended":
        return {
          text: "הסתיים",
          color: "bg-gray-100 text-gray-800",
          description: "השיחה הסתיימה"
        };
      case "failed":
        return {
          text: "נכשל",
          color: "bg-red-100 text-red-800",
          description: "השיחה נכשלה"
        };
      default:
        return {
          text: status,
          color: "bg-gray-100 text-gray-800",
          description: ""
        };
    }
  };

  const statusInfo = getStatusInfo(callStatus);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="bg-purple-500 text-white rounded-t-lg -m-6 p-6 mb-4">
          <div className="flex items-center space-x-3 space-x-reverse">
            <Phone className="h-6 w-6" />
            <DialogTitle className="text-white">שיחת AI</DialogTitle>
          </div>
        </DialogHeader>
        
        {/* Call Interface */}
        <div className="text-center space-y-6">
          {/* Customer Avatar */}
          <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center mx-auto">
            <User className="h-12 w-12 text-purple-500" />
          </div>
          
          {/* Customer Info */}
          <div>
            <h4 className="text-xl font-medium text-gray-900 mb-2">
              {customer?.name || "לקוח"}
            </h4>
            <p className="text-gray-500 mb-4">{customer?.phone}</p>
          </div>
          
          {/* Call Status */}
          <div className="space-y-2">
            <Badge className={statusInfo.color}>
              {statusInfo.text}
            </Badge>
            <p className="text-sm text-gray-600">{statusInfo.description}</p>
            {callStatus === "active" && (
              <div className="flex items-center justify-center space-x-2 space-x-reverse">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm text-green-600">בשיחה...</span>
              </div>
            )}
          </div>
          
          {/* Call Controls */}
          <div className="flex justify-center space-x-4 space-x-reverse">
            <Button
              onClick={handleEndCall}
              disabled={callStatus === "ended" || callStatus === "failed" || endCallMutation.isPending}
              className="w-12 h-12 bg-red-500 hover:bg-red-600 rounded-full"
            >
              <PhoneOff className="h-5 w-5" />
            </Button>
            <Button
              variant="outline"
              className="w-12 h-12 rounded-full"
              disabled
            >
              <MicOff className="h-5 w-5" />
            </Button>
          </div>
          
          {/* Call Notes */}
          <div className="text-right space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              הערות שיחה
            </label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="הערות על השיחה..."
              rows={3}
              className="w-full"
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
