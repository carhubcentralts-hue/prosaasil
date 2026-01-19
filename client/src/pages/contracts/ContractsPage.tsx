import React, { useState, useEffect } from 'react';
import { FileText, Plus, Search, Filter, Download, Send, X, Calendar, User, Upload, Trash2 } from 'lucide-react';
import { formatDate } from '../../shared/utils/format';
import { Badge } from '../../shared/components/Badge';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { CreateContractModal } from './CreateContractModal';
import { ContractDetails } from './ContractDetails';
import { UploadContractModal } from './UploadContractModal';

interface Contract {
  id: number;
  title: string;
  status: 'draft' | 'sent' | 'signed' | 'cancelled';
  lead_id?: number;
  signer_name?: string;
  signer_phone?: string;
  signer_email?: string;
  signed_at?: string;
  created_at: string;
  updated_at?: string;
  file_count: number;
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'טיוטה',
  sent: 'נשלח',
  signed: 'חתום',
  cancelled: 'בוטל',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'gray',
  sent: 'blue',
  signed: 'green',
  cancelled: 'red',
};

export function ContractsPage() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedContractId, setSelectedContractId] = useState<number | null>(null);

  const perPage = 20;

  useEffect(() => {
    loadContracts();
  }, [searchQuery, statusFilter, page]);

  const loadContracts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      params.append('page', page.toString());
      params.append('per_page', perPage.toString());

      const response = await fetch(`/api/contracts?${params.toString()}`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to load contracts');

      const data = await response.json();
      setContracts(data.contracts || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error('Error loading contracts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleContractCreated = () => {
    setIsCreateModalOpen(false);
    loadContracts();
  };

  const handleContractUpdated = () => {
    loadContracts();
  };

  const handleDeleteContract = async (contractId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    
    // Find the contract to get its status
    const contract = contracts.find(c => c.id === contractId);
    const isSignedOrSent = contract && (contract.status === 'signed' || contract.status === 'sent');
    
    // Enhanced confirmation message for signed/sent contracts
    const confirmMessage = isSignedOrSent
      ? 'חוזה זה כבר נשלח או נחתם! האם אתה בטוח שברצונך למחוק אותו? פעולה זו אינה ניתנת לביטול.'
      : 'האם אתה בטוח שברצונך למחוק את החוזה? פעולה זו אינה ניתנת לביטול.';
    
    if (!confirm(confirmMessage)) return;

    try {
      const response = await fetch(`/api/contracts/${contractId}`, {
        method: 'DELETE',
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete contract');
      }

      loadContracts();
    } catch (error: any) {
      console.error('Error deleting contract:', error);
      alert(error.message || 'שגיאה במחיקת חוזה');
    }
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl" style={{ fontFamily: 'Assistant, sans-serif' }}>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        {/* Header */}
        <div className="mb-4 md:mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <FileText className="w-5 h-5 md:w-6 md:h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl md:text-2xl font-bold text-gray-900">חוזים</h1>
                <p className="text-xs md:text-sm text-gray-600">ניהול חוזים דיגיטליים וחתימות</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              {/* כפתור העלאת חוזה - בולט וברור */}
              <Button 
                onClick={() => setIsUploadModalOpen(true)} 
                className="flex items-center justify-center gap-2 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white shadow-lg w-full sm:w-auto"
              >
                <Upload className="w-4 h-4 md:w-5 md:h-5" />
                <span className="font-bold text-sm md:text-base">העלה חוזה</span>
              </Button>
              {/* כפתור יצירת חוזה רגיל */}
              <Button 
                onClick={() => setIsCreateModalOpen(true)} 
                variant="outline"
                className="flex items-center justify-center gap-2 w-full sm:w-auto"
              >
                <Plus className="w-4 h-4" />
                <span className="text-sm md:text-base">חוזה ריק</span>
              </Button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center bg-white p-3 md:p-4 rounded-lg shadow-sm">
            <div className="flex-1 min-w-0">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 md:w-5 md:h-5" />
                <Input
                  type="text"
                  placeholder="חיפוש לפי כותרת..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setPage(1);
                  }}
                  className="pr-10 text-sm md:text-base"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 md:w-5 md:h-5 text-gray-500" />
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-auto"
              >
                <option value="all">כל הסטטוסים</option>
                <option value="draft">טיוטה</option>
                <option value="sent">נשלח</option>
                <option value="signed">חתום</option>
                <option value="cancelled">בוטל</option>
              </select>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600 text-sm">טוען...</p>
            </div>
          ) : contracts.length === 0 ? (
            <div className="text-center py-12 px-4">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-600 text-sm md:text-base">לא נמצאו חוזים</p>
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('all');
                  }}
                  className="mt-2 text-blue-600 hover:text-blue-700 text-sm"
                >
                  נקה חיפוש
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Mobile Cards View */}
              <div className="block md:hidden divide-y divide-gray-200">
                {contracts.map((contract) => (
                  <div
                    key={contract.id}
                    className="p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedContractId(contract.id)}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="font-medium text-gray-900 truncate">{contract.title}</span>
                      </div>
                      <Badge color={STATUS_COLORS[contract.status] as any} className="flex-shrink-0 mr-2">
                        {STATUS_LABELS[contract.status]}
                      </Badge>
                    </div>
                    <div className="space-y-1 text-sm text-gray-600 mb-3">
                      {contract.signer_name && (
                        <div className="flex items-center gap-1">
                          <User className="w-3 h-3 text-gray-400" />
                          <span>{contract.signer_name}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <FileText className="w-3 h-3 text-gray-400" />
                        <span>{contract.file_count} קבצים</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-gray-400" />
                        <span>{formatDate(contract.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedContractId(contract.id);
                        }}
                        className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                      >
                        פרטים
                      </button>
                      <button
                        onClick={(e) => handleDeleteContract(contract.id, e)}
                        className="p-1 hover:bg-red-100 rounded text-red-600 transition"
                        title="מחק חוזה"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop Table View */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        כותרת
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        סטטוס
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        חותם
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        קבצים
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        תאריך יצירה
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        פעולות
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {contracts.map((contract) => (
                      <tr
                        key={contract.id}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => setSelectedContractId(contract.id)}
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-400" />
                            <span className="font-medium text-gray-900">{contract.title}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <Badge color={STATUS_COLORS[contract.status] as any}>
                            {STATUS_LABELS[contract.status]}
                          </Badge>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm">
                            {contract.signer_name ? (
                              <div className="flex items-center gap-1">
                                <User className="w-3 h-3 text-gray-400" />
                                <span className="text-gray-900">{contract.signer_name}</span>
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm text-gray-600">{contract.file_count} קבצים</span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-600">
                            <div className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(contract.created_at)}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedContractId(contract.id);
                              }}
                              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                            >
                              פרטים
                            </button>
                            <button
                              onClick={(e) => handleDeleteContract(contract.id, e)}
                              className="p-1 hover:bg-red-100 rounded text-red-600 transition"
                              title="מחק חוזה"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-4 md:px-6 py-3 md:py-4 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="text-xs md:text-sm text-gray-600">
                    מציג {(page - 1) * perPage + 1} - {Math.min(page * perPage, total)} מתוך {total}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                      הקודם
                    </button>
                    <span className="px-3 py-1 text-sm text-gray-600">
                      עמוד {page} מתוך {totalPages}
                    </span>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                      הבא
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modals */}
      {isCreateModalOpen && (
        <CreateContractModal onClose={() => setIsCreateModalOpen(false)} onSuccess={handleContractCreated} />
      )}

      {isUploadModalOpen && (
        <UploadContractModal onClose={() => setIsUploadModalOpen(false)} onSuccess={handleContractCreated} />
      )}

      {selectedContractId && (
        <ContractDetails
          contractId={selectedContractId}
          onClose={() => setSelectedContractId(null)}
          onUpdate={handleContractUpdated}
        />
      )}
    </div>
  );
}
