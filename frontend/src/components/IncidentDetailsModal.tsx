import { useEffect } from 'react'
import type { Incident } from '../types'

interface IncidentDetailsModalProps {
  incident: Incident | null
  onClose: () => void
  onAcknowledge: (id: string) => void
  onResolve: (id: string) => void
}

export default function IncidentDetailsModal({
  incident,
  onClose,
  onAcknowledge,
  onResolve,
}: IncidentDetailsModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  if (!incident) return null

  const severityColors = {
    critical: 'bg-red-100 text-red-800 border-red-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    info: 'bg-blue-100 text-blue-800 border-blue-300',
  }

  const statusColors = {
    active: 'bg-red-100 text-red-800',
    acknowledged: 'bg-yellow-100 text-yellow-800',
    resolved: 'bg-green-100 text-green-800',
  }

  const metricColors: Record<string, string> = {
    cpu: 'bg-blue-200 text-blue-800',
    ram: 'bg-purple-200 text-purple-800',
    network_in: 'bg-green-200 text-green-800',
    network_out: 'bg-yellow-200 text-yellow-800',
    disk_read: 'bg-red-200 text-red-800',
    disk_write: 'bg-indigo-200 text-indigo-800',
  }

  const errorRatio = incident.reconstruction_error / incident.threshold
  const barWidth = Math.min(errorRatio * 50, 100)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto m-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Incident Details</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Server</label>
              <p className="text-gray-900 dark:text-white font-mono">{incident.agent_id}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Timestamp</label>
              <p className="text-gray-900 dark:text-white">{new Date(incident.created_at).toLocaleString()}</p>
            </div>
          </div>

          <div className="flex gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Severity</label>
              <div className="mt-1">
                <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full border ${severityColors[incident.severity]}`}>
                  {incident.severity}
                </span>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Status</label>
              <div className="mt-1">
                <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${statusColors[incident.status]}`}>
                  {incident.status}
                </span>
              </div>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Message</label>
            <p className="mt-1 text-gray-900 dark:text-white">{incident.message}</p>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Reconstruction Error vs Threshold</label>
            <div className="mt-2">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-400">Error: {incident.reconstruction_error.toFixed(4)}</span>
                <span className="text-gray-600 dark:text-gray-400">Threshold: {incident.threshold.toFixed(4)}</span>
              </div>
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500 rounded-full transition-all"
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Confidence: {incident.confidence.toFixed(2)}× threshold
              </p>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Affected Metrics</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {incident.affected_metrics.map((metric) => (
                <span
                  key={metric}
                  className={`px-3 py-1 text-sm rounded-full ${metricColors[metric] || 'bg-gray-200 text-gray-800'}`}
                >
                  {metric}
                </span>
              ))}
            </div>
          </div>

          {incident.acknowledged_at && (
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Acknowledged</label>
              <p className="text-gray-900 dark:text-white">{new Date(incident.acknowledged_at).toLocaleString()}</p>
            </div>
          )}

          {incident.resolved_at && (
            <div>
              <label className="text-sm font-medium text-gray-500 dark:text-gray-400">Resolved</label>
              <p className="text-gray-900 dark:text-white">{new Date(incident.resolved_at).toLocaleString()}</p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => {
              onAcknowledge(incident.id)
              onClose()
            }}
            disabled={incident.status !== 'active'}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-yellow-100 text-yellow-800 hover:bg-yellow-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed dark:bg-yellow-900/20 dark:text-yellow-400 dark:hover:bg-yellow-900/30"
          >
            Acknowledge
          </button>
          <button
            onClick={() => {
              onResolve(incident.id)
              onClose()
            }}
            disabled={incident.status === 'resolved'}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-green-100 text-green-800 hover:bg-green-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed dark:bg-green-900/20 dark:text-green-400 dark:hover:bg-green-900/30"
          >
            Resolve
          </button>
        </div>
      </div>
    </div>
  )
}
