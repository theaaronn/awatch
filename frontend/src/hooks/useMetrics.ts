import { useState, useEffect } from 'react'
import type { MetricPoint } from '../types'
import { getMetrics } from '../services/api'

export function useMetrics(agentId: string | null, timeRange: '-1h' | '-6h' | '-24h' | '-7d') {
  const [data, setData] = useState<Record<string, MetricPoint[]>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!agentId) return
    const metrics = ['cpu', 'ram', 'network_in', 'network_out', 'disk_read', 'disk_write']
    
    const fetch = async () => {
      setLoading(true)
      try {
        const results = await Promise.all(
          metrics.map((m) => getMetrics({ agent_id: agentId, metric_type: m, start: timeRange }))
        )
        setData(Object.fromEntries(metrics.map((m, i) => [m, results[i]])))
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    }

    fetch()
    const interval = setInterval(fetch, 5000)
    return () => clearInterval(interval)
  }, [agentId, timeRange])

  return { data, loading, error }
}
