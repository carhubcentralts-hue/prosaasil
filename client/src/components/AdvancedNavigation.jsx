import React, { useState } from 'react';
import { 
  Users, 
  Phone, 
  MessageSquare, 
  BarChart3, 
  Settings, 
  Calendar,
  FileText,
  Target,
  Bell,
  Search
} from 'lucide-react';

const AdvancedNavigation = ({ activeTab, onTabChange }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const navigationItems = [
    { key: 'dashboard', label: 'דשבורד', icon: BarChart3, color: 'blue' },
    { key: 'crm', label: 'ניהול לקוחות', icon: Users, color: 'green' },
    { key: 'calls', label: 'מרכז שיחות', icon: Phone, color: 'purple' },
    { key: 'whatsapp', label: 'WhatsApp', icon: MessageSquare, color: 'green' },
    { key: 'calendar', label: 'יומן', icon: Calendar, color: 'orange' },
    { key: 'tasks', label: 'משימות', icon: Target, color: 'red' },
    { key: 'reports', label: 'דוחות', icon: FileText, color: 'indigo' },
    { key: 'settings', label: 'הגדרות', icon: Settings, color: 'gray' }
  ];

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          {/* Logo and Title */}
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-xl font-bold text-gray-900 font-hebrew">Agent Locator CRM</h1>
            </div>
          </div>

          {/* Navigation Items */}
          <div className="hidden md:block">
            <div className="flex items-baseline space-x-4">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.key;
                
                return (
                  <button
                    key={item.key}
                    onClick={() => onTabChange(item.key)}
                    className={`px-3 py-2 rounded-md text-sm font-medium font-hebrew transition-colors duration-200 flex items-center gap-2 ${
                      isActive
                        ? `bg-${item.color}-100 text-${item.color}-700 border-b-2 border-${item.color}-500`
                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Search and Notifications */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="חיפוש מהיר..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-64 font-hebrew text-sm"
              />
            </div>
            
            <button className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-0 left-0 w-2 h-2 bg-red-500 rounded-full"></span>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation */}
      <div className="md:hidden">
        <div className="px-2 pt-2 pb-3 space-y-1 bg-gray-50">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.key;
            
            return (
              <button
                key={item.key}
                onClick={() => onTabChange(item.key)}
                className={`w-full text-right px-3 py-2 rounded-md text-base font-medium font-hebrew flex items-center gap-3 ${
                  isActive
                    ? `bg-${item.color}-100 text-${item.color}-700`
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
};

export default AdvancedNavigation;