import React, { useState, useEffect } from 'react';
import { Plus, Users, Target, Calendar, CheckCircle, Circle, Clock } from 'lucide-react';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: any) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: any) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    low: "bg-green-100 text-green-800",
    medium: "bg-yellow-100 text-yellow-800",
    high: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Task and Contact interfaces
interface CRMTask {
  id: string;
  title: string;
  description?: string;
  status: 'todo' | 'doing' | 'done';
  priority: 'low' | 'medium' | 'high';
  owner_name?: string;
  lead_name?: string;
  due_date?: string;
  created_at: string;
}

interface CRMContact {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  tags: string[];
  lastContact?: string;
}

export function CrmPage() {
  const [tasks, setTasks] = useState<CRMTask[]>([]);
  const [contacts, setContacts] = useState<CRMContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'tasks' | 'contacts'>('tasks');
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Fetch real tasks from API
      const response = await fetch('/api/crm/tasks', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setTasks(data.tasks || []);
      } else {
        console.error('Failed to load tasks');
        setTasks([]);
      }
      
      // Contacts will be loaded from customers table in the future
      setContacts([]);
      
    } catch (error) {
      console.error('Error loading CRM data:', error);
      setTasks([]);
      setContacts([]);
    } finally {
      setLoading(false);
    }
  };

  const getTasksByStatus = (status: 'todo' | 'doing' | 'done') => {
    return tasks.filter(task => task.status === status);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'high';
      case 'medium': return 'medium';
      case 'low': return 'low';
      default: return 'default';
    }
  };

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'high': return 'גבוה';
      case 'medium': return 'בינוני';
      case 'low': return 'נמוך';
      default: return priority;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'todo': return <Circle className="w-4 h-4 text-gray-400" />;
      case 'doing': return <Clock className="w-4 h-4 text-blue-500" />;
      case 'done': return <CheckCircle className="w-4 h-4 text-green-500" />;
      default: return <Circle className="w-4 h-4" />;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'todo': return 'לביצוע';
      case 'doing': return 'בביצוע';
      case 'done': return 'הושלם';
      default: return status;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען נתוני CRM...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900">CRM</h1>
          </div>
          
          <div className="flex items-center gap-3">
            <Button 
              onClick={() => activeTab === 'tasks' ? setShowTaskModal(true) : setShowContactModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              {activeTab === 'tasks' ? 'משימה חדשה' : 'איש קשר חדש'}
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex space-x-8" dir="ltr">
          <button
            onClick={() => setActiveTab('tasks')}
            className={`${
              activeTab === 'tasks'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Target className="w-4 h-4 mr-2" />
            משימות ({tasks.length})
          </button>
          <button
            onClick={() => setActiveTab('contacts')}
            className={`${
              activeTab === 'contacts'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Users className="w-4 h-4 mr-2" />
            אנשי קשר ({contacts.length})
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'tasks' ? (
          // Kanban Board for Tasks
          <div className="h-full p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-full">
              {/* Todo Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Circle className="w-5 h-5 text-gray-400" />
                  <h3 className="font-semibold text-gray-900">לביצוע</h3>
                  <Badge>{getTasksByStatus('todo').length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getTasksByStatus('todo').map((task) => (
                    <Card key={task.id} className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{task.title}</h4>
                        <Badge variant={getPriorityColor(task.priority)}>
                          {getPriorityLabel(task.priority)}
                        </Badge>
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>{task.lead_name || task.owner_name}</span>
                        {task.due_date && (
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(task.due_date).toLocaleDateString('he-IL')}
                          </div>
                        )}
                      </div>
                    </Card>
                  ))}
                  
                  {getTasksByStatus('todo').length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Circle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות לביצוע</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Doing Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="w-5 h-5 text-blue-500" />
                  <h3 className="font-semibold text-gray-900">בביצוע</h3>
                  <Badge>{getTasksByStatus('doing').length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getTasksByStatus('doing').map((task) => (
                    <Card key={task.id} className="p-4 border-blue-200 bg-blue-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{task.title}</h4>
                        <Badge variant={getPriorityColor(task.priority)}>
                          {getPriorityLabel(task.priority)}
                        </Badge>
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>{task.lead_name || task.owner_name}</span>
                        {task.due_date && (
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(task.due_date).toLocaleDateString('he-IL')}
                          </div>
                        )}
                      </div>
                    </Card>
                  ))}
                  
                  {getTasksByStatus('doing').length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות בביצוע</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Done Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <h3 className="font-semibold text-gray-900">הושלם</h3>
                  <Badge>{getTasksByStatus('done').length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getTasksByStatus('done').map((task) => (
                    <Card key={task.id} className="p-4 border-green-200 bg-green-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{task.title}</h4>
                        <Badge variant={getPriorityColor(task.priority)}>
                          {getPriorityLabel(task.priority)}
                        </Badge>
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>{task.lead_name || task.owner_name}</span>
                        <div className="flex items-center gap-1">
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          הושלם
                        </div>
                      </div>
                    </Card>
                  ))}
                  
                  {getTasksByStatus('done').length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <CheckCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות שהושלמו</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          // Contacts List
          <div className="h-full p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {contacts.map((contact) => (
                <Card key={contact.id} className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">{contact.name}</h3>
                      {contact.company && (
                        <p className="text-sm text-gray-600">{contact.company}</p>
                      )}
                    </div>
                    <Users className="w-5 h-5 text-gray-400" />
                  </div>
                  
                  <div className="space-y-2 mb-4">
                    {contact.email && (
                      <p className="text-sm text-gray-600" dir="ltr">{contact.email}</p>
                    )}
                    {contact.phone && (
                      <p className="text-sm text-gray-600" dir="ltr">{contact.phone}</p>
                    )}
                  </div>
                  
                  {contact.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-4">
                      {contact.tags.map((tag, index) => (
                        <Badge key={index} variant="default">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                  
                  {contact.lastContact && (
                    <p className="text-xs text-gray-500">
                      קשר אחרון: {new Date(contact.lastContact).toLocaleDateString('he-IL')}
                    </p>
                  )}
                </Card>
              ))}
              
              {contacts.length === 0 && (
                <div className="col-span-full text-center py-12">
                  <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">אין אנשי קשר</h3>
                  <p className="text-gray-500">התחל בהוספת אנשי הקשר שלך</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}