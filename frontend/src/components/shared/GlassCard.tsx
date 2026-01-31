import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/utils'

interface GlassCardProps extends HTMLMotionProps<'div'> {
  children: React.ReactNode
  className?: string
  hover?: boolean
}

export function GlassCard({ children, className, hover = true, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      whileHover={hover ? { scale: 1.02, y: -2 } : undefined}
      className={cn(
        'rounded-2xl border bg-card/50 backdrop-blur-xl',
        'shadow-lg hover:shadow-xl transition-shadow duration-300',
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}
