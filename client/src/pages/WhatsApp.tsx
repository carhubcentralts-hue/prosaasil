export default function WhatsApp() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">WhatsApp Business</h1>
          <p className="text-gray-600 mt-1">ניהול הודעות והתכתבויות עם לקוחות</p>
        </div>
        <button className="bg-green-500 hover:bg-green-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
          <i className="fab fa-whatsapp ml-2"></i>
          הודעה חדשה
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="text-center py-20">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <i className="fab fa-whatsapp text-2xl text-green-600"></i>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">מודול WhatsApp</h2>
          <p className="text-gray-600 mb-6 max-w-md mx-auto">
            התכתבות מקצועית עם לקוחות דרך WhatsApp Business API ו-Baileys integration
          </p>
          <div className="flex justify-center space-x-reverse space-x-4">
            <button className="bg-green-500 hover:bg-green-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
              חבר WhatsApp
            </button>
            <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-6 py-3 rounded-lg font-medium transition-colors">
              הגדרות Baileys
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}