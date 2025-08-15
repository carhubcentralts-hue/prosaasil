// Use local User interface
interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  businessId: string | null;
  isActive: boolean;
}

interface SystemSelectorProps {
  user: User;
  onSelectSystem: (system: string) => void;
}

export function SystemSelector({ user, onSelectSystem }: SystemSelectorProps) {
  const systems = [
    {
      id: 'calls',
      title: 'מערכת שיחות',
      description: 'ניהול שיחות נכנסות ויוצאות',
      icon: '📞',
      available: ['admin', 'business'],
    },
    {
      id: 'whatsapp', 
      title: 'מערכת WhatsApp',
      description: 'ניהול הודעות WhatsApp',
      icon: '💬',
      available: ['admin', 'business'],
    },
    {
      id: 'crm',
      title: 'מערכת CRM',
      description: 'ניהול לקוחות ולידים',
      icon: '👥',
      available: ['admin', 'business'],
    },
  ];

  const availableSystems = systems.filter(system => 
    system.available.includes(user.role)
  );

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12" dir="rtl">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            מערכת ניהול שיחות עברית AI
          </h1>
          <p className="text-xl text-gray-600 mb-2">
            שלום {user.firstName} {user.lastName}
          </p>
          <p className="text-lg text-gray-500">
            {user.role === 'admin' ? 'מנהל מערכת' : 'מנהל עסק'}
          </p>
        </div>

        {/* System Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {availableSystems.map((system) => (
            <div
              key={system.id}
              onClick={() => onSelectSystem(system.id)}
              className="bg-white border-2 border-gray-200 rounded-lg p-8 hover:border-indigo-500 hover:shadow-lg transition-all duration-200 cursor-pointer group"
              data-testid={`card-system-${system.id}`}
            >
              <div className="text-center">
                <div className="text-6xl mb-4">{system.icon}</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3" dir="rtl">
                  {system.title}
                </h3>
                <p className="text-gray-600 mb-6" dir="rtl">
                  {system.description}
                </p>
                <button className="w-full bg-indigo-600 text-white px-6 py-3 rounded-md hover:bg-indigo-700 transition-colors group-hover:bg-indigo-700" data-testid={`button-enter-${system.id}`}>
                  כניסה למערכת
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Admin Panel for Admin Users */}
        {user.role === 'admin' && (
          <div className="mt-16 max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center" dir="rtl">
              פאנל ניהול מנהל
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div
                onClick={() => onSelectSystem('admin-users')}
                className="bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-lg p-6 hover:from-purple-700 hover:to-purple-800 transition-all duration-200 cursor-pointer"
                data-testid="card-admin-users"
              >
                <div className="text-center">
                  <div className="text-4xl mb-3">👨‍💼</div>
                  <h3 className="text-xl font-bold mb-2" dir="rtl">ניהול משתמשים</h3>
                  <p className="text-purple-100" dir="rtl">ניהול משתמשים ותפקידים במערכת</p>
                </div>
              </div>

              <div
                onClick={() => onSelectSystem('admin-businesses')}
                className="bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg p-6 hover:from-green-700 hover:to-green-800 transition-all duration-200 cursor-pointer"
                data-testid="card-admin-businesses"
              >
                <div className="text-center">
                  <div className="text-4xl mb-3">🏢</div>
                  <h3 className="text-xl font-bold mb-2" dir="rtl">ניהול עסקים</h3>
                  <p className="text-green-100" dir="rtl">ניהול עסקים ובקרה על המערכת</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Logout Button */}
        <div className="text-center mt-16">
          <button
            onClick={() => onSelectSystem('logout')}
            className="text-gray-600 hover:text-gray-800 text-lg font-medium border border-gray-300 px-6 py-2 rounded-md hover:border-gray-400 transition-colors"
            data-testid="button-logout"
            dir="rtl"
          >
            התנתק מהמערכת
          </button>
        </div>
      </div>
    </div>
  );
}