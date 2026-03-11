import type { Server } from '../../types'

interface ServerSelectorProps {
  servers: Server[]
  selectedAgentId: string | null
  onChange: (agentId: string) => void
}

export default function ServerSelector({ servers, selectedAgentId, onChange }: ServerSelectorProps) {
  return (
    <select
      value={selectedAgentId ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="block w-full max-w-xs rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
    >
      {servers.map((server) => (
        <option key={server.agent_id} value={server.agent_id}>
          {server.hostname} ({server.agent_id})
        </option>
      ))}
    </select>
  )
}
