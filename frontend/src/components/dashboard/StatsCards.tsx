import { motion } from 'framer-motion'
import { Users, ShoppingCart, TrendingUp } from 'lucide-react'
import { GlassCard } from '@/components/shared/GlassCard'
import { AnimatedCounter } from '@/components/shared/AnimatedCounter'
import { useAccounts, useOrders, useHistory } from '@/hooks'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

export function StatsCards() {
  const { data: accounts } = useAccounts()
  const { data: orders } = useOrders()
  const { data: history } = useHistory()

  const stats = [
    {
      title: 'Active Accounts',
      value: accounts?.filter((a) => a.is_active).length ?? 0,
      icon: Users,
      color: 'from-blue-500 to-cyan-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      title: 'Active Orders',
      value: orders?.length ?? 0,
      icon: ShoppingCart,
      color: 'from-purple-500 to-pink-500',
      bgColor: 'bg-purple-500/10',
    },
    {
      title: 'Total Outbids',
      value: history?.length ?? 0,
      icon: TrendingUp,
      color: 'from-green-500 to-emerald-500',
      bgColor: 'bg-green-500/10',
    },
  ]

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="grid gap-4 md:grid-cols-3"
    >
      {stats.map((stat, index) => {
        const Icon = stat.icon
        return (
          <GlassCard key={stat.title} transition={{ delay: index * 0.1 }}>
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.title}</p>
                  <p className="text-3xl font-bold mt-1">
                    <AnimatedCounter value={stat.value} />
                  </p>
                </div>
                <div
                  className={`p-3 rounded-xl bg-gradient-to-br ${stat.color} shadow-lg`}
                >
                  <Icon className="h-6 w-6 text-white" />
                </div>
              </div>
            </div>
          </GlassCard>
        )
      })}
    </motion.div>
  )
}
