import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { insertCustomerSchema, InsertCustomer } from "../../../../shared/schema";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

interface AddCustomerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AddCustomerModal({ open, onOpenChange }: AddCustomerModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  const form = useForm<InsertCustomer>({
    resolver: zodResolver(insertCustomerSchema),
    defaultValues: {
      name: "",
      phone: "",
      email: "",
      notes: "",
      status: "active",
    },
  });

  const createCustomerMutation = useMutation({
    mutationFn: (data: InsertCustomer) => apiRequest("/api/customers", {
      method: "POST",
      body: data,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/customers"] });
      queryClient.invalidateQueries({ queryKey: ["/api/stats"] });
      queryClient.invalidateQueries({ queryKey: ["/api/activities"] });
      
      toast({
        title: "הצלחה",
        description: "הלקוח נוסף בהצלחה",
      });
      
      form.reset();
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: "שגיאה",
        description: error.message || "שגיאה בהוספת הלקוח",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: InsertCustomer) => {
    createCustomerMutation.mutate(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>הוסף לקוח חדש</DialogTitle>
        </DialogHeader>
        
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>שם מלא</FormLabel>
                  <FormControl>
                    <Input placeholder="הכנס שם מלא" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>מספר טלפון</FormLabel>
                  <FormControl>
                    <Input placeholder="050-1234567" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>כתובת אימייל (אופציונלי)</FormLabel>
                  <FormControl>
                    <Input 
                      type="email" 
                      placeholder="example@email.com" 
                      {...field} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>סטטוס</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="בחר סטטוס" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="active">פעיל</SelectItem>
                      <SelectItem value="pending">ממתין</SelectItem>
                      <SelectItem value="inactive">לא פעיל</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>הערות (אופציונלי)</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="הערות נוספות..." 
                      rows={3}
                      {...field} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <div className="flex space-x-3 space-x-reverse pt-4">
              <Button 
                type="submit" 
                className="flex-1"
                disabled={createCustomerMutation.isPending}
              >
                {createCustomerMutation.isPending ? "שומר..." : "שמור"}
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                className="flex-1"
                onClick={() => onOpenChange(false)}
              >
                ביטול
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
