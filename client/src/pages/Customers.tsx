export default function Customers() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">ניהול לקוחות</h1>
          <p className="text-gray-600 mt-1">ניהול מאגר הלקוחות והליידים</p>
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
          <i className="fas fa-plus ml-2"></i>
          לקוח חדש
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="text-center py-20">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <i className="fas fa-users text-2xl text-blue-600"></i>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">מודול לקוחות</h2>
          <p className="text-gray-600 mb-6 max-w-md mx-auto">
            כאן תוכל לנהל את כל הלקוחות שלך, לעקוב אחר פעילותם ולקבל תובנות על התנהגותם
          </p>
          <div className="flex justify-center space-x-reverse space-x-4">
            <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
              הוסף לקוח ראשון
            </button>
            <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-6 py-3 rounded-lg font-medium transition-colors">
              ייבא מקובץ CSV
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}