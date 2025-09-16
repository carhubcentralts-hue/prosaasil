import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Shield, Settings, Eye, Edit, Trash2, Mail, Phone } from 'lucide-react';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: any) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
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
    admin: "bg-red-100 text-red-800",
    manager: "bg-purple-100 text-purple-800",
    business: "bg-blue-100 text-blue-800",
    agent: "bg-green-100 text-green-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// User interface
interface SystemUser {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'manager' | 'business_owner' | 'business_agent' | 'read_only';
  business_id?: string;
  business_name?: string;
  status: 'active' | 'inactive' | 'pending';
  last_login?: string;
  created_at: string;
  phone?: string;
  permissions: string[];
}

export function UsersPage() {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showUserModal, setShowUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<SystemUser | null>(null);
  const [showImpersonateModal, setShowImpersonateModal] = useState(false);

  useEffect(() => {
    loadUsers();
  }, [searchQuery, roleFilter, statusFilter]);

  const loadUsers = async () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      const mockUsers: SystemUser[] = [
        {
          id: '1',
          email: 'admin@shai-realestate.co.il',
          name: 'מנהל מערכת',
          role: 'admin',
          status: 'active',
          last_login: '2025-09-16T10:30:00Z',
          created_at: '2025-01-01T00:00:00Z',
          phone: '+972-50-1234567',
          permissions: ['all']
        },
        {
          id: '2',
          email: 'manager@shai-realestate.co.il',
          name: 'שרה לוי - מנהלת',
          role: 'manager',
          business_id: '1',
          business_name: 'שי דירות ומשרדים בע״מ',
          status: 'active',
          last_login: '2025-09-16T09:15:00Z',
          created_at: '2025-02-15T00:00:00Z',
          phone: '+972-52-9876543',
          permissions: ['business_management', 'user_management', 'reports']
        },
        {
          id: '3',
          email: 'owner@shai-realestate.co.il',
          name: 'שי כהן - בעלים',
          role: 'business_owner',
          business_id: '1',
          business_name: 'שי דירות ומשרדים בע״מ',
          status: 'active',
          last_login: '2025-09-15T16:45:00Z',
          created_at: '2025-01-15T00:00:00Z',
          phone: '+972-54-1122334',
          permissions: ['business_full_access', 'settings', 'billing']
        },
        {
          id: '4',
          email: 'agent1@shai-realestate.co.il',
          name: 'דני גולן - סוכן',
          role: 'business_agent',
          business_id: '1',
          business_name: 'שי דירות ומשרדים בע״מ',
          status: 'active',
          last_login: '2025-09-16T08:30:00Z',
          created_at: '2025-03-01T00:00:00Z',
          phone: '+972-55-6677889',
          permissions: ['leads_access', 'calls_access', 'basic_crm']
        },
        {
          id: '5',
          email: 'temp@example.com',
          name: 'משתמש זמני',
          role: 'read_only',
          business_id: '1',
          business_name: 'שי דירות ומשרדים בע״מ',
          status: 'pending',
          created_at: '2025-09-14T00:00:00Z',
          permissions: ['read_only']
        }
      ];
      
      setUsers(mockUsers);
      setLoading(false);
    }, 500);
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'admin';
      case 'manager': return 'manager';
      case 'business_owner': return 'business';
      case 'business_agent': return 'agent';
      case 'read_only': return 'default';
      default: return 'default';
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'admin': return 'מנהל מערכת';
      case 'manager': return 'מנהל עסק';
      case 'business_owner': return 'בעל עסק';
      case 'business_agent': return 'סוכן';
      case 'read_only': return 'צפייה בלבד';
      default: return role;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'inactive': return 'default';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'inactive': return 'לא פעיל';
      case 'pending': return 'ממתין';
      default: return status;
    }
  };

  const handleImpersonate = (user: SystemUser) => {
    setSelectedUser(user);
    setShowImpersonateModal(true);
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = searchQuery === '' || 
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.business_name?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || user.status === statusFilter;
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  // Stats calculations
  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.status === 'active').length;
  const pendingUsers = users.filter(u => u.status === 'pending').length;
  const adminUsers = users.filter(u => u.role === 'admin').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען משתמשים...</p>
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
            <Users className="w-6 h-6 text-indigo-600" />
            <h1 className="text-2xl font-bold text-gray-900">ניהול משתמשים</h1>
            <Badge>{totalUsers} משתמשים</Badge>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <Shield className="w-4 h-4 mr-2" />
              הרשאות
            </Button>
            <Button onClick={() => setShowUserModal(true)}>
              <UserPlus className="w-4 h-4 mr-2" />
              משתמש חדש
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-full">
                <Users className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">סה״כ משתמשים</p>
                <p className="text-lg font-semibold text-gray-900">{totalUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-full">
                <Users className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">פעילים</p>
                <p className="text-lg font-semibold text-gray-900">{activeUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-full">
                <Users className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">ממתינים</p>
                <p className="text-lg font-semibold text-gray-900">{pendingUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-full">
                <Shield className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">מנהלים</p>
                <p className="text-lg font-semibold text-gray-900">{adminUsers}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="חיפוש לפי שם, אימייל, עסק..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex gap-3">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל התפקידים</option>
              <option value="admin">מנהל מערכת</option>
              <option value="manager">מנהל עסק</option>
              <option value="business_owner">בעל עסק</option>
              <option value="business_agent">סוכן</option>
              <option value="read_only">צפייה בלבד</option>
            </select>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="active">פעיל</option>
              <option value="inactive">לא פעיל</option>
              <option value="pending">ממתין</option>
            </select>
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="flex-1 overflow-hidden">
        <Card className="h-full m-6">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    משתמש
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    עסק
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    תפקיד
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    כניסה אחרונה
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                            <span className="text-sm font-medium text-gray-700">
                              {user.name.charAt(0)}
                            </span>
                          </div>
                        </div>
                        <div className="mr-4">
                          <div className="text-sm font-medium text-gray-900">{user.name}</div>
                          <div className="text-sm text-gray-500 flex items-center gap-2">
                            <Mail className="w-3 h-3" />
                            {user.email}
                          </div>
                          {user.phone && (
                            <div className="text-sm text-gray-500 flex items-center gap-2" dir="ltr">
                              <Phone className="w-3 h-3" />
                              {user.phone}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.business_name || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getRoleColor(user.role)}>
                        {getRoleLabel(user.role)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getStatusColor(user.status)}>
                        {getStatusLabel(user.status)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.last_login 
                        ? new Date(user.last_login).toLocaleString('he-IL')
                        : 'לא התחבר'
                      }
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleImpersonate(user)}
                          title="התחזות"
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" title="עריכה">
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" title="הגדרות">
                          <Settings className="w-4 h-4" />
                        </Button>
                        {user.role !== 'admin' && (
                          <Button variant="ghost" size="sm" title="מחיקה">
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {filteredUsers.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">אין משתמשים</h3>
              <p className="text-gray-500">אין משתמשים שמתאימים לחיפוש</p>
            </div>
          )}
        </Card>
      </div>

      {/* Impersonation Modal */}
      {showImpersonateModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              התחזות למשתמש
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              האם אתה בטוח שברצונך להתחזות למשתמש <strong>{selectedUser.name}</strong>?
              פעולה זו תעביר אותך לממשק שלו.
            </p>
            <div className="flex gap-3">
              <Button 
                onClick={() => {
                  // TODO: Implement impersonation logic
                  alert(`התחזות ל-${selectedUser.name}`);
                  setShowImpersonateModal(false);
                }}
              >
                אישור
              </Button>
              <Button 
                variant="outline"
                onClick={() => setShowImpersonateModal(false)}
              >
                ביטול
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}