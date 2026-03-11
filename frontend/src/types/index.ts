export interface MetricPoint {
  timestamp: number
  value: number
}

export interface Server {
  id: string
  agent_id: string
  hostname: string
  ip_address: string
  status: 'online' | 'offline'
  agent_version: string | null
  last_seen: string | null
  created_at: string
}

export interface Incident {
  id: string
  server_id: string
  agent_id: string
  severity: 'info' | 'warning' | 'critical'
  status: 'active' | 'acknowledged' | 'resolved'
  reconstruction_error: number
  threshold: number
  confidence: number
  affected_metrics: string[]
  message: string
  acknowledged_by: string | null
  acknowledged_at: string | null
  resolved_at: string | null
  created_at: string
}

export interface AlertMessage {
  type: 'alert' | 'ping' | 'buffered_alerts'
  timestamp: number
  data?: Incident
  alerts?: AlertMessage[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
