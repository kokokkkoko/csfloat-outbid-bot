import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type { User, LoginCredentials, RegisterCredentials } from '@/types'
import { authApi } from '@/lib/api'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  register: (credentials: RegisterCredentials) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check if user is already logged in
    const storedUser = localStorage.getItem('user')
    const token = localStorage.getItem('access_token')

    if (storedUser && token) {
      try {
        setUser(JSON.parse(storedUser))
      } catch {
        localStorage.removeItem('user')
        localStorage.removeItem('access_token')
      }
    }
    setIsLoading(false)
  }, [])

  const login = async (credentials: LoginCredentials) => {
    const response = await authApi.login(credentials)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    setUser(response.user)
  }

  const register = async (credentials: RegisterCredentials) => {
    const response = await authApi.register(credentials)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    setUser(response.user)
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
