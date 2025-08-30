import { useAuth } from '@/contexts/AuthContext'

const AdminOverviewDebug = () => {
  const { user } = useAuth()
  
  console.log('🔧 DEBUG: AdminOverviewDebug component loaded!')
  console.log('🔧 User:', user)

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6 bg-red-50 min-h-screen">
      <div className="bg-red-500 text-white p-8 rounded-2xl text-center">
        <h1 className="text-3xl font-bold mb-4">🎯 ADMIN OVERVIEW DEBUG</h1>
        <p className="text-xl">משתמש: {user?.name || 'לא זמין'}</p>
        <p className="text-lg">תפקיד: {user?.role || 'לא זמין'}</p>
        <p className="text-lg">אימייל: {user?.email || 'לא זמין'}</p>
      </div>
      
      <div className="bg-white p-6 rounded-xl shadow-lg">
        <h2 className="text-2xl font-bold text-slate-800 mb-4">✅ הקומפוננט עובד!</h2>
        <p className="text-slate-600 mb-4">אם אתה רואה את זה, React עובד תקין.</p>
        
        <div className="bg-gradient-to-br from-purple-500 to-indigo-600 text-white p-4 rounded-xl">
          <h3 className="text-lg font-bold mb-2">🎯 קוביית ניהול עסקים</h3>
          <p className="text-purple-200">12 עסקים פעילים</p>
          <p className="text-purple-200">9 פעילים, 3 מוקפאים</p>
        </div>
      </div>
      
      <div className="bg-white p-6 rounded-xl shadow-lg">
        <h3 className="text-xl font-bold text-slate-800 mb-4">📊 KPIs מהירים</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-blue-100 p-4 rounded-lg text-center">
            <p className="text-2xl font-bold text-blue-600">15</p>
            <p className="text-blue-800">שיחות פעילות</p>
          </div>
          <div className="bg-green-100 p-4 rounded-lg text-center">
            <p className="text-2xl font-bold text-green-600">247</p>
            <p className="text-green-800">הודעות WA</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminOverviewDebug