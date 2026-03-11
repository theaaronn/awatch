import { useState } from 'react'
import type { Server } from '../types'

interface ServerRegistrationFormProps {
  onSuccess: (server: Server) => void
  onCancel: () => void
}

export default function ServerRegistrationForm({ onSuccess, onCancel }: ServerRegistrationFormProps) {
  const [agentId, setAgentId] = useState('')
  const [hostname, setHostname] = useState('')
  const [ipAddress, setIpAddress] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!agentId) {
      newErrors.agent_id = 'Agent ID is required'
    } else if (!/^[a-zA-Z0-9_-]{1,64}$/.test(agentId)) {
      newErrors.agent_id = 'Must be 1-64 chars: letters, numbers, underscore, hyphen'
    }

    if (!hostname) {
      newErrors.hostname = 'Hostname is required'
    } else if (hostname.length > 255) {
      newErrors.hostname = 'Must be 255 characters or less'
    }

    if (!ipAddress) {
      newErrors.ip_address = 'IP address is required'
    } else if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(ipAddress) && !ipAddress.includes(':')) {
      newErrors.ip_address = 'Must be a valid IPv4 or IPv6 address'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)

    if (!validate()) return

    setLoading(true)
    try {
      const { createServer } = await import('../services/api')
      const server = await createServer({
        agent_id: agentId,
        hostname,
        ip_address: ipAddress,
      })
      onSuccess(server)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to register server'
      if (message.includes('already exists')) {
        setSubmitError('An agent with this ID already exists')
      } else {
        setSubmitError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-lg p-6 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Register New Server</h3>

      {submitError && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {submitError}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Agent ID
        </label>
        <input
          type="text"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:border-blue-500 focus:ring-blue-500"
          placeholder="e.g., prod-web-01"
        />
        {errors.agent_id && (
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.agent_id}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Hostname
        </label>
        <input
          type="text"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:border-blue-500 focus:ring-blue-500"
          placeholder="e.g., web-server-01"
        />
        {errors.hostname && (
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.hostname}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          IP Address
        </label>
        <input
          type="text"
          value={ipAddress}
          onChange={(e) => setIpAddress(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white focus:border-blue-500 focus:ring-blue-500"
          placeholder="e.g., 192.168.1.100"
        />
        {errors.ip_address && (
          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.ip_address}</p>
        )}
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed"
        >
          {loading ? 'Registering...' : 'Register'}
        </button>
      </div>
    </form>
  )
}
