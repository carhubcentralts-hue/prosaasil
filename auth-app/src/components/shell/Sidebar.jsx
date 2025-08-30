import { motion, AnimatePresence } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { 
  X, 
  BarChart3, 
  Building2, 
  Users, 
  MessageSquare, 
  Phone, 
  UserCheck, 
  CreditCard, 
  Settings,
  Eye,
  Zap
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import clsx from 'clsx'

const Sidebar = ({ open, onClose }) => {
  const { user, isAdmin, isBusiness, hasPermission } = useAuth()

  // Navigation items based on role
  const getNavItems = () => {
    if (isAdmin()) {
      return [
        { 
          id: 'overview', 
          path: '/app/admin/overview', 
          icon: BarChart3, 
          label: 'סקירה כללית',
          badge: null
        },
        { 
          id: 'businesses', 
          path: '/app/admin/businesses', 
          icon: Building2, 
          label: 'עסקים',
          badge: '5'
        },
        { 
          id: 'users', 
          path: '/app/admin/users', 
          icon: Users, 
          label: 'משתמשים',
          badge: null
        },
        { 
          id: 'whatsapp', 
          path: '/app/admin/whatsapp', 
          icon: MessageSquare, 
          label: 'WhatsApp Panorama',
          badge: '12'
        },
        { 
          id: 'calls', 
          path: '/app/admin/calls', 
          icon: Phone, 
          label: 'שיחות מערכתיות',
          badge: '3'
        },
        { 
          id: 'finance', 
          path: '/app/admin/finance', 
          icon: CreditCard, 
          label: 'כספים',
          badge: null
        },
        { 
          id: 'settings', 
          path: '/app/admin/settings', 
          icon: Settings, 
          label: 'הגדרות מערכת',
          badge: null
        }
      ]
    } else if (isBusiness()) {
      const items = [
        { 
          id: 'overview', 
          path: '/app/biz/overview', 
          icon: BarChart3, 
          label: 'סקירה כללית',
          badge: null
        },
        { 
          id: 'whatsapp', 
          path: '/app/biz/whatsapp', 
          icon: MessageSquare, 
          label: 'WhatsApp',
          badge: '8'
        },
        { 
          id: 'calls', 
          path: '/app/biz/calls', 
          icon: Phone, 
          label: 'שיחות',
          badge: '2'
        },
        { 
          id: 'crm', 
          path: '/app/biz/crm', 
          icon: UserCheck, 
          label: 'CRM',
          badge: '15'
        },
        { 
          id: 'finance', 
          path: '/app/biz/finance', 
          icon: CreditCard, 
          label: 'תשלומים וחוזים',
          badge: '3'
        }
      ]

      // Add users management for business owners
      if (hasPermission('manage_business_users')) {
        items.push({
          id: 'users', 
          path: '/app/biz/users', 
          icon: Users, 
          label: 'משתמשי העסק',
          badge: null
        })
      }

      items.push({
        id: 'settings', 
        path: '/app/biz/settings', 
        icon: Settings, 
        label: 'הגדרות העסק',
        badge: null
      })

      return items
    }

    return []
  }

  const navItems = getNavItems()

  return (
    <>
      {/* Backdrop */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 bg-black/50 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/* Sidebar Sheet */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed top-0 right-0 h-full w-80 bg-white shadow-2xl z-50 flex flex-col"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-200">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-primary rounded-xl flex items-center justify-center">
                  <span className="text-white font-bold">שי</span>
                </div>
                <div>
                  <h2 className="font-bold text-slate-800">
                    {isAdmin() ? 'מנהל מערכת' : 'לוח הבקרה'}
                  </h2>
                  <p className="text-sm text-slate-500">{user?.name}</p>
                </div>
              </div>
              
              <motion.button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <X className="w-5 h-5 text-slate-600" />
              </motion.button>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-1">
              {navItems.map((item, index) => {
                const Icon = item.icon
                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <NavLink
                      to={item.path}
                      onClick={onClose}
                      className={({ isActive }) => clsx(
                        'flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200',
                        isActive 
                          ? 'bg-gradient-primary text-white shadow-lg' 
                          : 'text-slate-700 hover:bg-slate-100 hover:scale-[1.02]'
                      )}
                    >
                      <Icon className="w-5 h-5" />
                      <span className="flex-1">{item.label}</span>
                      {item.badge && (
                        <span className="px-2 py-1 bg-red-500 text-white text-xs rounded-full">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  </motion.div>
                )
              })}
            </nav>

            {/* Quick Actions */}
            <div className="p-4 border-t border-slate-200">
              <div className="space-y-2">
                {isAdmin() && (
                  <motion.button
                    className="w-full flex items-center gap-2 px-4 py-2 bg-orange-100 text-orange-700 rounded-lg text-sm font-medium hover:bg-orange-200 transition-colors"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Eye className="w-4 h-4" />
                    מצב התחזות
                  </motion.button>
                )}
                
                <motion.button
                  className="w-full flex items-center gap-2 px-4 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200 transition-colors"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Zap className="w-4 h-4" />
                  פעולה מהירה
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

export default Sidebar