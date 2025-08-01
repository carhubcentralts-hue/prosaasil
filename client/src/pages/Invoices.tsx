export default function Invoices() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">ניהול חשבוניות</h1>
          <p className="text-gray-600 mt-1">יצירה ומעקב אחר חשבוניות ותשלומים</p>
        </div>
        <button className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
          <i className="fas fa-file-invoice ml-2"></i>
          חשבונית חדשה
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="text-center py-20">
          <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <i className="fas fa-file-invoice-dollar text-2xl text-orange-600"></i>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">מודול חשבוניות</h2>
          <p className="text-gray-600 mb-6 max-w-md mx-auto">
            יצירה אוטומטית של חשבוניות, אינטגרציה עם Cardcom/Tranzila/משולם
          </p>
          <div className="flex justify-center space-x-reverse space-x-4">
            <button className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
              צור חשבונית ראשונה
            </button>
            <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-6 py-3 rounded-lg font-medium transition-colors">
              הגדרות תשלום
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}