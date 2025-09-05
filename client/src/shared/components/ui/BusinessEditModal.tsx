import React, { useState } from 'react';
import { X, Save, Building2, Phone, MessageCircle, Lock } from 'lucide-react';

interface Business {
  id: number;
  name: string;
  domain: string;
  defaultPhoneE164: string;
  whatsappJid: string;
  status: 'active' | 'suspended';
  prompt?: string;
  permissions?: string[];
}

interface BusinessEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  business: Business | null;
  onSave: (updatedBusiness: Business) => void;
}

export function BusinessEditModal({ isOpen, onClose, business, onSave }: BusinessEditModalProps) {
  const [formData, setFormData] = useState({
    name: business?.name || '',
    domain: business?.domain || '',
    defaultPhoneE164: business?.defaultPhoneE164 || '',
    whatsappJid: business?.whatsappJid || '',
    prompt: business?.prompt || 'אני ליאה, הסוכנת הדיגיטלית של שי דירות ומשרדים. אני כאן לעזור לכם למצוא את הנכס המושלם. איך אוכל לעזור לכם היום?',
    permissions: business?.permissions || ['calls', 'whatsapp', 'crm']
  });

  React.useEffect(() => {
    if (business) {
      setFormData({
        name: business.name,
        domain: business.domain,
        defaultPhoneE164: business.defaultPhoneE164,
        whatsappJid: business.whatsappJid,
        prompt: business.prompt || 'אני ליאה, הסוכנת הדיגיטלית של שי דירות ומשרדים. אני כאן לעזור לכם למצוא את הנכס המושלם. איך אוכל לעזור לכם היום?',
        permissions: business.permissions || ['calls', 'whatsapp', 'crm']
      });
    }
  }, [business]);

  const handleSave = () => {
    if (!business) return;
    
    const updatedBusiness = {
      ...business,
      ...formData
    };
    
    onSave(updatedBusiness);
    onClose();
  };

  const handlePermissionToggle = (permission: string) => {
    setFormData(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter(p => p !== permission)
        : [...prev.permissions, permission]
    }));
  };

  if (!isOpen || !business) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" dir="rtl">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Building2 className="h-5 w-5 text-white" />
              </div>
              <h2 className="text-xl font-semibold text-slate-900">
                עריכת עסק - {business.name}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              data-testid="button-close-edit-modal"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Basic Info */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-slate-900 flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                פרטי עסק
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    שם העסק
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    data-testid="input-business-name"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    דומיין
                  </label>
                  <input
                    type="text"
                    value={formData.domain}
                    onChange={(e) => setFormData(prev => ({ ...prev, domain: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent direction-ltr"
                    data-testid="input-business-domain"
                  />
                </div>
              </div>
            </div>

            {/* Contact Info */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-slate-900 flex items-center gap-2">
                <Phone className="h-5 w-5" />
                פרטי התקשרות
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    מספר טלפון ראשי
                  </label>
                  <input
                    type="text"
                    value={formData.defaultPhoneE164}
                    onChange={(e) => setFormData(prev => ({ ...prev, defaultPhoneE164: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent direction-ltr"
                    placeholder="+972-XX-XXX-XXXX"
                    data-testid="input-phone-number"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    WhatsApp JID
                  </label>
                  <input
                    type="text"
                    value={formData.whatsappJid}
                    onChange={(e) => setFormData(prev => ({ ...prev, whatsappJid: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent direction-ltr"
                    placeholder="972XXXXXXXXX@s.whatsapp.net"
                    data-testid="input-whatsapp-jid"
                  />
                </div>
              </div>
            </div>

            {/* AI Prompt */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-slate-900 flex items-center gap-2">
                <MessageCircle className="h-5 w-5" />
                פרומפט AI
              </h3>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הודעת פתיחה של הסוכן הדיגיטלי
                </label>
                <textarea
                  value={formData.prompt}
                  onChange={(e) => setFormData(prev => ({ ...prev, prompt: e.target.value }))}
                  rows={4}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="הכנס את הפרומפט עבור הסוכן הדיגיטלי..."
                  data-testid="textarea-ai-prompt"
                />
              </div>
            </div>

            {/* Permissions */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-slate-900 flex items-center gap-2">
                <Lock className="h-5 w-5" />
                הרשאות מערכת
              </h3>
              
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { id: 'calls', label: 'שיחות טלפון', icon: Phone },
                  { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
                  { id: 'crm', label: 'CRM', icon: Building2 }
                ].map(({ id, label, icon: Icon }) => (
                  <label key={id} className="flex items-center gap-3 p-3 border border-slate-200 rounded-lg hover:bg-slate-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.permissions.includes(id)}
                      onChange={() => handlePermissionToggle(id)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      data-testid={`checkbox-permission-${id}`}
                    />
                    <Icon className="h-4 w-4 text-slate-600" />
                    <span className="text-sm font-medium text-slate-700">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200">
            <button
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              data-testid="button-cancel-edit"
            >
              ביטול
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              data-testid="button-save-edit"
            >
              <Save className="h-4 w-4" />
              שמור שינויים
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}