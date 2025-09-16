import React, { useState, useEffect } from 'react';
import { CreditCard, FileText, Download, Eye, Plus, DollarSign, Calendar, AlertCircle, Clock } from 'lucide-react';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  [key: string]: any;
}) => {
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

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "success" | "warning" | "destructive" | "secondary";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800",
    destructive: "bg-red-100 text-red-800",
    secondary: "bg-blue-100 text-blue-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

// Data interfaces
interface Payment {
  id: string;
  amount: number;
  status: 'paid' | 'pending' | 'overdue' | 'cancelled';
  description: string;
  client_name: string;
  due_date: string;
  paid_date?: string;
  invoice_number: string;
  payment_method?: string;
}

interface Contract {
  id: string;
  title: string;
  client_name: string;
  property_address: string;
  contract_type: 'sale' | 'rent' | 'management';
  value: number;
  status: 'draft' | 'active' | 'completed' | 'cancelled';
  start_date: string;
  end_date?: string;
  commission_rate: number;
}

export function BillingPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'payments' | 'contracts'>('payments');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showContractModal, setShowContractModal] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    // Simulate API calls
    setTimeout(() => {
      const mockPayments: Payment[] = [
        {
          id: '1',
          amount: 25000,
          status: 'paid',
          description: 'עמלת מכירה - דירת 4 חדרים',
          client_name: 'יוסי כהן',
          due_date: '2025-09-10',
          paid_date: '2025-09-08',
          invoice_number: 'INV-2025-001',
          payment_method: 'העברה בנקאית'
        },
        {
          id: '2',
          amount: 15000,
          status: 'pending',
          description: 'עמלת השכרה - דירת 3 חדרים',
          client_name: 'רחל לוי',
          due_date: '2025-09-20',
          invoice_number: 'INV-2025-002'
        },
        {
          id: '3',
          amount: 30000,
          status: 'overdue',
          description: 'עמלת מכירה - בית פרטי',
          client_name: 'מיכאל שמואל',
          due_date: '2025-09-05',
          invoice_number: 'INV-2025-003'
        },
        {
          id: '4',
          amount: 8000,
          status: 'pending',
          description: 'ניהול נכסים - שכירות חודשית',
          client_name: 'שרה דוד',
          due_date: '2025-09-25',
          invoice_number: 'INV-2025-004'
        }
      ];

      const mockContracts: Contract[] = [
        {
          id: '1',
          title: 'חוזה מכירה - רחוב הרצל 15',
          client_name: 'יוסי כהן',
          property_address: 'רחוב הרצל 15, תל אביב',
          contract_type: 'sale',
          value: 2500000,
          status: 'completed',
          start_date: '2025-08-01',
          end_date: '2025-09-01',
          commission_rate: 2.5
        },
        {
          id: '2',
          title: 'חוזה השכרה - רחוב דיזנגוף 45',
          client_name: 'רחל לוי',
          property_address: 'רחוב דיזנגוף 45, תל אביב',
          contract_type: 'rent',
          value: 8000,
          status: 'active',
          start_date: '2025-09-01',
          end_date: '2026-09-01',
          commission_rate: 1.0
        },
        {
          id: '3',
          title: 'חוזה ניהול - רחוב אלנבי 20',
          client_name: 'מיכאל שמואל',
          property_address: 'רחוב אלנבי 20, תל אביב',
          contract_type: 'management',
          value: 12000,
          status: 'draft',
          start_date: '2025-10-01',
          commission_rate: 8.0
        }
      ];

      setPayments(mockPayments);
      setContracts(mockContracts);
      setLoading(false);
    }, 500);
  };

  const getPaymentStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'success';
      case 'pending': return 'warning';
      case 'overdue': return 'destructive';
      case 'cancelled': return 'secondary';
      default: return 'default';
    }
  };

  const getPaymentStatusLabel = (status: string) => {
    switch (status) {
      case 'paid': return 'שולם';
      case 'pending': return 'ממתין';
      case 'overdue': return 'איחור';
      case 'cancelled': return 'בוטל';
      default: return status;
    }
  };

  const getContractStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'draft': return 'warning';
      case 'completed': return 'secondary';
      case 'cancelled': return 'destructive';
      default: return 'default';
    }
  };

  const getContractStatusLabel = (status: string) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'draft': return 'טיוטה';
      case 'completed': return 'הושלם';
      case 'cancelled': return 'בוטל';
      default: return status;
    }
  };

  const getContractTypeLabel = (type: string) => {
    switch (type) {
      case 'sale': return 'מכירה';
      case 'rent': return 'השכרה';
      case 'management': return 'ניהול';
      default: return type;
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS'
    }).format(amount);
  };

  // Calculate summary stats
  const totalRevenue = payments.filter(p => p.status === 'paid').reduce((sum, p) => sum + p.amount, 0);
  const pendingPayments = payments.filter(p => p.status === 'pending').reduce((sum, p) => sum + p.amount, 0);
  const overduePayments = payments.filter(p => p.status === 'overdue').reduce((sum, p) => sum + p.amount, 0);
  const activeContracts = contracts.filter(c => c.status === 'active').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען נתוני חיוב...</p>
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
            <CreditCard className="w-6 h-6 text-green-600" />
            <h1 className="text-2xl font-bold text-gray-900">חיוב וחוזים</h1>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              ייצא נתונים
            </Button>
            <Button 
              onClick={() => activeTab === 'payments' ? setShowPaymentModal(true) : setShowContractModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              {activeTab === 'payments' ? 'חיוב חדש' : 'חוזה חדש'}
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-full">
                <DollarSign className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">סה״כ הכנסות</p>
                <p className="text-lg font-semibold text-gray-900">{formatCurrency(totalRevenue)}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-full">
                <Clock className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">תשלומים ממתינים</p>
                <p className="text-lg font-semibold text-gray-900">{formatCurrency(pendingPayments)}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertCircle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">איחורים</p>
                <p className="text-lg font-semibold text-gray-900">{formatCurrency(overduePayments)}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-full">
                <FileText className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">חוזים פעילים</p>
                <p className="text-lg font-semibold text-gray-900">{activeContracts}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex space-x-8" dir="ltr">
          <button
            onClick={() => setActiveTab('payments')}
            className={`${
              activeTab === 'payments'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <CreditCard className="w-4 h-4 mr-2" />
            תשלומים ({payments.length})
          </button>
          <button
            onClick={() => setActiveTab('contracts')}
            className={`${
              activeTab === 'contracts'
                ? 'border-green-500 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <FileText className="w-4 h-4 mr-2" />
            חוזים ({contracts.length})
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-6">
        {activeTab === 'payments' ? (
          // Payments Table
          <Card className="h-full">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      חשבונית
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      לקוח
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      תיאור
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      סכום
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      תאריך יעד
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      סטטוס
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      פעולות
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {payments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {payment.invoice_number}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {payment.client_name}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                        {payment.description}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                        {formatCurrency(payment.amount)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {new Date(payment.due_date).toLocaleDateString('he-IL')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={getPaymentStatusColor(payment.status)}>
                          {getPaymentStatusLabel(payment.status)}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="sm">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Download className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {payments.length === 0 && (
              <div className="text-center py-12">
                <CreditCard className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">אין תשלומים</h3>
                <p className="text-gray-500">התחל בהוספת תשלומים לעסק שלך</p>
              </div>
            )}
          </Card>
        ) : (
          // Contracts Grid
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 overflow-y-auto">
            {contracts.map((contract) => (
              <Card key={contract.id} className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">{contract.title}</h3>
                    <p className="text-sm text-gray-600">{contract.client_name}</p>
                  </div>
                  <Badge variant={getContractStatusColor(contract.status)}>
                    {getContractStatusLabel(contract.status)}
                  </Badge>
                </div>
                
                <div className="space-y-3 mb-4">
                  <div>
                    <label className="text-xs font-medium text-gray-500">כתובת</label>
                    <p className="text-sm text-gray-900">{contract.property_address}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-gray-500">סוג</label>
                      <p className="text-sm text-gray-900">{getContractTypeLabel(contract.contract_type)}</p>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500">עמלה</label>
                      <p className="text-sm text-gray-900">{contract.commission_rate}%</p>
                    </div>
                  </div>
                  
                  <div>
                    <label className="text-xs font-medium text-gray-500">ערך</label>
                    <p className="text-sm font-semibold text-gray-900">{formatCurrency(contract.value)}</p>
                  </div>
                  
                  <div>
                    <label className="text-xs font-medium text-gray-500">תקופה</label>
                    <p className="text-sm text-gray-900">
                      {new Date(contract.start_date).toLocaleDateString('he-IL')}
                      {contract.end_date && ` - ${new Date(contract.end_date).toLocaleDateString('he-IL')}`}
                    </p>
                  </div>
                </div>
                
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1">
                    <Eye className="w-4 h-4 mr-2" />
                    הצג
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1">
                    <Download className="w-4 h-4 mr-2" />
                    הורד
                  </Button>
                </div>
              </Card>
            ))}
            
            {contracts.length === 0 && (
              <div className="col-span-full text-center py-12">
                <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">אין חוזים</h3>
                <p className="text-gray-500">התחל בהוספת חוזים לעסק שלך</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}