import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { getServers, deleteServer } from '../services/api'
import ServerCard from '../components/ServerCard'
import ServerRegistrationForm from '../components/ServerRegistrationForm'
import DeleteConfirmModal from '../components/DeleteConfirmModal'
import type { Server } from '../types'

export default function Servers() {
  const navigate = useNavigate()
  const { servers, setServers, setSelectedAgentId } = useAppStore()
  
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [pendingDeleteAgentId, setPendingDeleteAgentId] = useState<string | null>(null)

  useEffect(() => {
    async function fetchServers() {
      setLoading(true)
      try {
        const data = await getServers()
        setServers(data)
      } catch (err) {
        console.error('Failed to fetch servers:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchServers()
  }, [])

  const handleSelect = (agentId: string) => {
    setSelectedAgentId(agentId)
    navigate('/')
  }

  const handleDelete = async (agentId: string) => {
    try {
      await deleteServer(agentId)
      setServers(servers.filter((s) => s.agent_id !== agentId))
    } catch (err) {
      console.error('Failed to delete server:', err)
    }
    setPendingDeleteAgentId(null)
  }

  const handleRegistrationSuccess = (server: Server) => {
    setServers([...servers, server])
    setShowForm(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Servers</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Server'}
        </button>
      </div>

      {showForm && (
        <div className="mb-6">
          <ServerRegistrationForm
            onSuccess={handleRegistrationSuccess}
            onCancel={() => setShowForm(false)}
          />
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-2" />
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-2/3" />
            </div>
          ))}
        </div>
      ) : servers.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-500 dark:text-gray-400">No servers registered yet.</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-4 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700"
          >
            Register your first server
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {servers.map((server) => (
            <ServerCard
              key={server.id}
              server={server}
              onDelete={setPendingDeleteAgentId}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}

      <DeleteConfirmModal
        agentId={pendingDeleteAgentId}
        onConfirm={handleDelete}
        onCancel={() => setPendingDeleteAgentId(null)}
      />
    </div>
  )
}
