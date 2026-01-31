// User & Auth types
export interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface RegisterCredentials {
  username: string
  email: string
  password: string
}

// Account types
export interface Account {
  id: number
  name: string
  api_key: string
  proxy?: string
  is_active: boolean
  status: 'idle' | 'online' | 'error'
  error_message?: string
  last_check?: string
  user_id?: number
}

export interface CreateAccountData {
  name: string
  api_key: string
  proxy?: string
}

// Order types
export interface BuyOrder {
  id: number
  order_id: string
  account_id: number
  market_hash_name: string
  price_cents: number
  quantity: number
  order_type: 'simple' | 'advanced'
  float_min?: number
  float_max?: number
  def_index?: number
  paint_index?: number
  icon_url?: string
  is_active: boolean
  outbid_count: number
  created_at: string
  updated_at: string
}

// History types
export interface OutbidHistory {
  id: number
  account_id: number
  order_id: string
  market_hash_name: string
  old_price_cents: number
  new_price_cents: number
  competitor_price_cents: number
  timestamp: string
}

// Settings types
export interface BotSettings {
  check_interval: number
  outbid_step: number
  max_outbids: number
  price_ceiling_percent: number
}

// Bot status
export interface BotStatus {
  is_running: boolean
  check_interval: number
  outbid_step: number
  max_outbids: number
  active_tasks: number
}

// Admin types
export interface AdminStats {
  total_users: number
  active_accounts: number
  total_orders: number
  total_outbids: number
}

export interface LogEntry {
  timestamp: string
  level: string
  message: string
}
