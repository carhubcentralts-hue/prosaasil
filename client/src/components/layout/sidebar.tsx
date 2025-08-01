import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { 
  LayoutDashboard, 
  Users, 
  MessageCircle, 
  Phone, 
  BarChart3, 
  Settings,
  User
} from "lucide-react";

const navigation = [
  { name: "לוח בקרה", href: "/", icon: LayoutDashboard },
  { name: "לקוחות", href: "/customers", icon: Users },
  { name: "WhatsApp", href: "/whatsapp", icon: MessageCircle },
  { name: "שיחות AI", href: "/ai-calls", icon: Phone },
  { name: "דוחות", href: "/reports", icon: BarChart3 },
  { name: "הגדרות", href: "/settings", icon: Settings },
];

export default function Sidebar() {
  const [location] = useLocation();

  return (
    <div className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0">
      <div className="flex flex-col flex-grow bg-white border-l border-gray-200 shadow-sm">
        {/* Logo */}
        <div className="flex items-center justify-center h-16 px-4 bg-primary text-primary-foreground">
          <h1 className="text-xl font-bold">מערכת CRM</h1>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = location === item.href;
            
            return (
              <Link key={item.name} href={item.href}>
                <a className={cn(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                  isActive 
                    ? "text-primary-foreground bg-primary" 
                    : "text-gray-700 hover:bg-gray-100"
                )}>
                  <Icon className="ml-3 h-5 w-5" />
                  {item.name}
                </a>
              </Link>
            );
          })}
        </nav>
        
        {/* User Profile */}
        <div className="flex items-center px-4 py-3 border-t border-gray-200">
          <div className="flex-shrink-0">
            <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
              <User className="h-4 w-4 text-primary-foreground" />
            </div>
          </div>
          <div className="mr-3">
            <p className="text-sm font-medium text-gray-700">יוסי כהן</p>
            <p className="text-xs text-gray-500">מנהל מכירות</p>
          </div>
        </div>
      </div>
    </div>
  );
}
