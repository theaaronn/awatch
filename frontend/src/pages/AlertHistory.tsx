import { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import { getIncidents, acknowledgeIncident, resolveIncident, getServers } from '../services/api'
import IncidentTable from '../components/IncidentTable'
import IncidentDetailsModal from '../components/IncidentDetailsModal'
import type { Incident, Server } from '../types'

const PAGE_SIZE = 50

export default function AlertHistory() {
  const { incidents, setIncidents, updateIncident, setServers } = useAppStore()
  
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('')
  const [filterServerId, setFilterServerId] = useState('')
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [servers, setServersLocal] = useState<Server[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)

  useEffect(() => {
    async function loadServers() {
      try {
        const data = await getServers()
        setServersLocal(data)
        setServers(data)
      } catch (err) {
        console.error('Failed to load servers:', err)
      }
    }
    loadServers()
  }, [])

  useEffect(() => {
    async function fetchIncidents() {
      setLoading(true)
      try {
        const response = await getIncidents({
          server_id: filterServerId || undefined,
          status: filterStatus || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        })
        setIncidents(response.items, response.total)
        setTotal(response.total)
      } catch (err) {
        console.error('Failed to fetch incidents:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchIncidents()
  }, [filterStatus, filterSeverity, filterServerId, page])

  const handleFilterChange = (setter: (v: string) => void) => (value: string) => {
    setter(value)
    setPage(0)
  }

  const handleAcknowledge = async (id: string) => {
    try {
      const updated = await acknowledgeIncident(id)
      updateIncident(updated)
    } catch (err) {
      console.error('Failed to acknowledge incident:', err)
    }
  }

  const handleResolve = async (id: string) => {
    try {
      const updated = await resolveIncident(id)
      updateIncident(updated)
    } catch (err) {
      console.error('Failed to resolve incident:', err)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Alert History</h1>

      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 mb-6">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Severity
            </label>
            <select
              value={filterSeverity}
              onChange={(e) => handleFilterChange(setFilterSeverity)(e.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="">All</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Status
            </label>
            <select
              value={filterStatus}
              onChange={(e) => handleFilterChange(setFilterStatus)(e.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Server
            </label>
            <select
              value={filterServerId}
              onChange={(e) => handleFilterChange(setFilterServerId)(e.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="">All servers</option>
              {servers.map((server) => (
                <option key={server.id} value={server.id}>
                  {server.hostname} ({server.agent_id})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <IncidentTable
        incidents={incidents}
        loading={loading}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
        onRowClick={setSelectedIncident}
      />

      <div className="flex items-center justify-between mt-4">
        <button
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
        >
          ← Previous
        </button>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          Page {page + 1} of {totalPages || 1}
        </span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={(page + 1) * PAGE_SIZE >= total}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
        >
          Next →
        </button>
      </div>

      <IncidentDetailsModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
      />
    </div>
  )
}
