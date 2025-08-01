import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import TopBar from "../components/layout/topbar";
import CustomerList from "../components/customer-list";
import AddCustomerModal from "../components/modals/add-customer-modal";
import WhatsAppModal from "../components/modals/whatsapp-modal";
import AICallModal from "../components/modals/ai-call-modal";
import { Customer } from "../../../shared/schema";

export default function Customers() {
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [showAddCustomer, setShowAddCustomer] = useState(false);
  const [showWhatsApp, setShowWhatsApp] = useState(false);
  const [showAICall, setShowAICall] = useState(false);

  const { data: customers = [], isLoading } = useQuery({
    queryKey: ["/api/customers"],
  });

  const handleWhatsAppClick = (customer: Customer) => {
    setSelectedCustomer(customer);
    setShowWhatsApp(true);
  };

  const handleAICallClick = (customer: Customer) => {
    setSelectedCustomer(customer);
    setShowAICall(true);
  };

  return (
    <>
      <TopBar title="לקוחות" />
      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1">
          <CustomerList 
            customers={customers}
            isLoading={isLoading}
            onWhatsAppClick={handleWhatsAppClick}
            onAICallClick={handleAICallClick}
            onAddCustomer={() => setShowAddCustomer(true)}
            showFullTable={true}
          />
        </div>
      </div>

      <AddCustomerModal 
        open={showAddCustomer}
        onOpenChange={setShowAddCustomer}
      />
      
      <WhatsAppModal
        open={showWhatsApp}
        onOpenChange={setShowWhatsApp}
        customer={selectedCustomer}
      />
      
      <AICallModal
        open={showAICall}
        onOpenChange={setShowAICall}
        customer={selectedCustomer}
      />
    </>
  );
}
