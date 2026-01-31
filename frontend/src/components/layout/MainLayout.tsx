import { Outlet } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from './Header'

export function MainLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container px-4 py-6">
        <AnimatePresence mode="wait">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.2 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
