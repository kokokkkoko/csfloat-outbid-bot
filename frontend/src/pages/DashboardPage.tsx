import { motion } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import { StatsCards } from '@/components/dashboard/StatsCards'
import { AccountsTab } from '@/components/accounts/AccountsTab'
import { OrdersTab } from '@/components/orders/OrdersTab'
import { HistoryTab } from '@/components/history/HistoryTab'
import { SettingsTab } from '@/components/settings/SettingsTab'
import { useHistory } from '@/hooks'

// Map URL paths to tab values
const pathToTab: Record<string, string> = {
  '/': 'dashboard',
  '/accounts': 'accounts',
  '/orders': 'orders',
  '/history': 'history',
  '/settings': 'settings',
}

export function DashboardPage() {
  const location = useLocation()
  const activeTab = pathToTab[location.pathname] || 'dashboard'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      {/* Stats Cards */}
      <StatsCards />

      {/* Content based on URL */}
      {activeTab === 'dashboard' && <RecentActivity />}
      {activeTab === 'accounts' && <AccountsTab />}
      {activeTab === 'orders' && <OrdersTab />}
      {activeTab === 'history' && <HistoryTab />}
      {activeTab === 'settings' && <SettingsTab />}
    </motion.div>
  )
}

function RecentActivity() {
  const { data: history, isLoading } = useHistory(10)

  return (
    <div className="rounded-xl border bg-card p-6">
      <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
      ) : history?.length === 0 ? (
        <p className="text-muted-foreground text-center py-8">
          No recent activity
        </p>
      ) : (
        <div className="space-y-3">
          {history?.slice(0, 10).map((h) => (
            <div
              key={h.id}
              className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
            >
              <div>
                <p className="font-medium truncate max-w-[200px]">
                  {h.market_hash_name}
                </p>
                <p className="text-sm text-muted-foreground">
                  {new Date(h.timestamp).toLocaleString()}
                </p>
              </div>
              <div className="text-right">
                <p className="text-green-500 font-medium">
                  ${(h.new_price_cents / 100).toFixed(2)}
                </p>
                <p className="text-sm text-muted-foreground">
                  from ${(h.old_price_cents / 100).toFixed(2)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
