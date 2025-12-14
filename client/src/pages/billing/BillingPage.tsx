import React, { useState, useEffect } from 'react';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { CreditCard, FileText, Download, Eye, Plus, DollarSign, Calendar, AlertCircle, Clock, X, PenTool, MessageSquare } from 'lucide-react';
import { http } from '../../services/http';
import { SignatureCanvas } from '../../components/SignatureCanvas';

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
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
  const [signatureName, setSignatureName] = useState('');
  const [leads, setLeads] = useState<Array<{id: number; name: string; phone: string}>>([]);
  const [showWhatsAppModal, setShowWhatsAppModal] = useState(false);
  const [selectedItemType, setSelectedItemType] = useState<'invoice' | 'contract'>('invoice');
  const [selectedItemId, setSelectedItemId] = useState('');
  const [whatsappPhone, setWhatsappPhone] = useState('');
  
  // Form states
  const [paymentForm, setPaymentForm] = useState({
    lead_id: '',
    amount: '',
    description: '',
    client_name: '',
    payment_provider: ''
  });
  
  const [contractForm, setContractForm] = useState({
    lead_id: '',
    title: '',
    type: 'sale',
    custom_title: '',
    client_name: '',
    property_address: '',
    amount: 0
  });

  useEffect(() => {
    loadData();
    loadLeads();
  }, []);

  const loadLeads = async () => {
    try {
      const response = await http.get('/api/leads') as any;
      const leadsData = response?.items || response?.leads || [];
      setLeads(leadsData.map((lead: any) => ({
        id: lead.id,
        name: lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם',
        phone: lead.phone_e164 || lead.phone || ''
      })));
    } catch (error) {
      console.error('Error loading leads:', error);
      setLeads([]);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load invoices/receipts from the real API
      const receiptsResponse = await http.get('/api/receipts') as any;
      const invoices = receiptsResponse?.invoices || [];
      
      // Transform to match Payment interface
      const paymentsData = invoices.map((inv: any) => ({
        id: inv.id,
        amount: inv.total || inv.amount,
        status: inv.status === 'created' ? 'pending' : inv.status === 'paid' ? 'paid' : 'pending',
        description: inv.description || 'חשבונית',
        client_name: inv.customer_name || 'לקוח',
        due_date: inv.created_at,
        paid_date: inv.paid_at,
        invoice_number: inv.invoice_number,
        payment_method: 'ידני'
      }));
      
      setPayments(paymentsData);
      setContracts([]); // Contracts will be loaded separately when needed
    } catch (error) {
      console.error('Error loading billing data:', error);
      setPayments([]);
      setContracts([]);
    } finally {
      setLoading(false);
    }
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

  // Create new payment/receipt
  const handleCreatePayment = async () => {
    try {
      if (!paymentForm.amount || !paymentForm.description || !paymentForm.lead_id) {
        alert('נא למלא את כל השדות הנדרשים (כולל Lead ID)');
        return;
      }

      const response = await http.post('/api/receipts', {
        lead_id: parseInt(paymentForm.lead_id),
        amount: parseFloat(paymentForm.amount), // Send as float, backend converts
        description: paymentForm.description,
        customer_name: paymentForm.client_name || "לקוח"
      }) as any;

      if (response.success) {
        alert(`חשבונית ${response.invoice_number} נוצרה בהצלחה! סכום: ${response.total_with_tax} ₪ (כולל מע״מ)`);
        setShowPaymentModal(false);
        setPaymentForm({ lead_id: '', amount: '', description: '', client_name: '', payment_provider: '' });
        loadData(); // Reload the data
      } else {
        alert('שגיאה ביצירת החשבונית: ' + response.message);
      }
    } catch (error) {
      console.error('Error creating payment:', error);
      alert('שגיאה ביצירת החשבונית');
    }
  };

  // Create new contract
  const handleCreateContract = async () => {
    try {
      if (!contractForm.title || !contractForm.type || !contractForm.lead_id) {
        alert('נא למלא את כל השדות הנדרשים (כולל Lead ID)');
        return;
      }

      const response = await http.post('/api/contracts', {
        lead_id: parseInt(contractForm.lead_id),
        type: contractForm.type,
        title: contractForm.title || contractForm.custom_title
      }) as any;

      if (response.success) {
        alert(`חוזה נוצר בהצלחה! מספר: ${response.contract_id}`);
        setShowContractModal(false);
        setContractForm({ lead_id: '', title: '', type: 'sale', custom_title: '', client_name: '', property_address: '', amount: 0 });
        loadData(); // Reload the data
      } else {
        alert('שגיאה ביצירת החוזה: ' + response.message);
      }
    } catch (error) {
      console.error('Error creating contract:', error);
      alert('שגיאה ביצירת החוזה');
    }
  };

  // Document viewing and downloading handlers
  const handleViewInvoice = async (paymentId: string) => {
    try {
      const payment = payments.find(p => p.id === paymentId);
      if (!payment) return;

      // Generate and open invoice PDF in new tab
      const response = await fetch(`/api/billing/invoice/${paymentId}/view`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        window.URL.revokeObjectURL(url);
      } else {
        alert('שגיאה בפתיחת החשבונית');
      }
    } catch (error) {
      console.error('Error viewing invoice:', error);
      alert('שגיאה בפתיחת החשבונית');
    }
  };

  const handleDownloadInvoice = async (paymentId: string) => {
    try {
      const payment = payments.find(p => p.id === paymentId);
      if (!payment) return;

      // Generate and download invoice PDF
      const response = await fetch(`/api/billing/invoice/${paymentId}/download`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `invoice-${payment.invoice_number}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        alert('שגיאה בהורדת החשבונית');
      }
    } catch (error) {
      console.error('Error downloading invoice:', error);
      alert('שגיאה בהורדת החשבונית');
    }
  };

  const handleViewContract = async (contractId: string) => {
    try {
      const contract = contracts.find(c => c.id === contractId);
      if (!contract) return;

      // Generate and open contract PDF in new tab
      const response = await fetch(`/api/billing/contract/${contractId}/view`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        window.URL.revokeObjectURL(url);
      } else {
        alert('שגיאה בפתיחת החוזה');
      }
    } catch (error) {
      console.error('Error viewing contract:', error);
      alert('שגיאה בפתיחת החוזה');
    }
  };

  const handleDownloadContract = async (contractId: string) => {
    try {
      const contract = contracts.find(c => c.id === contractId);
      if (!contract) return;

      // Generate and download contract PDF
      const response = await fetch(`/api/billing/contract/${contractId}/download`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `contract-${contract.title.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        alert('שגיאה בהורדת החוזה');
      }
    } catch (error) {
      console.error('Error downloading contract:', error);
      alert('שגיאה בהורדת החוזה');
    }
  };

  const handleOpenSignatureModal = (contract: Contract) => {
    setSelectedContract(contract);
    setSignatureName('');
    setShowSignatureModal(true);
  };

  const handleSignContract = async (signatureData: string) => {
    if (!selectedContract) return;
    
    if (!signatureName.trim()) {
      alert('אנא הזן שם מלא');
      return;
    }

    try {
      const response = await http.post(`/api/contracts/${selectedContract.id}/sign`, {
        signature_data: signatureData,
        signed_name: signatureName.trim()
      }) as any;

      if (response.success) {
        alert('החוזה נחתם בהצלחה! ✓');
        setShowSignatureModal(false);
        setSelectedContract(null);
        setSignatureName('');
        // Reload contracts to get updated data
        loadData();
      } else {
        alert(response.message || 'שגיאה בחתימה');
      }
    } catch (error) {
      console.error('Error signing contract:', error);
      alert('שגיאה בחתימת החוזה');
    }
  };

  const handleSendWhatsApp = async () => {
    if (!whatsappPhone.trim()) {
      alert('נא להזין מספר טלפון');
      return;
    }

    try {
      const message = selectedItemType === 'invoice' ? 'חשבונית נשלח' : 'חוזה נשלח';
      
      const response = await http.post('/api/whatsapp/send', {
        to: whatsappPhone,
        message: message,
        type: selectedItemType,
        id: selectedItemId
      }) as any;

      if (response.success || response.status === 'sent') {
        alert(`${message} בהצלחה ל-${whatsappPhone}`);
        setShowWhatsAppModal(false);
        setWhatsappPhone('');
      } else {
        alert('שגיאה בשליחת ההודעה: ' + (response.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error sending WhatsApp:', error);
      alert('שגיאה בשליחת הודעת WhatsApp');
    }
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
                        {formatDateOnly(payment.due_date)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant={getPaymentStatusColor(payment.status)}>
                          {getPaymentStatusLabel(payment.status)}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleViewInvoice(payment.id)}
                            title="צפייה בחשבונית"
                            data-testid={`button-view-invoice-${payment.id}`}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleDownloadInvoice(payment.id)}
                            title="הורדת חשבונית"
                            data-testid={`button-download-invoice-${payment.id}`}
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={() => {
                              setSelectedItemType('invoice');
                              setSelectedItemId(payment.id);
                              setShowWhatsAppModal(true);
                            }}
                            title="שלח ב-WhatsApp"
                            data-testid={`button-whatsapp-invoice-${payment.id}`}
                          >
                            <MessageSquare className="w-4 h-4" />
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
                      {formatDateOnly(contract.start_date)}
                      {contract.end_date && ` - ${formatDateOnly(contract.end_date)}`}
                    </p>
                  </div>
                </div>
                
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="flex-1"
                      onClick={() => handleViewContract(contract.id)}
                      title="צפייה בחוזה"
                      data-testid={`button-view-contract-${contract.id}`}
                    >
                      <Eye className="w-4 h-4 mr-2" />
                      הצג
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="flex-1"
                      onClick={() => handleDownloadContract(contract.id)}
                      title="הורדת חוזה"
                      data-testid={`button-download-contract-${contract.id}`}
                    >
                      <Download className="w-4 h-4 mr-2" />
                      הורד
                    </Button>
                    <Button 
                      size="sm" 
                      className="flex-1"
                      onClick={() => handleOpenSignatureModal(contract)}
                      title="חתימה דיגיטלית"
                      data-testid={`button-sign-contract-${contract.id}`}
                    >
                      <PenTool className="w-4 h-4 mr-2" />
                      חתום
                    </Button>
                  </div>
                  <Button 
                    variant="outline"
                    size="sm"
                    className="w-full bg-green-50 border-green-200 text-green-700 hover:bg-green-100"
                    onClick={() => {
                      setSelectedItemType('contract');
                      setSelectedItemId(contract.id);
                      setShowWhatsAppModal(true);
                    }}
                    title="שלח ב-WhatsApp"
                    data-testid={`button-whatsapp-contract-${contract.id}`}
                  >
                    <MessageSquare className="w-4 h-4 mr-2" />
                    שלח ב-WhatsApp
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

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md shadow-xl">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  חיוב חדש
                </h3>
                <button
                  onClick={() => setShowPaymentModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    בחר ליד <span className="text-red-500">*</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={paymentForm.lead_id}
                    onChange={(e) => {
                      const selectedLead = leads.find(l => l.id === parseInt(e.target.value));
                      setPaymentForm({
                        ...paymentForm, 
                        lead_id: e.target.value,
                        client_name: selectedLead?.name || ''
                      });
                    }}
                  >
                    <option value="">-- בחר ליד --</option>
                    {leads.map(lead => (
                      <option key={lead.id} value={lead.id}>
                        {lead.name} {lead.phone ? `(${lead.phone})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    סכום (₪) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="0.00"
                    min="0"
                    step="0.01"
                    value={paymentForm.amount}
                    onChange={(e) => setPaymentForm({...paymentForm, amount: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    תיאור <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="עמלת תיווך, שירותי ייעוץ..."
                    value={paymentForm.description}
                    onChange={(e) => setPaymentForm({...paymentForm, description: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שם לקוח (אופציונלי)
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="שם הלקוח"
                    value={paymentForm.client_name}
                    onChange={(e) => setPaymentForm({...paymentForm, client_name: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    שיטת תשלום
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      className="flex items-center justify-center p-4 border-2 border-blue-200 rounded-lg hover:border-blue-400 transition-colors"
                      onClick={() => {
                        setPaymentForm({...paymentForm, payment_provider: 'paypal'});
                        handleCreatePayment();
                      }}
                    >
                      <div className="text-center">
                        <div className="w-8 h-8 bg-blue-600 rounded mx-auto mb-2 flex items-center justify-center">
                          <CreditCard className="w-4 h-4 text-white" />
                        </div>
                        <span className="text-sm font-medium">PayPal</span>
                      </div>
                    </button>
                    
                    <button
                      className="flex items-center justify-center p-4 border-2 border-green-200 rounded-lg hover:border-green-400 transition-colors"
                      onClick={() => {
                        setPaymentForm({...paymentForm, payment_provider: 'tranzilla'});
                        handleCreatePayment();
                      }}
                    >
                      <div className="text-center">
                        <div className="w-8 h-8 bg-green-600 rounded mx-auto mb-2 flex items-center justify-center">
                          <CreditCard className="w-4 h-4 text-white" />
                        </div>
                        <span className="text-sm font-medium">Tranzilla</span>
                      </div>
                    </button>
                  </div>
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => setShowPaymentModal(false)}
                  >
                    ביטול
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={handleCreatePayment}
                  >
                    צור חיוב
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Contract Modal */}
      {showContractModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md shadow-xl">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  חוזה חדש
                </h3>
                <button
                  onClick={() => setShowContractModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    בחר ליד <span className="text-red-500">*</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={contractForm.lead_id}
                    onChange={(e) => {
                      const selectedLead = leads.find(l => l.id === parseInt(e.target.value));
                      setContractForm({
                        ...contractForm, 
                        lead_id: e.target.value,
                        client_name: selectedLead?.name || ''
                      });
                    }}
                  >
                    <option value="">-- בחר ליד --</option>
                    {leads.map(lead => (
                      <option key={lead.id} value={lead.id}>
                        {lead.name} {lead.phone ? `(${lead.phone})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    כותרת החוזה
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="חוזה מכירה - רחוב..."
                    value={contractForm.title}
                    onChange={(e) => setContractForm({...contractForm, title: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שם הלקוח (אופציונלי)
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="שם הלקוח"
                    value={contractForm.client_name}
                    onChange={(e) => setContractForm({...contractForm, client_name: e.target.value})}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    כתובת הנכס
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="רחוב, עיר"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      סוג חוזה
                    </label>
                    <select className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="sale">מכירה</option>
                      <option value="rent">השכרה</option>
                      <option value="management">ניהול</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      עמלה (%)
                    </label>
                    <input
                      type="number"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="2.5"
                      min="0"
                      max="100"
                      step="0.1"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    ערך הנכס (₪)
                  </label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="1000000"
                    min="0"
                  />
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => setShowContractModal(false)}
                  >
                    ביטול
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={handleCreateContract}
                  >
                    צור חוזה
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Signature Modal */}
      {showSignatureModal && selectedContract && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white rounded-lg w-full max-w-2xl shadow-xl">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  חתימה דיגיטלית על חוזה
                </h3>
                <button
                  onClick={() => setShowSignatureModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="button-close-signature-modal"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-1">{selectedContract.title}</h4>
                <p className="text-sm text-gray-600">{selectedContract.client_name}</p>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שם מלא של החותם *
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="הזן שם מלא"
                    value={signatureName}
                    onChange={(e) => setSignatureName(e.target.value)}
                    data-testid="input-signer-name"
                  />
                </div>

                <SignatureCanvas
                  onSave={handleSignContract}
                  onClear={() => console.log('Signature cleared')}
                  width={600}
                  height={200}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* WhatsApp Modal */}
      {showWhatsAppModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md shadow-xl">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  שליחה ב-WhatsApp
                </h3>
                <button
                  onClick={() => {
                    setShowWhatsAppModal(false);
                    setWhatsappPhone('');
                  }}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="button-close-whatsapp-modal"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare className="w-5 h-5 text-green-600" />
                    <span className="font-medium text-green-900">
                      {selectedItemType === 'invoice' ? 'שליחת חשבונית' : 'שליחת חוזה'}
                    </span>
                  </div>
                  <p className="text-sm text-green-700">
                    {selectedItemType === 'invoice' 
                      ? 'החשבונית תישלח ללקוח דרך WhatsApp'
                      : 'החוזה יישלח ללקוח דרך WhatsApp'}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    מספר טלפון <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="tel"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="972501234567"
                    value={whatsappPhone}
                    onChange={(e) => setWhatsappPhone(e.target.value)}
                    data-testid="input-whatsapp-phone"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    הזן מספר בפורמט בינלאומי (לדוגמה: 972501234567)
                  </p>
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => {
                      setShowWhatsAppModal(false);
                      setWhatsappPhone('');
                    }}
                    data-testid="button-cancel-whatsapp"
                  >
                    ביטול
                  </Button>
                  <Button
                    className="flex-1 bg-green-600 hover:bg-green-700"
                    onClick={handleSendWhatsApp}
                    data-testid="button-send-whatsapp"
                  >
                    <MessageSquare className="w-4 h-4 mr-2" />
                    שלח
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
