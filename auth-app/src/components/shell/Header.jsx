import { motion } from 'framer-motion'
import { Menu, Search, Bell, User, LogOut } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useState } from 'react'

const Header = ({ onMenuClick }) => {
  const { user, logout, impersonating, stopImpersonating } = useAuth()
  const [showUserMenu, setShowUserMenu] = useState(false)

  const handleLogout = () => {
    logout()
    setShowUserMenu(false)
  }

  const stopImpersonation = () => {
    stopImpersonating()
    setShowUserMenu(false)
  }

  return (
    <motion.header 
      className="fixed top-0 left-0 right-0 h-16 bg-white/90 backdrop-blur-lg border-b border-slate-200/60 z-50"
      initial={{ y: -64 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="h-full px-4 flex items-center justify-between">
        {/* Right side - Menu & Logo */}
        <div className="flex items-center gap-3">
          <motion.button
            onClick={onMenuClick}
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Menu className="w-5 h-5 text-slate-700" />
          </motion.button>
          
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">שי</span>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-slate-800">
                {impersonating ? impersonating.name : 
                 user?.role === 'superadmin' || user?.role === 'admin' ? 'מנהל מערכת' : 
                 user?.business?.name || 'מערכת CRM'}
              </span>
              {impersonating && (
                <span className="text-xs text-orange-600 font-medium">
                  מתחזה כעסק
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Left side - Actions */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <motion.button
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Search className="w-5 h-5 text-slate-600" />
          </motion.button>

          {/* Notifications */}
          <motion.button
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors relative"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Bell className="w-5 h-5 text-slate-600" />
            <span className="absolute -top-1 -left-1 w-3 h-3 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">3</span>
          </motion.button>

          {/* User Menu */}
          <div className="relative">
            <motion.button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-100 transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-full flex items-center justify-center">
                <span className="text-white font-semibold text-sm">
                  {user?.name?.charAt(0) || 'M'}
                </span>
              </div>
            </motion.button>

            {/* User Dropdown */}
            {showUserMenu && (
              <motion.div
                className="absolute left-0 top-full mt-2 w-64 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50"
                initial={{ opacity: 0, scale: 0.95, y: -10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.15 }}
              >
                <div className="px-4 py-3 border-b border-slate-100">
                  <p className="font-semibold text-slate-800">{user?.name}</p>
                  <p className="text-sm text-slate-500">{user?.email}</p>
                  <span className="inline-block mt-1 px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full">
                    {user?.role === 'superadmin' ? 'מנהל עליון' :
                     user?.role === 'admin' ? 'מנהל מערכת' :
                     user?.role === 'business_owner' ? 'בעל עסק' :
                     user?.role === 'business_agent' ? 'סוכן' : 'צופה'}
                  </span>
                </div>
                
                {impersonating && (
                  <button
                    onClick={stopImpersonation}
                    className="w-full px-4 py-2 text-right hover:bg-orange-50 text-orange-600 text-sm flex items-center gap-2"
                  >
                    <User className="w-4 h-4" />
                    הפסק התחזות
                  </button>
                )}
                
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-right hover:bg-red-50 text-red-600 text-sm flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  התנתק
                </button>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </motion.header>
  )
}

export default Header