import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Stats } from "../../../shared/schema";
import { Users, MessageCircle, Phone, Star } from "lucide-react";

export default function StatsCards() {
  const { data: stats, isLoading } = useQuery<Stats>({
    queryKey: ["/api/stats"],
  });

  const statsCards = [
    {
      title: "סך הלקוחות",
      value: stats?.totalCustomers || 0,
      icon: Users,
      color: "bg-blue-500",
    },
    {
      title: "הודעות היום", 
      value: stats?.todayMessages || 0,
      icon: MessageCircle,
      color: "bg-green-500",
    },
    {
      title: "שיחות AI",
      value: stats?.aiCalls || 0, 
      icon: Phone,
      color: "bg-purple-500",
    },
    {
      title: "לקוחות פעילים",
      value: stats?.activeCustomers || 0,
      icon: Star,
      color: "bg-orange-500",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {statsCards.map((stat, index) => {
        const Icon = stat.icon;
        
        return (
          <Card key={index}>
            <CardContent className="p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className={`w-8 h-8 ${stat.color} rounded-full flex items-center justify-center`}>
                    <Icon className="h-4 w-4 text-white" />
                  </div>
                </div>
                <div className="mr-3">
                  <p className="text-sm font-medium text-gray-500">{stat.title}</p>
                  {isLoading ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    <p className="text-2xl font-semibold text-gray-900">
                      {stat.value.toLocaleString('he-IL')}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
