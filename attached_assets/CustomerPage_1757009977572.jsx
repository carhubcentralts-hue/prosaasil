import React, { useState, useEffect } from 'react';
import { useRoute } from 'wouter';
import { 
  User, 
  Phone, 
  Mail, 
  Building,
  Calendar,
  MessageCircle,
  FileText,
  Activity,
  Edit,
  Save,
  X,
  Plus,
  Clock,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

function CustomerPage() {
  const [match, params] = useRoute('/crm/customer/:id');
  const [customer, setCustomer] = useState(null);
  const [interactions, setInteractions] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [newTask, setNewTask] = useState('');

  useEffect(() => {
    if (params?.id) {
      fetchCustomerData(params.id);
    }
  }, [params?.id]);

  const fetchCustomerData = async (customerId) => {
    try {
      setLoading(true);
      const [customerRes, interactionsRes, tasksRes] = await Promise.all([
        fetch(`/api/crm/customers/${customerId}`),
        fetch(`/api/crm/customers/${customerId}/interactions`),
        fetch(`/api/crm/customers/${customerId}/tasks`)
      ]);

      if (customerRes.ok) {
        const customerData = await customerRes.json();
        setCustomer(customerData);
        setEditData(customerData);
      }

      if (interactionsRes.ok) {
        const interactionsData = await interactionsRes.json();
        setInteractions(interactionsData.interactions || []);
      }

      if (tasksRes.ok) {
        const tasksData = await tasksRes.json();
        setTasks(tasksData.tasks || []);
      }
    } catch (error) {
      console.error('Failed to fetch customer data:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateCustomer = async () => {
    try {
      const response = await fetch(`/api/crm/customers/${params.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editData),
      });

      if (response.ok) {
        const updatedCustomer = await response.json();
        setCustomer(updatedCustomer);
        setIsEditing(false);
      }
    } catch (error) {
      console.error('Failed to update customer:', error);
    }
  };

  const addTask = async () => {
    if (!newTask.trim()) return;

    try {
      const response = await fetch('/api/crm/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          customer_id: params.id,
          title: newTask,
          status: 'pending'
        }),
      });

      if (response.ok) {
        setNewTask('');
        fetchCustomerData(params.id);
      }
    } catch (error) {
      console.error('Failed to add task:', error);
    }
  };

  const completeTask = async (taskId) => {
    try {
      const response = await fetch(`/api/crm/tasks/${taskId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: 'completed' }),
      });

      if (response.ok) {
        fetchCustomerData(params.id);
      }
    } catch (error) {
      console.error('Failed to complete task:', error);
    }
  };

  const getInteractionIcon = (type) => {
    switch (type) {
      case 'call':
        return <Phone className="w-4 h-4 text-blue-600" />;
      case 'whatsapp':
        return <MessageCircle className="w-4 h-4 text-green-600" />;
      case 'email':
        return <Mail className="w-4 h-4 text-purple-600" />;
      default:
        return <Activity className="w-4 h-4 text-gray-600" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'lead':
        return 'bg-yellow-100 text-yellow-800';
      case 'prospect':
        return 'bg-blue-100 text-blue-800';
      case 'customer':
        return 'bg-green-100 text-green-800';
      case 'inactive':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="h-64 bg-gray-200 rounded-lg"></div>
            <div className="md:col-span-2 h-64 bg-gray-200 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center py-12">
          <User className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            לקוח לא נמצא
          </h3>
          <p className="text-gray-500">
            הלקוח שחיפשת אינו קיים במערכת
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {customer.first_name} {customer.last_name}
            </h1>
            <p className="text-gray-600 mt-1">
              לקוח #{customer.id} • {customer.company || 'לא צוין'}
            </p>
          </div>
          <div className="flex space-x-3 space-x-reverse">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(customer.status)}`}>
              {customer.status === 'lead' && 'ליד'}
              {customer.status === 'prospect' && 'פרוספקט'}
              {customer.status === 'customer' && 'לקוח'}
              {customer.status === 'inactive' && 'לא פעיל'}
            </span>
            {isEditing ? (
              <div className="flex space-x-2 space-x-reverse">
                <button
                  onClick={updateCustomer}
                  className="bg-green-600 text-white px-3 py-1 rounded-md hover:bg-green-700 flex items-center"
                >
                  <Save className="w-4 h-4 ml-1" />
                  שמור
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setEditData(customer);
                  }}
                  className="bg-gray-300 text-gray-700 px-3 py-1 rounded-md hover:bg-gray-400 flex items-center"
                >
                  <X className="w-4 h-4 ml-1" />
                  ביטול
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsEditing(true)}
                className="bg-blue-600 text-white px-3 py-1 rounded-md hover:bg-blue-700 flex items-center"
              >
                <Edit className="w-4 h-4 ml-1" />
                ערוך
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Customer Info */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              פרטי לקוח
            </h3>
            
            <div className="space-y-4">
              <div className="flex items-center">
                <User className="w-5 h-5 text-gray-400 ml-3" />
                {isEditing ? (
                  <div className="flex space-x-2 space-x-reverse flex-1">
                    <input
                      type="text"
                      value={editData.first_name || ''}
                      onChange={(e) => setEditData({...editData, first_name: e.target.value})}
                      className="border border-gray-300 rounded-md px-2 py-1 flex-1"
                      placeholder="שם פרטי"
                    />
                    <input
                      type="text"
                      value={editData.last_name || ''}
                      onChange={(e) => setEditData({...editData, last_name: e.target.value})}
                      className="border border-gray-300 rounded-md px-2 py-1 flex-1"
                      placeholder="שם משפחה"
                    />
                  </div>
                ) : (
                  <span className="text-gray-900">{customer.first_name} {customer.last_name}</span>
                )}
              </div>

              <div className="flex items-center">
                <Phone className="w-5 h-5 text-gray-400 ml-3" />
                {isEditing ? (
                  <input
                    type="tel"
                    value={editData.phone_number || ''}
                    onChange={(e) => setEditData({...editData, phone_number: e.target.value})}
                    className="border border-gray-300 rounded-md px-2 py-1 flex-1"
                    placeholder="מספר טלפון"
                  />
                ) : (
                  <span className="text-gray-900">{customer.phone_number}</span>
                )}
              </div>

              {(customer.email || isEditing) && (
                <div className="flex items-center">
                  <Mail className="w-5 h-5 text-gray-400 ml-3" />
                  {isEditing ? (
                    <input
                      type="email"
                      value={editData.email || ''}
                      onChange={(e) => setEditData({...editData, email: e.target.value})}
                      className="border border-gray-300 rounded-md px-2 py-1 flex-1"
                      placeholder="כתובת אימייל"
                    />
                  ) : (
                    <span className="text-gray-900">{customer.email}</span>
                  )}
                </div>
              )}

              {(customer.company || isEditing) && (
                <div className="flex items-center">
                  <Building className="w-5 h-5 text-gray-400 ml-3" />
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.company || ''}
                      onChange={(e) => setEditData({...editData, company: e.target.value})}
                      className="border border-gray-300 rounded-md px-2 py-1 flex-1"
                      placeholder="חברה"
                    />
                  ) : (
                    <span className="text-gray-900">{customer.company}</span>
                  )}
                </div>
              )}

              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-gray-400 ml-3" />
                <span className="text-gray-900">
                  נוצר: {new Date(customer.created_at).toLocaleDateString('he-IL')}
                </span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="mt-6 grid grid-cols-2 gap-3">
              <button className="flex items-center justify-center p-2 border border-blue-300 text-blue-600 rounded-md hover:bg-blue-50">
                <Phone className="w-4 h-4 ml-1" />
                התקשר
              </button>
              <button className="flex items-center justify-center p-2 border border-green-300 text-green-600 rounded-md hover:bg-green-50">
                <MessageCircle className="w-4 h-4 ml-1" />
                וואטסאפ
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Tabs */}
          <div className="bg-white rounded-lg shadow">
            <div className="border-b border-gray-200">
              <nav className="flex space-x-8 space-x-reverse px-6">
                {[
                  { id: 'overview', label: 'סקירה כללית', icon: Activity },
                  { id: 'interactions', label: 'אינטראקציות', icon: MessageCircle },
                  { id: 'tasks', label: 'משימות', icon: CheckCircle },
                ].map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center py-4 px-1 border-b-2 font-medium text-sm ${
                        activeTab === tab.id
                          ? 'border-blue-500 text-blue-600'
                          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                      }`}
                    >
                      <Icon className="w-4 h-4 ml-2" />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            </div>

            <div className="p-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <Phone className="w-5 h-5 text-blue-600 ml-2" />
                        <span className="text-sm font-medium text-blue-900">שיחות</span>
                      </div>
                      <p className="text-2xl font-bold text-blue-900 mt-1">
                        {interactions.filter(i => i.interaction_type === 'call').length}
                      </p>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <MessageCircle className="w-5 h-5 text-green-600 ml-2" />
                        <span className="text-sm font-medium text-green-900">הודעות</span>
                      </div>
                      <p className="text-2xl font-bold text-green-900 mt-1">
                        {interactions.filter(i => i.interaction_type === 'whatsapp').length}
                      </p>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="flex items-center">
                        <CheckCircle className="w-5 h-5 text-purple-600 ml-2" />
                        <span className="text-sm font-medium text-purple-900">משימות</span>
                      </div>
                      <p className="text-2xl font-bold text-purple-900 mt-1">
                        {tasks.length}
                      </p>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-lg font-medium text-gray-900 mb-3">פעילות אחרונה</h4>
                    <div className="space-y-3">
                      {interactions.slice(0, 5).map((interaction, index) => (
                        <div key={index} className="flex items-start space-x-3 space-x-reverse">
                          <div className="flex-shrink-0">
                            {getInteractionIcon(interaction.interaction_type)}
                          </div>
                          <div className="flex-1">
                            <p className="text-sm text-gray-900">
                              {interaction.content || 'אינטראקציה ללא תוכן'}
                            </p>
                            <p className="text-xs text-gray-500">
                              {new Date(interaction.interaction_date).toLocaleString('he-IL')}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'interactions' && (
                <div className="space-y-4">
                  {interactions.map((interaction, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-3 space-x-reverse">
                          <div className="flex-shrink-0">
                            {getInteractionIcon(interaction.interaction_type)}
                          </div>
                          <div className="flex-1">
                            <h4 className="text-sm font-medium text-gray-900">
                              {interaction.interaction_type === 'call' && 'שיחה טלפונית'}
                              {interaction.interaction_type === 'whatsapp' && 'הודעת וואטסאפ'}
                              {interaction.interaction_type === 'email' && 'אימייל'}
                            </h4>
                            <p className="text-sm text-gray-600 mt-1">
                              {interaction.content}
                            </p>
                            {interaction.ai_response && (
                              <div className="mt-2 p-2 bg-blue-50 rounded border-r-4 border-blue-500">
                                <p className="text-sm text-blue-900">
                                  <strong>תגובת AI:</strong> {interaction.ai_response}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">
                          {new Date(interaction.interaction_date).toLocaleString('he-IL')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'tasks' && (
                <div className="space-y-4">
                  {/* Add New Task */}
                  <div className="flex space-x-3 space-x-reverse">
                    <input
                      type="text"
                      value={newTask}
                      onChange={(e) => setNewTask(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && addTask()}
                      placeholder="הוסף משימה חדשה..."
                      className="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <button
                      onClick={addTask}
                      className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center"
                    >
                      <Plus className="w-4 h-4 ml-1" />
                      הוסף
                    </button>
                  </div>

                  {/* Tasks List */}
                  <div className="space-y-3">
                    {tasks.map((task) => (
                      <div key={task.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                        <div className="flex items-center space-x-3 space-x-reverse">
                          <button
                            onClick={() => completeTask(task.id)}
                            className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                              task.status === 'completed'
                                ? 'bg-green-500 border-green-500 text-white'
                                : 'border-gray-300 hover:border-green-500'
                            }`}
                          >
                            {task.status === 'completed' && <CheckCircle className="w-3 h-3" />}
                          </button>
                          <span className={`text-sm ${
                            task.status === 'completed' ? 'text-gray-500 line-through' : 'text-gray-900'
                          }`}>
                            {task.title}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 space-x-reverse text-xs text-gray-500">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(task.created_at).toLocaleDateString('he-IL')}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CustomerPage;