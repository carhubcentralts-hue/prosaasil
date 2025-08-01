import { Link, useLocation } from 'wouter';

const navigationItems = [
  { 
    name: 'לוח בקרה', 
    path: '/', 
    icon: 'fas fa-tachometer-alt',
    description: 'סקירה כללית של המערכת'
  },
  { 
    name: 'לקוחות', 
    path: '/customers', 
    icon: 'fas fa-users',
    description: 'ניהול לקוחות וליידים'
  },
  { 
    name: 'WhatsApp', 
    path: '/whatsapp', 
    icon: 'fab fa-whatsapp',
    description: 'הודעות והתכתבויות'
  },
  { 
    name: 'שיחות AI', 
    path: '/ai-calls', 
    icon: 'fas fa-phone',
    description: 'שיחות טלפון אוטומטיות'
  },
  { 
    name: 'חשבוניות', 
    path: '/invoices', 
    icon: 'fas fa-file-invoice',
    description: 'ניהול חשבוניות ותשלומים'
  },
  { 
    name: 'חתימות דיגיטליות', 
    path: '/signatures', 
    icon: 'fas fa-signature',
    description: 'חוזים וחתימות'
  }
];

export default function Sidebar() {
  const [location] = useLocation();

  return (
    <div className="w-64 bg-white shadow-lg border-l border-gray-200 flex flex-col">
      {/* Logo and Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center space-x-reverse space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg flex items-center justify-center">
            <i className="fas fa-chart-line text-white text-lg"></i>
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-800">CRM עברית</h1>
            <p className="text-sm text-gray-500">מערכת ניהול לקוחות</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-6 px-4 space-y-2">
        {navigationItems.map((item) => {
          const isActive = location === item.path;
          return (
            <Link key={item.path} to={item.path}>
              <div className={`
                group flex items-center space-x-reverse space-x-3 px-4 py-3 rounded-lg transition-all duration-200 cursor-pointer
                ${isActive 
                  ? 'bg-blue-50 text-blue-700 border-r-4 border-blue-500' 
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'
                }
              `}>
                <i className={`${item.icon} text-lg ${isActive ? 'text-blue-600' : 'text-gray-500 group-hover:text-gray-700'}`}></i>
                <div className="flex-1">
                  <div className={`font-medium ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>
                    {item.name}
                  </div>
                  <div className={`text-xs ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                    {item.description}
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <div className="bg-gradient-to-r from-blue-50 to-teal-50 rounded-lg p-4">
          <div className="flex items-center space-x-reverse space-x-2 mb-2">
            <i className="fas fa-crown text-yellow-500"></i>
            <span className="font-medium text-gray-700">גרסה מקצועית</span>
          </div>
          <p className="text-xs text-gray-600 mb-3">
            כל התכונות המתקדמות זמינות
          </p>
          <button className="w-full bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-medium py-2 px-4 rounded-md hover:from-blue-600 hover:to-teal-600 transition-all">
            <i className="fas fa-cog ml-2"></i>
            הגדרות מערכת
          </button>
        </div>
      </div>
    </div>
  );
}