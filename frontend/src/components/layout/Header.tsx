import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Users,
  ShoppingCart,
  History,
  Settings,
  LogOut,
  Palette,
  Bot,
  Play,
  Square,
  Check,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useAuth } from '@/context/AuthContext'
import { useTheme, themes } from '@/context/ThemeContext'
import { useBotStatus, useStartBot, useStopBot } from '@/hooks'
import { cn } from '@/lib/utils'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/accounts', label: 'Accounts', icon: Users },
  { path: '/orders', label: 'Orders', icon: ShoppingCart },
  { path: '/history', label: 'History', icon: History },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export function Header() {
  const location = useLocation()
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const { data: botStatus } = useBotStatus()
  const startBot = useStartBot()
  const stopBot = useStopBot()

  const isRunning = botStatus?.is_running ?? false

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-lg">
      <div className="container flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <motion.div
            whileHover={{ scale: 1.05 }}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600"
          >
            <Bot className="h-5 w-5 text-white" />
          </motion.div>
          <span className="text-lg font-bold gradient-text">CSFloat Bot</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            const Icon = item.icon
            return (
              <Link key={item.path} to={item.path}>
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'gap-2 transition-all',
                    isActive && 'bg-primary/10 text-primary'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Button>
              </Link>
            )
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Bot Status & Control */}
          <div className="flex items-center gap-2">
            <motion.div
              initial={false}
              animate={{ scale: isRunning ? [1, 1.2, 1] : 1 }}
              transition={{ repeat: isRunning ? Infinity : 0, duration: 2 }}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
                isRunning
                  ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                  : 'bg-gray-500/10 text-gray-600 dark:text-gray-400'
              )}
            >
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
                )}
              />
              {isRunning ? 'Running' : 'Stopped'}
            </motion.div>

            <Button
              size="sm"
              variant={isRunning ? 'destructive' : 'default'}
              onClick={() => (isRunning ? stopBot.mutate() : startBot.mutate())}
              disabled={startBot.isPending || stopBot.isPending}
              className="gap-1"
            >
              {isRunning ? (
                <>
                  <Square className="h-3 w-3" />
                  Stop
                </>
              ) : (
                <>
                  <Play className="h-3 w-3" />
                  Start
                </>
              )}
            </Button>
          </div>

          {/* Theme Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <Palette className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36">
              {themes.map((t) => (
                <DropdownMenuItem
                  key={t.id}
                  onClick={() => setTheme(t.id)}
                  className="flex items-center gap-2"
                >
                  <span
                    className="h-4 w-4 rounded-full border border-border"
                    style={{ backgroundColor: t.color }}
                  />
                  <span>{t.name}</span>
                  {theme === t.id && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="gap-2 px-2">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-primary/10 text-primary">
                    {user?.username?.charAt(0).toUpperCase() || 'U'}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden sm:inline-block text-sm font-medium">
                  {user?.username}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem className="text-muted-foreground">
                {user?.email}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {user?.is_admin && (
                <DropdownMenuItem asChild>
                  <Link to="/admin">Admin Panel</Link>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={logout} className="text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
