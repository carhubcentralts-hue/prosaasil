export default function Topbar() {
  return (
    <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Search Bar */}
        <div className="flex-1 max-w-md">
          <div className="relative">
            <div className="absolute inset-y-0 right-0 flex items-center pr-3">
              <i className="fas fa-search text-gray-400"></i>
            </div>
            <input
              type="text"
              placeholder="חיפוש לקוחות, חשבוניות וכו'..."
              className="w-full bg-gray-50 border border-gray-300 rounded-lg py-2 pr-10 pl-4 text-sm focus:outline-none focus:border-blue-500 focus:bg-white transition-colors"
            />
          </div>
        </div>

        {/* Right Side Actions */}
        <div className="flex items-center space-x-reverse space-x-4">
          {/* Notifications */}
          <button className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
            <i className="fas fa-bell text-lg"></i>
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>

          {/* Quick Actions */}
          <div className="flex items-center space-x-reverse space-x-2">
            <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
              <i className="fas fa-plus ml-2"></i>
              לקוח חדש
            </button>
            <button className="bg-teal-500 hover:bg-teal-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
              <i className="fas fa-phone ml-2"></i>
              שיחה חדשה
            </button>
          </div>

          {/* User Menu */}
          <div className="flex items-center space-x-reverse space-x-3 border-r border-gray-200 pr-4">
            <div className="text-right">
              <div className="text-sm font-medium text-gray-700">משתמש מנהל</div>
              <div className="text-xs text-gray-500">admin@example.com</div>
            </div>
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-teal-500 rounded-full flex items-center justify-center">
              <i className="fas fa-user text-white text-sm"></i>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}