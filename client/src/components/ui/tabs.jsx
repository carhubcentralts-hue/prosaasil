import React, { createContext, useContext, useState } from 'react';

const TabsContext = createContext();

export const Tabs = ({ defaultValue, value, onValueChange, children, className = '' }) => {
  const [activeTab, setActiveTab] = useState(value || defaultValue);
  
  const handleTabChange = (newValue) => {
    setActiveTab(newValue);
    if (onValueChange) {
      onValueChange(newValue);
    }
  };

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab: handleTabChange }}>
      <div className={className}>
        {children}
      </div>
    </TabsContext.Provider>
  );
};

export const TabsList = ({ children, className = '' }) => {
  return (
    <div className={`flex space-x-1 rounded-lg bg-gray-100 p-1 ${className}`}>
      {children}
    </div>
  );
};

export const TabsTrigger = ({ value, children, className = '' }) => {
  const { activeTab, setActiveTab } = useContext(TabsContext);
  const isActive = activeTab === value;

  return (
    <button
      className={`
        flex items-center justify-center whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium 
        transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring 
        focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50
        ${isActive 
          ? 'bg-white text-gray-900 shadow-sm' 
          : 'text-gray-600 hover:bg-gray-200'
        }
        ${className}
      `}
      onClick={() => setActiveTab(value)}
    >
      {children}
    </button>
  );
};

export const TabsContent = ({ value, children, className = '' }) => {
  const { activeTab } = useContext(TabsContext);
  
  if (activeTab !== value) {
    return null;
  }

  return (
    <div className={`mt-2 ${className}`}>
      {children}
    </div>
  );
};