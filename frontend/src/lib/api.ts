import axios from 'axios'
import type {
  AuthResponse,
  LoginCredentials,
  RegisterCredentials,
  Account,
  CreateAccountData,
  BuyOrder,
  OutbidHistory,
  BotSettings,
  BotStatus,
  AdminStats,
  User,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/login', credentials)
    return data
  },

  register: async (credentials: RegisterCredentials): Promise<AuthResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/register', credentials)
    return data
  },

  me: async (): Promise<User> => {
    const { data } = await api.get<User>('/auth/me')
    return data
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
  },
}

// Bot API
export const botApi = {
  getStatus: async (): Promise<BotStatus> => {
    const { data } = await api.get<BotStatus>('/bot/status')
    return data
  },

  start: async (): Promise<void> => {
    await api.post('/bot/start')
  },

  stop: async (): Promise<void> => {
    await api.post('/bot/stop')
  },
}

// Accounts API
export const accountsApi = {
  getAll: async (): Promise<Account[]> => {
    const { data } = await api.get<Account[]>('/accounts')
    return data
  },

  create: async (account: CreateAccountData): Promise<Account> => {
    const { data } = await api.post<Account>('/accounts', account)
    return data
  },

  update: async (id: number, account: Partial<CreateAccountData>): Promise<Account> => {
    const { data } = await api.put<Account>(`/accounts/${id}`, account)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/accounts/${id}`)
  },

  test: async (id: number): Promise<{ success: boolean; message?: string }> => {
    const { data } = await api.post(`/accounts/${id}/test`)
    return data
  },

  syncOrders: async (id: number): Promise<void> => {
    await api.post(`/accounts/${id}/sync-orders`)
  },
}

// Orders API
export const ordersApi = {
  getAll: async (activeOnly = true): Promise<BuyOrder[]> => {
    const { data } = await api.get<BuyOrder[]>('/orders', {
      params: { active_only: activeOnly },
    })
    return data
  },

  delete: async (orderId: string): Promise<void> => {
    await api.delete(`/orders/${orderId}`)
  },
}

// History API
export const historyApi = {
  getAll: async (limit = 50): Promise<OutbidHistory[]> => {
    const { data } = await api.get<OutbidHistory[]>('/history', {
      params: { limit },
    })
    return data
  },
}

// Settings API
export const settingsApi = {
  get: async (): Promise<BotSettings> => {
    const { data } = await api.get<BotSettings>('/settings')
    return data
  },

  update: async (settings: Partial<BotSettings>): Promise<BotSettings> => {
    const { data } = await api.put<BotSettings>('/settings', settings)
    return data
  },
}

// Admin API
export const adminApi = {
  getStats: async (): Promise<AdminStats> => {
    const { data } = await api.get<AdminStats>('/admin/stats')
    return data
  },

  getUsers: async (): Promise<User[]> => {
    const { data } = await api.get<User[]>('/admin/users')
    return data
  },

  updateUser: async (id: number, userData: Partial<User>): Promise<User> => {
    const { data } = await api.put<User>(`/admin/users/${id}`, userData)
    return data
  },

  getLogs: async (limit = 100): Promise<string[]> => {
    const { data } = await api.get<string[]>('/admin/logs', {
      params: { limit },
    })
    return data
  },
}

export default api
