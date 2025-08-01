import { Search, Bell, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TopBarProps {
  title: string;
}

export default function TopBar({ title }: TopBarProps) {
  return (
    <div className="flex items-center justify-between h-16 px-4 bg-white border-b border-gray-200">
      <div className="flex items-center">
        <Button variant="ghost" size="sm" className="lg:hidden p-2">
          <Menu className="h-5 w-5" />
        </Button>
        <h1 className="mr-4 text-2xl font-semibold text-gray-900">{title}</h1>
      </div>
      <div className="flex items-center space-x-4 space-x-reverse">
        <div className="relative">
          <Input 
            type="search" 
            placeholder="חיפוש לקוחות..." 
            className="w-64 pr-10"
          />
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
        </div>
        <Button variant="ghost" size="sm">
          <Bell className="h-5 w-5" />
        </Button>
      </div>
    </div>
  );
}
