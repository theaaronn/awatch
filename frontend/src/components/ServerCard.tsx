import type { Server } from '../types'

interface ServerCardProps {
  server: Server
  onDelete: (agentId: string) => void
  onSelect: (agentId: string) => void
}

const relativeTime = (iso: string | null): string => {
  if (!iso) return 'Never'
  const diffMs = Date.now() - new Date(iso).getTime()
  if (diffMs < 60_000) return 'Just now'
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`
  return `${Math.floor(diffMs / 86_400_000)}d ago`
}

export default function ServerCard({ server, onDelete, onSelect }: ServerCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              server.status === 'online' ? 'bg-green-500' : 'bg-gray-400'
            }`}
          />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {server.hostname}
          </h3>
        </div>
      </div>

      <div className="mt-2 space-y-1">
        <p className="text-sm font-mono text-gray-500 dark:text-gray-400">
          {server.agent_id}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {server.ip_address}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Last seen: {relativeTime(server.last_seen)}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Agent: {server.agent_version ? `v${server.agent_version}` : 'Unknown'}
        </p>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          onClick={() => onSelect(server.agent_id)}
          className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/30"
        >
          View metrics
        </button>
        <button
          onClick={() => onDelete(server.agent_id)}
          className="px-3 py-2 text-sm font-medium rounded-lg bg-red-100 text-red-800 hover:bg-red-200 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/30"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
