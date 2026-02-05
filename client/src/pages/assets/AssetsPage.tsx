/**
 * Assets Library Page (מאגר)
 * 
 * Displays business assets in a grid/card layout with:
 * - Search and filtering
 * - Mobile-optimized cards
 * - Asset detail drawer
 * - Media gallery management
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Package,
  Plus,
  Search,
  Filter,
  Image,
  MoreVertical,
  Edit,
  Archive,
  X,
  ChevronRight,
  Upload,
  Trash2,
  Star,
  Loader2,
  Bot
} from 'lucide-react';
import { cn } from '../../shared/utils/cn';

interface Asset {
  id: number;
  title: string;
  description: string | null;
  tags: string[];
  category: string | null;
  status: string;
  cover_attachment_id: number | null;
  cover_preview_url: string | null;
  media_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface AssetMedia {
  id: number;
  attachment_id: number;
  filename: string;
  mime_type: string;
  file_size: number;
  role: string;
  sort_order: number;
  signed_url: string;
  created_at: string | null;
}

interface AssetDetail extends Asset {
  custom_fields: Record<string, any> | null;
  media: AssetMedia[];
  created_by: number | null;
  updated_by: number | null;
}

interface AssetsListResponse {
  items: Asset[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  
  // AI Tools Toggle state
  const [assetsUseAi, setAssetsUseAi] = useState(true);
  const [savingAiToggle, setSavingAiToggle] = useState(false);
  
  // Detail drawer state
  const [selectedAsset, setSelectedAsset] = useState<AssetDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  
  // Create/edit modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState<AssetDetail | null>(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    tags: [] as string[],
    custom_fields: {} as Record<string, any>
  });
  const [saving, setSaving] = useState(false);
  
  // File upload state
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(false);

  // Fetch assets
  const fetchAssets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (categoryFilter) params.append('category', categoryFilter);
      if (statusFilter) params.append('status', statusFilter);
      params.append('page', String(page));
      params.append('page_size', '30');
      
      const response = await fetch(`/api/assets?${params}`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('אין לך הרשאה לצפות במאגר');
        }
        throw new Error('שגיאה בטעינת המאגר');
      }
      
      const data: AssetsListResponse = await response.json();
      setAssets(data.items);
      setTotalPages(data.pages);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה לא ידועה');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, categoryFilter, statusFilter, page]);

  // Fetch AI tools setting
  const fetchAiSetting = useCallback(async () => {
    try {
      const response = await fetch('/api/business/current', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setAssetsUseAi(data.assets_use_ai !== false); // Default to true if not set
      }
    } catch (err) {
      console.error('Error fetching AI setting:', err);
    }
  }, []);

  // Update AI tools setting
  const updateAiSetting = async (enabled: boolean) => {
    try {
      setSavingAiToggle(true);
      const response = await fetch('/api/business/current/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ assets_use_ai: enabled })
      });
      
      if (!response.ok) {
        throw new Error('שגיאה בשמירת ההגדרה');
      }
      
      setAssetsUseAi(enabled);
    } catch (err) {
      console.error('Error updating AI setting:', err);
      alert(err instanceof Error ? err.message : 'שגיאה בשמירת ההגדרה');
      // Revert on error
      setAssetsUseAi(!enabled);
    } finally {
      setSavingAiToggle(false);
    }
  };

  useEffect(() => {
    fetchAssets();
    fetchAiSetting();
  }, [fetchAssets, fetchAiSetting]);

  // Fetch asset details
  const fetchAssetDetail = async (assetId: number) => {
    try {
      setDetailLoading(true);
      const response = await fetch(`/api/assets/${assetId}`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('שגיאה בטעינת פרטי הפריט');
      }
      
      const data: AssetDetail = await response.json();
      setSelectedAsset(data);
      setDrawerOpen(true);
    } catch (err) {
      console.error('Error fetching asset detail:', err);
    } finally {
      setDetailLoading(false);
    }
  };

  // Create new asset
  const handleCreate = async () => {
    if (!formData.title.trim()) return;
    
    try {
      setSaving(true);
      
      // Create asset first
      const response = await fetch('/api/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: formData.title.trim(),
          description: formData.description.trim() || null,
          category: formData.category.trim() || null,
          tags: formData.tags,
          custom_fields: Object.keys(formData.custom_fields).length > 0 ? formData.custom_fields : null
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'שגיאה ביצירת פריט');
      }
      
      const asset = await response.json();
      const assetId = asset.id;
      
      // Upload files if any
      if (uploadingFiles.length > 0) {
        setUploadProgress(true);
        const uploadPromises = uploadingFiles.map(async (file, i) => {
          try {
            // Upload file to attachments service
            const uploadFormData = new FormData();
            uploadFormData.append('file', file);
            uploadFormData.append('channel', 'assets');
            
            const uploadResponse = await fetch('/api/attachments/upload', {
              method: 'POST',
              credentials: 'include',
              body: uploadFormData
            });
            
            if (!uploadResponse.ok) {
              const errorData = await uploadResponse.json().catch(() => ({}));
              throw new Error(`Failed to upload ${file.name}: ${errorData.error || uploadResponse.statusText}`);
            }
            
            const attachmentData = await uploadResponse.json();
            
            // Link attachment to asset
            const linkResponse = await fetch(`/api/assets/${assetId}/media`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({
                attachment_id: attachmentData.id,
                role: i === 0 ? 'cover' : 'gallery',
                sort_order: i
              })
            });
            
            if (!linkResponse.ok) {
              const linkError = await linkResponse.json().catch(() => ({}));
              console.warn(`Failed to link ${file.name} to asset:`, linkError.error || linkResponse.statusText);
            }
            
            return { success: true, filename: file.name };
          } catch (fileErr) {
            console.error(`Error uploading file ${file.name}:`, fileErr);
            return { success: false, filename: file.name, error: fileErr instanceof Error ? fileErr.message : String(fileErr) };
          }
        });
        
        // Wait for all uploads to complete
        const results = await Promise.all(uploadPromises);
        const failedUploads = results.filter(r => !r.success);
        
        if (failedUploads.length > 0) {
          const failedNames = failedUploads.map(f => f.filename).join(', ');
          alert(`חלק מהקבצים לא הועלו בהצלחה: ${failedNames}`);
        }
        
        setUploadProgress(false);
      }
      
      setModalOpen(false);
      resetForm();
      setUploadingFiles([]);
      fetchAssets();
    } catch (err) {
      console.error('Error creating asset:', err);
      alert(err instanceof Error ? err.message : 'שגיאה ביצירת פריט');
    } finally {
      setSaving(false);
      setUploadProgress(false);
    }
  };

  // Update asset
  const handleUpdate = async () => {
    if (!editingAsset || !formData.title.trim()) return;
    
    try {
      setSaving(true);
      const response = await fetch(`/api/assets/${editingAsset.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: formData.title.trim(),
          description: formData.description.trim() || null,
          category: formData.category.trim() || null,
          tags: formData.tags,
          custom_fields: Object.keys(formData.custom_fields).length > 0 ? formData.custom_fields : null
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'שגיאה בעדכון פריט');
      }
      
      setModalOpen(false);
      setEditingAsset(null);
      resetForm();
      fetchAssets();
      
      // Refresh detail if open
      if (selectedAsset?.id === editingAsset.id) {
        fetchAssetDetail(editingAsset.id);
      }
    } catch (err) {
      console.error('Error updating asset:', err);
      alert(err instanceof Error ? err.message : 'שגיאה בעדכון פריט');
    } finally {
      setSaving(false);
    }
  };

  // Archive asset
  const handleArchive = async (assetId: number) => {
    if (!confirm('האם לארכב את הפריט? ניתן לשחזר אותו בהמשך.')) return;
    
    try {
      const response = await fetch(`/api/assets/${assetId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('שגיאה בארכוב הפריט');
      }
      
      fetchAssets();
      if (selectedAsset?.id === assetId) {
        setDrawerOpen(false);
        setSelectedAsset(null);
      }
    } catch (err) {
      console.error('Error archiving asset:', err);
      alert('שגיאה בארכוב הפריט');
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      category: '',
      tags: [],
      custom_fields: {}
    });
    setUploadingFiles([]);
  };

  const openEditModal = (asset: AssetDetail) => {
    setEditingAsset(asset);
    setFormData({
      title: asset.title,
      description: asset.description || '',
      category: asset.category || '',
      tags: asset.tags || [],
      custom_fields: asset.custom_fields || {}
    });
    setModalOpen(true);
  };

  const openCreateModal = () => {
    setEditingAsset(null);
    resetForm();
    setModalOpen(true);
  };

  // Render loading state
  if (loading && assets.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="px-4 md:px-6 py-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-center gap-3">
              <Package className="h-6 w-6 text-blue-600" />
              <div>
                <h1 className="text-xl md:text-2xl font-bold text-slate-900">מאגר</h1>
                <p className="text-sm text-slate-500">{total} פריטים</p>
              </div>
            </div>
            
            {/* AI Tools Toggle */}
            <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
              <Bot className="h-5 w-5 text-blue-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-900">גישת AI למאגר</p>
                <p className="text-xs text-slate-600">כאשר מופעל, ה-AI יכול לחפש ולהציג פריטים מהמאגר</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={assetsUseAi}
                  onChange={(e) => updateAiSetting(e.target.checked)}
                  disabled={savingAiToggle}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white  after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                <span className="mr-3 text-sm font-medium text-slate-700">
                  {savingAiToggle ? 'שומר...' : (assetsUseAi ? 'מופעל' : 'כבוי')}
                </span>
              </label>
            </div>
            
            {/* Desktop create button */}
            <button
              onClick={openCreateModal}
              className="hidden md:flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium"
            >
              <Plus className="h-5 w-5" />
              פריט חדש
            </button>
          </div>
          
          {/* Filters */}
          <div className="mt-4 flex flex-col md:flex-row gap-3">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                placeholder="חיפוש לפי שם, תיאור או תגיות..."
                className="w-full pr-10 pl-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            
            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white min-w-[120px]"
            >
              <option value="active">פעילים</option>
              <option value="archived">ארכיון</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mx-4 md:mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          {error}
        </div>
      )}

      {/* Assets Grid */}
      <div className="p-4 md:p-6">
        {assets.length === 0 ? (
          <div className="text-center py-12">
            <Package className="h-12 w-12 mx-auto text-slate-300 mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">אין פריטים במאגר</h3>
            <p className="text-slate-500 mb-4">התחל להוסיף פריטים למאגר שלך</p>
            <button
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700"
            >
              <Plus className="h-5 w-5" />
              הוסף פריט ראשון
            </button>
          </div>
        ) : (
          <>
            {/* Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {assets.map((asset) => (
                <div
                  key={asset.id}
                  onClick={() => fetchAssetDetail(asset.id)}
                  className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-lg transition-all cursor-pointer group"
                >
                  {/* Cover Image */}
                  <div className="aspect-video bg-slate-100 relative overflow-hidden">
                    {asset.cover_preview_url ? (
                      <img
                        src={asset.cover_preview_url}
                        alt={asset.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="h-12 w-12 text-slate-300" />
                      </div>
                    )}
                    
                    {/* Media count badge */}
                    {asset.media_count > 0 && (
                      <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-lg flex items-center gap-1">
                        <Image className="h-3 w-3" />
                        {asset.media_count}
                      </div>
                    )}
                  </div>
                  
                  {/* Content */}
                  <div className="p-4">
                    <h3 className="font-semibold text-slate-900 truncate">{asset.title}</h3>
                    {asset.description && (
                      <p className="text-sm text-slate-500 mt-1 line-clamp-2" title={asset.description}>{asset.description}</p>
                    )}
                    
                    {/* Tags */}
                    {asset.tags && asset.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3 overflow-x-auto">
                        {asset.tags.slice(0, 3).map((tag, i) => (
                          <span
                            key={i}
                            className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full whitespace-nowrap"
                          >
                            {tag}
                          </span>
                        ))}
                        {asset.tags.length > 3 && (
                          <span className="text-xs text-slate-400">+{asset.tags.length - 3}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex justify-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                >
                  הקודם
                </button>
                <span className="px-4 py-2 text-slate-600">
                  עמוד {page} מתוך {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                >
                  הבא
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Mobile FAB */}
      <button
        onClick={openCreateModal}
        className="md:hidden fixed bottom-24 left-4 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-blue-700 z-20"
        aria-label="הוסף פריט"
      >
        <Plus className="h-6 w-6" />
      </button>

      {/* Detail Drawer */}
      {drawerOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => { setDrawerOpen(false); setSelectedAsset(null); }}
          />
          
          {/* Drawer */}
          <div className="fixed inset-y-0 left-0 w-full max-w-lg bg-white shadow-xl z-50 overflow-y-auto">
            {/* Drawer Header */}
            <div className="sticky top-0 bg-white border-b border-slate-200 px-4 py-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {selectedAsset?.title || 'טוען...'}
              </h2>
              <button
                onClick={() => { setDrawerOpen(false); setSelectedAsset(null); }}
                className="p-2 hover:bg-slate-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            {detailLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              </div>
            ) : selectedAsset ? (
              <div className="p-4">
                {/* Actions */}
                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => openEditModal(selectedAsset)}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-slate-300 rounded-xl hover:bg-slate-50"
                  >
                    <Edit className="h-4 w-4" />
                    עריכה
                  </button>
                  <button
                    onClick={() => handleArchive(selectedAsset.id)}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-red-300 text-red-600 rounded-xl hover:bg-red-50"
                  >
                    <Archive className="h-4 w-4" />
                    ארכב
                  </button>
                </div>
                
                {/* Gallery */}
                {selectedAsset.media && selectedAsset.media.length > 0 && (
                  <div className="mb-6">
                    <h3 className="font-semibold text-slate-900 mb-3">תמונות ({selectedAsset.media.length})</h3>
                    <div className="grid grid-cols-2 gap-2">
                      {selectedAsset.media.map((media) => (
                        <div key={media.id} className="relative aspect-square rounded-lg overflow-hidden bg-slate-100">
                          <img
                            src={media.signed_url}
                            alt={media.filename}
                            className="w-full h-full object-cover"
                          />
                          {media.role === 'cover' && (
                            <div className="absolute top-1 left-1 bg-yellow-500 text-white text-xs px-1.5 py-0.5 rounded flex items-center gap-1">
                              <Star className="h-3 w-3" />
                              קאבר
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Details */}
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-slate-900 mb-2">פרטים</h3>
                    <dl className="space-y-2">
                      {selectedAsset.category && (
                        <div className="flex justify-between">
                          <dt className="text-slate-500">קטגוריה</dt>
                          <dd className="text-slate-900">{selectedAsset.category}</dd>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <dt className="text-slate-500">סטטוס</dt>
                        <dd className={cn(
                          "px-2 py-0.5 rounded text-sm",
                          selectedAsset.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                        )}>
                          {selectedAsset.status === 'active' ? 'פעיל' : 'ארכיון'}
                        </dd>
                      </div>
                    </dl>
                  </div>
                  
                  {selectedAsset.description && (
                    <div>
                      <h3 className="font-semibold text-slate-900 mb-2">תיאור</h3>
                      <p className="text-slate-600 whitespace-pre-wrap">{selectedAsset.description}</p>
                    </div>
                  )}
                  
                  {selectedAsset.tags && selectedAsset.tags.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-slate-900 mb-2">תגיות</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedAsset.tags.map((tag, i) => (
                          <span key={i} className="px-3 py-1 bg-slate-100 text-slate-700 rounded-full text-sm">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {selectedAsset.custom_fields && Object.keys(selectedAsset.custom_fields).length > 0 && (
                    <div>
                      <h3 className="font-semibold text-slate-900 mb-2">שדות מותאמים</h3>
                      <dl className="space-y-2">
                        {Object.entries(selectedAsset.custom_fields).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <dt className="text-slate-500">{key}</dt>
                            <dd className="text-slate-900">{String(value)}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </>
      )}

      {/* Create/Edit Modal */}
      {modalOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => { setModalOpen(false); setEditingAsset(null); resetForm(); }}
          />
          
          {/* Modal */}
          <div className="fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full md:max-w-lg bg-white rounded-xl shadow-xl z-50 overflow-hidden flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {editingAsset ? 'עריכת פריט' : 'פריט חדש'}
              </h2>
              <button
                onClick={() => { setModalOpen(false); setEditingAsset(null); resetForm(); }}
                className="p-2 hover:bg-slate-100 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            {/* Form */}
            <div className="p-6 overflow-y-auto flex-1">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    שם הפריט *
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData(f => ({ ...f, title: e.target.value }))}
                    placeholder="הזן שם לפריט"
                    className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    maxLength={160}
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    תיאור
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData(f => ({ ...f, description: e.target.value }))}
                    placeholder="תיאור הפריט"
                    rows={4}
                    className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    קטגוריה
                  </label>
                  <input
                    type="text"
                    value={formData.category}
                    onChange={(e) => setFormData(f => ({ ...f, category: e.target.value }))}
                    placeholder="למשל: דירה, מוצר, שירות"
                    className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    תגיות (מופרדות בפסיקים)
                  </label>
                  <input
                    type="text"
                    value={formData.tags.join(', ')}
                    onChange={(e) => setFormData(f => ({
                      ...f,
                      tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                    }))}
                    placeholder="תגית1, תגית2, תגית3"
                    className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                
                {/* File Upload Section */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    תמונות ומדיה
                  </label>
                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-4 text-center">
                    <input
                      type="file"
                      multiple
                      accept="image/*,video/*,application/pdf"
                      onChange={(e) => {
                        if (e.target.files) {
                          setUploadingFiles(Array.from(e.target.files));
                        }
                      }}
                      className="hidden"
                      id="asset-file-upload"
                    />
                    <label
                      htmlFor="asset-file-upload"
                      className="cursor-pointer flex flex-col items-center"
                    >
                      <Upload className="h-8 w-8 text-slate-400 mb-2" />
                      <span className="text-sm text-slate-600 mb-1">העלה תמונות ומדיה</span>
                      <span className="text-xs text-slate-400">תמונות, סרטונים, PDF</span>
                    </label>
                    
                    {uploadingFiles.length > 0 && (
                      <div className="mt-3 text-right space-y-1">
                        <p className="text-sm font-medium text-slate-700">קבצים נבחרו:</p>
                        {uploadingFiles.map((file, i) => (
                          <div key={i} className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded">
                            <span>{file.name}</span>
                            <button
                              type="button"
                              onClick={() => setUploadingFiles(files => files.filter((_, index) => index !== i))}
                              className="text-red-500 hover:text-red-700"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    התמונה הראשונה תהיה תמונת הקאבר של הפריט
                  </p>
                </div>
              </div>
            </div>
            
            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-200 flex gap-3">
              <button
                onClick={() => { setModalOpen(false); setEditingAsset(null); resetForm(); }}
                className="flex-1 px-4 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 font-medium"
              >
                ביטול
              </button>
              <button
                onClick={editingAsset ? handleUpdate : handleCreate}
                disabled={saving || uploadProgress || !formData.title.trim()}
                className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {(saving || uploadProgress) && <Loader2 className="h-4 w-4 animate-spin" />}
                {uploadProgress ? 'מעלה קבצים...' : (editingAsset ? 'שמור שינויים' : 'צור פריט')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
