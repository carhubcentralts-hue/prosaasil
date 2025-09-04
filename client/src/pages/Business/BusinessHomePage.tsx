export default function BusinessHomePage() {
  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">דשבורד עסקי</h1>
        <p className="text-gray-600 mt-2">שי דירות ומשרדים - סקירה כללית</p>
      </div>
      
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">לידים חדשים היום</h3>
          <p className="text-2xl font-bold text-green-600 mt-2">5</p>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">לידים פעילים</h3>
          <p className="text-2xl font-bold text-gray-900 mt-2">23</p>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">הודעות שלא נקראו</h3>
          <p className="text-2xl font-bold text-red-600 mt-2">7</p>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">פגישות היום</h3>
          <p className="text-2xl font-bold text-blue-600 mt-2">3</p>
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">פעולות מהירות</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-center">
            <div className="text-2xl mb-2">📞</div>
            <div className="text-sm font-medium">פתח מוקד שיחות</div>
          </button>
          
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-center">
            <div className="text-2xl mb-2">💬</div>
            <div className="text-sm font-medium">פתח וואטסאפ</div>
          </button>
          
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-center">
            <div className="text-2xl mb-2">👥</div>
            <div className="text-sm font-medium">פתח לידים</div>
          </button>
          
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-center">
            <div className="text-2xl mb-2">📅</div>
            <div className="text-sm font-medium">פתח יומן</div>
          </button>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">לידים אחרונים</h3>
        <p className="text-gray-600">בקרוב - רשימת לידים אחרונים</p>
      </div>
    </div>
  );
}