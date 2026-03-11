import { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import { getServers } from '../services/api'
import { useMetrics } from '../hooks/useMetrics'
import ServerSelector from '../components/charts/ServerSelector'
import TimeRangeSelector from '../components/charts/TimeRangeSelector'
import MetricChart from '../components/charts/MetricChart'

const CHART_CONFIG = [
  { key: 'cpu', title: 'CPU Usage', unit: '%', color: '#3b82f6', chartType: 'line' as const },
  { key: 'ram', title: 'RAM Usage', unit: '%', color: '#8b5cf6', chartType: 'area' as const },
  { key: 'network_in', title: 'Network In', unit: 'bytes/s', color: '#10b981', chartType: 'line' as const },
  { key: 'network_out', title: 'Network Out', unit: 'bytes/s', color: '#f59e0b', chartType: 'line' as const },
  { key: 'disk_read', title: 'Disk Read', unit: 'bytes/s', color: '#ef4444', chartType: 'bar' as const },
  { key: 'disk_write', title: 'Disk Write', unit: 'bytes/s', color: '#6366f1', chartType: 'bar' as const },
]

const DEFAULT_VISIBLE = ['cpu', 'ram', 'network_in', 'disk_read']

export default function Dashboard() {
  const { 
    servers, 
    setServers, 
    setServersLoading, 
    setServersError, 
    selectedAgentId, 
    setSelectedAgentId 
  } = useAppStore()
  
  const [timeRange, setTimeRange] = useState<'-1h' | '-6h' | '-24h' | '-7d'>('-1h')
  const [showAll, setShowAll] = useState(false)
  
  const { data, loading, error } = useMetrics(selectedAgentId, timeRange)

  useEffect(() => {
    async function fetchServers() {
      setServersLoading(true)
      try {
        const data = await getServers()
        setServers(data)
        if (!selectedAgentId && data.length > 0) {
          setSelectedAgentId(data[0].agent_id)
        }
      } catch (err) {
        setServersError(err instanceof Error ? err.message : 'Failed to fetch servers')
      } finally {
        setServersLoading(false)
      }
    }
    fetchServers()
  }, [])

  const visibleCharts = showAll ? CHART_CONFIG : CHART_CONFIG.filter(c => DEFAULT_VISIBLE.includes(c.key))

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      
      {servers.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-500 dark:text-gray-400">No servers registered yet.</p>
        </div>
      ) : (
        <>
          <div className="mb-6">
            <ServerSelector 
              servers={servers} 
              selectedAgentId={selectedAgentId} 
              onChange={setSelectedAgentId} 
            />
          </div>
          
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {error}
            </div>
          )}
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {visibleCharts.map((config) => (
              <MetricChart
                key={config.key}
                title={config.title}
                unit={config.unit}
                data={data[config.key] || []}
                color={config.color}
                chartType={config.chartType}
                loading={loading}
              />
            ))}
          </div>
          
          <div className="mt-4 text-center">
            <button
              onClick={() => setShowAll(!showAll)}
              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {showAll ? 'Show less' : 'Show all metrics'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
