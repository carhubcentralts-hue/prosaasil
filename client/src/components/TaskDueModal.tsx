import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Phone, MessageCircle, Clock, CheckCircle } from 'lucide-react';

interface TaskDueModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: {
    id: string;
    customerName: string;
    customerPhone: string;
    taskTitle: string;
    description?: string;
  };
}

export function TaskDueModal({ isOpen, onClose, task }: TaskDueModalProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleCall = async () => {
    setIsLoading(true);
    // API call to initiate call
    setTimeout(() => setIsLoading(false), 1000);
  };

  const handleWhatsApp = () => {
    const url = `https://wa.me/${task.customerPhone.replace(/[^0-9]/g, '')}`;
    window.open(url, '_blank');
  };

  const handleSnooze = async (minutes: number) => {
    setIsLoading(true);
    // API call to snooze task
    setTimeout(() => {
      setIsLoading(false);
      onClose();
    }, 500);
  };

  const handleDone = async () => {
    setIsLoading(true);
    // API call to mark task as done
    setTimeout(() => {
      setIsLoading(false);
      onClose();
    }, 500);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md mx-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="text-right">משימה דחופה</DialogTitle>
          <DialogDescription className="text-right">
            {task.taskTitle}
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4">
          <div className="text-right">
            <h3 className="font-semibold">{task.customerName}</h3>
            <p className="text-muted-foreground">{task.customerPhone}</p>
            {task.description && (
              <p className="text-sm mt-2">{task.description}</p>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <Button
              onClick={handleCall}
              disabled={isLoading}
              className="flex items-center gap-2"
              data-testid="button-call"
            >
              <Phone className="h-4 w-4" />
              התקשר
            </Button>
            
            <Button
              onClick={handleWhatsApp}
              variant="outline"
              className="flex items-center gap-2"
              data-testid="button-whatsapp"
            >
              <MessageCircle className="h-4 w-4" />
              WhatsApp
            </Button>
            
            <Button
              onClick={() => handleSnooze(15)}
              variant="outline"
              disabled={isLoading}
              className="flex items-center gap-2"
              data-testid="button-snooze-15"
            >
              <Clock className="h-4 w-4" />
              נודניק 15ד'
            </Button>
            
            <Button
              onClick={handleDone}
              variant="default"
              disabled={isLoading}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700"
              data-testid="button-done"
            >
              <CheckCircle className="h-4 w-4" />
              בוצע
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}