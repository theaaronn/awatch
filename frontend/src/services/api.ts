import axios, { AxiosInstance } from 'axios'
import type { Server, Incident, MetricPoint, PaginatedResponse } from '../types'

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const key = localStorage.getItem('awatch_api_key')
  if (key) config.headers['X-API-Key'] = key
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    const message = err.response?.data?.message ?? err.message
    return Promise.reject(new Error(message))
  }
)

export const getServers = (): Promise<Server[]> =>
  apiClient.get('/servers').then((r) => r.data)

export const createServer = (body: {
  agent_id: string
  hostname: string
  ip_address: string
}): Promise<Server> =>
  apiClient.post('/servers', body).then((r) => r.data)

export const deleteServer = (agentId: string): Promise<void> =>
  apiClient.delete(`/servers/${agentId}`).then(() => undefined)

export const getIncidents = (params: {
  server_id?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<Incident>> =>
  apiClient.get('/incidents', { params }).then((r) => r.data)

export const acknowledgeIncident = (id: string): Promise<Incident> =>
  apiClient.post(`/incidents/${id}/acknowledge`).then((r) => r.data)

export const resolveIncident = (id: string): Promise<Incident> =>
  apiClient.post(`/incidents/${id}/resolve`).then((r) => r.data)

export const getMetrics = (params: {
  agent_id: string
  metric_type: string
  start?: string
}): Promise<MetricPoint[]> =>
  apiClient.get('/metrics', { params }).then((r) => r.data)

export const getModelStatus = () =>
  apiClient.get('/model/status').then((r) => r.data)

export const triggerTraining = (body: {
  start_time?: number
  end_time?: number
  agent_id?: string
}) => apiClient.post('/model/train', body).then((r) => r.data)
