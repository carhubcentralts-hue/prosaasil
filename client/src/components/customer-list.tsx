import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Customer } from "../../../shared/schema";
import { MessageCircle, Phone, Edit, Plus, User } from "lucide-react";

interface CustomerListProps {
  customers: Customer[];
  isLoading: boolean;
  onWhatsAppClick: (customer: Customer) => void;
  onAICallClick: (customer: Customer) => void;
  onAddCustomer: () => void;
  showFullTable?: boolean;
}

export default function CustomerList({
  customers,
  isLoading,
  onWhatsAppClick,
  onAICallClick,
  onAddCustomer,
  showFullTable = false
}: CustomerListProps) {
  const displayCustomers = showFullTable ? customers : customers.slice(0, 5);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800";
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "inactive":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "active":
        return "פעיל";
      case "pending":
        return "ממתין";
      case "inactive":
        return "לא פעיל";
      default:
        return status;
    }
  };

  return (
    <Card className={showFullTable ? "" : "lg:col-span-2"}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle>{showFullTable ? "כל הלקוחות" : "לקוחות אחרונים"}</CardTitle>
        <Button onClick={onAddCustomer} className="bg-primary hover:bg-primary/90">
          <Plus className="ml-2 h-4 w-4" />
          הוסף לקוח
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-4 space-x-reverse">
                <Skeleton className="h-12 w-12 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-4 w-[150px]" />
                </div>
              </div>
            ))}
          </div>
        ) : displayCustomers.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <User className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>אין לקוחות עדיין</p>
            <p className="text-sm">הוסף את הלקוח הראשון שלך</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    שם
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    טלפון
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {displayCustomers.map((customer) => (
                  <tr key={customer.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                            <User className="h-5 w-5 text-gray-600" />
                          </div>
                        </div>
                        <div className="mr-4">
                          <div className="text-sm font-medium text-gray-900">
                            {customer.name}
                          </div>
                          {customer.email && (
                            <div className="text-sm text-gray-500">
                              {customer.email}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {customer.phone}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge className={getStatusColor(customer.status)}>
                        {getStatusText(customer.status)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-left text-sm font-medium">
                      <div className="flex space-x-2 space-x-reverse">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onWhatsAppClick(customer)}
                          className="text-green-600 hover:text-green-900"
                        >
                          <MessageCircle className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onAICallClick(customer)}
                          className="text-purple-600 hover:text-purple-900"
                        >
                          <Phone className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-blue-600 hover:text-blue-900"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
