export default function AiCalls() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">שיחות AI</h1>
          <p className="text-gray-600 mt-1">מערכת שיחות אוטומטיות בעברית</p>
        </div>
        <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
          <i className="fas fa-phone ml-2"></i>
          שיחה חדשה
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="text-center py-20">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <i className="fas fa-phone text-2xl text-blue-600"></i>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">מערכת שיחות AI</h2>
          <p className="text-gray-600 mb-6 max-w-md mx-auto">
            שיחות טלפון אוטומטיות עם בינה מלאכותית בעברית, אינטגרציה עם Twilio ו-OpenAI
          </p>
          <div className="flex justify-center space-x-reverse space-x-4">
            <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium transition-colors">
              הגדר Twilio
            </button>
            <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-6 py-3 rounded-lg font-medium transition-colors">
              בדיקת מערכת
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}