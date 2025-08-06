/**
 * AgentLocator Dashboard Component - React frontend consuming Flask APIs
 * דשבורד AgentLocator עם React הצורך APIs של Flask
 */
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Users,
  Phone,
  MessageSquare,
  FileSignature,
  FileText,
  Receipt,
  TrendingUp,
  CheckCircle,
  Clock,
  AlertCircle
} from 'lucide-react';

const AgentLocatorDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  // State for different data types
  const [customers, setCustomers] = useState([]);
  const [signatures, setSignatures] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [conversations, setConversations] = useState([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      // Fetch all data in parallel
      await Promise.all([
        fetchStats(),
        fetchCustomers(),
        fetchSignatures(),
        fetchProposals(),
        fetchInvoices(),
        fetchConversations()
      ]);

    } catch (err) {
      console.error('Dashboard data fetch error:', err);
      setError('שגיאה בטעינת נתוני הדשבורד');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      console.log('🔄 AgentLocator: Fetching stats from /api/stats/overview...');
      const response = await fetch('/api/stats/overview');
      console.log('📡 AgentLocator: Stats response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('📊 AgentLocator: Stats data received:', data);
        setStats(data.stats || null);
      } else {
        console.error('❌ AgentLocator: Stats API failed:', response.status);
      }
    } catch (err) {
      console.error('❌ AgentLocator: Stats fetch error:', err);
    }
  };

  const fetchCustomers = async () => {
    try {
      console.log('🔄 AgentLocator: Fetching customers from /api/crm/customers...');
      const response = await fetch('/api/crm/customers');
      console.log('📡 AgentLocator: Customers response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('👥 AgentLocator: Customers data received:', data);
        setCustomers(Array.isArray(data.customers) ? data.customers : []);
      } else {
        console.error('❌ AgentLocator: Customers API failed:', response.status);
        setCustomers([]);
      }
    } catch (err) {
      console.error('❌ AgentLocator: Customers fetch error:', err);
      setCustomers([]);
    }
  };

  const fetchSignatures = async () => {
    try {
      const response = await fetch('/api/signature/signatures');
      if (response.ok) {
        const data = await response.json();
        console.log('Signatures data:', data);
        setSignatures(Array.isArray(data.signatures) ? data.signatures : []);
      }
    } catch (err) {
      console.error('Error fetching signatures:', err);
      setSignatures([]);
    }
  };

  const fetchProposals = async () => {
    try {
      const response = await fetch('/api/proposal/proposals');
      if (response.ok) {
        const data = await response.json();
        console.log('Proposals data:', data);
        setProposals(Array.isArray(data.proposals) ? data.proposals : []);
      }
    } catch (err) {
      console.error('Error fetching proposals:', err);
      setProposals([]);
    }
  };

  const fetchInvoices = async () => {
    try {
      const response = await fetch('/api/invoice/invoices');
      if (response.ok) {
        const data = await response.json();
        console.log('Invoices data:', data);
        setInvoices(Array.isArray(data.invoices) ? data.invoices : []);
      }
    } catch (err) {
      console.error('Error fetching invoices:', err);
      setInvoices([]);
    }
  };

  const fetchConversations = async () => {
    try {
      const response = await fetch('/api/whatsapp/conversations');
      if (response.ok) {
        const data = await response.json();
        console.log('Conversations data:', data);
        setConversations(Array.isArray(data.conversations) ? data.conversations : []);
      }
    } catch (err) {
      console.error('Error fetching conversations:', err);
      setConversations([]);
    }
  };

  const StatCard = ({ title, value, icon: Icon, status, trend }) => (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-600">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-blue-900">{value}</div>
        {status && (
          <Badge variant={status === 'success' ? 'default' : 'secondary'} className="mt-2">
            {status === 'success' ? 'פעיל' : 'ממתין'}
          </Badge>
        )}
        {trend && (
          <p className="text-xs text-muted-foreground mt-1">
            {trend > 0 ? `↗️ +${trend}%` : `↘️ ${trend}%`} מהחודש שעבר
          </p>
        )}
      </CardContent>
    </Card>
  );

  const DataTable = ({ title, data, columns, emptyMessage }) => {
    // תיקון חיוני - וידוא שdata תמיד מערך
    const safeData = Array.isArray(data) ? data : [];
    
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          {safeData.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    {columns.map((col, index) => (
                      <th key={index} className="text-right p-2 font-medium">
                        {col.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {safeData.slice(0, 5).map((item, index) => (
                    <tr key={index} className="border-b hover:bg-gray-50">
                      {columns.map((col, colIndex) => (
                        <td key={colIndex} className="p-2 text-right">
                          {col.render ? col.render(item) : (item[col.key] || '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              {emptyMessage}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">טוען נתוני דשבורד...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="max-w-md">
          <CardContent className="pt-6">
            <div className="text-center">
              <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">שגיאה בטעינת הדשבורד</h3>
              <p className="text-gray-600 mb-4">{error}</p>
              <Button onClick={fetchDashboardData}>נסה שוב</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            דשבורד AgentLocator
          </h1>
          <p className="text-gray-600">
            מערכת ניהול לקוחות מקיפה עם בינה מלאכותית
          </p>
        </div>

        {/* Overview Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {stats.customers && (
              <StatCard
                title="לקוחות"
                value={stats.customers.total || 0}
                icon={Users}
                trend={12}
              />
            )}
            {stats.calls && (
              <StatCard
                title="שיחות היום"
                value={stats.calls.today || 0}
                icon={Phone}
                trend={8}
              />
            )}
            {stats.whatsapp && (
              <StatCard
                title="שיחות WhatsApp פעילות"
                value={stats.whatsapp.active || 0}
                icon={MessageSquare}
                trend={15}
              />
            )}
            {stats.tasks && (
              <StatCard
                title="משימות פתוחות"
                value={stats.tasks.pending || 0}
                icon={CheckCircle}
                trend={-5}
              />
            )}
          </div>
        )}

        {/* Tabs for different sections */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">סקירה</TabsTrigger>
            <TabsTrigger value="customers">לקוחות</TabsTrigger>
            <TabsTrigger value="signatures">חתימות</TabsTrigger>
            <TabsTrigger value="proposals">הצעות</TabsTrigger>
            <TabsTrigger value="invoices">חשבוניות</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Activity */}
              <Card>
                <CardHeader>
                  <CardTitle>פעילות אחרונה</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center space-x-3 rtl:space-x-reverse">
                      <Phone className="h-4 w-4 text-blue-500" />
                      <span className="text-sm">שיחה חדשה התקבלה</span>
                      <span className="text-xs text-gray-500">לפני 5 דקות</span>
                    </div>
                    <div className="flex items-center space-x-3 rtl:space-x-reverse">
                      <FileSignature className="h-4 w-4 text-green-500" />
                      <span className="text-sm">חוזה נחתם</span>
                      <span className="text-xs text-gray-500">לפני 15 דקות</span>
                    </div>
                    <div className="flex items-center space-x-3 rtl:space-x-reverse">
                      <Receipt className="h-4 w-4 text-orange-500" />
                      <span className="text-sm">חשבונית נוצרה</span>
                      <span className="text-xs text-gray-500">לפני שעה</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Financial Summary */}
              {stats?.financial && (
                <Card>
                  <CardHeader>
                    <CardTitle>סיכום כספי</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span>חשבוניות ששולמו:</span>
                        <span className="font-bold text-green-600">
                          ₪{stats.financial.invoices.paid_amount.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>ממתין לתשלום:</span>
                        <span className="font-bold text-orange-600">
                          ₪{stats.financial.invoices.pending_amount.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>ערך הצעות מחיר:</span>
                        <span className="font-bold text-blue-600">
                          ₪{stats.financial.proposals.total_value.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>

          <TabsContent value="customers" className="mt-6">
            <DataTable
              title="לקוחות אחרונים"
              data={customers}
              columns={[
                { header: 'שם', key: 'name' },
                { header: 'טלפון', key: 'phone' },
                { header: 'סטטוס', key: 'status', render: (item) => (
                  <Badge variant={item.status === 'active' ? 'default' : 'secondary'}>
                    {item.status === 'active' ? 'פעיל' : 'לא פעיל'}
                  </Badge>
                )},
                { header: 'מקור', key: 'source' }
              ]}
              emptyMessage="אין לקוחות להצגה"
            />
          </TabsContent>

          <TabsContent value="signatures" className="mt-6">
            <DataTable
              title="חתימות דיגיטליות אחרונות"
              data={signatures}
              columns={[
                { header: 'מסמך', key: 'document_name' },
                { header: 'חותם', key: 'signer_name' },
                { header: 'סטטוס', key: 'status', render: (item) => (
                  <Badge variant={item.status === 'signed' ? 'default' : 'secondary'}>
                    {item.status === 'signed' ? 'נחתם' : 'ממתין'}
                  </Badge>
                )},
                { header: 'תאריך', key: 'created_at', render: (item) => 
                  new Date(item.created_at).toLocaleDateString('he-IL')
                }
              ]}
              emptyMessage="אין חתימות להצגה"
            />
          </TabsContent>

          <TabsContent value="proposals" className="mt-6">
            <DataTable
              title="הצעות מחיר אחרונות"
              data={proposals}
              columns={[
                { header: 'כותרת', key: 'title' },
                { header: 'לקוח', key: 'customer_name' },
                { header: 'סכום', key: 'amount', render: (item) => 
                  `₪${item.amount.toLocaleString()}`
                },
                { header: 'סטטוס', key: 'status', render: (item) => (
                  <Badge variant={item.status === 'accepted' ? 'default' : 'secondary'}>
                    {item.status === 'accepted' ? 'אושר' : 'ממתין'}
                  </Badge>
                )}
              ]}
              emptyMessage="אין הצעות מחיר להצגה"
            />
          </TabsContent>

          <TabsContent value="invoices" className="mt-6">
            <DataTable
              title="חשבוניות אחרונות"
              data={invoices}
              columns={[
                { header: 'מספר', key: 'invoice_number' },
                { header: 'לקוח', key: 'customer_name' },
                { header: 'סכום', key: 'amount', render: (item) => 
                  `₪${item.amount.toLocaleString()}`
                },
                { header: 'סטטוס', key: 'status', render: (item) => (
                  <Badge variant={item.status === 'paid' ? 'default' : 'secondary'}>
                    {item.status === 'paid' ? 'שולם' : 'ממתין'}
                  </Badge>
                )}
              ]}
              emptyMessage="אין חשבוניות להצגה"
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AgentLocatorDashboard;