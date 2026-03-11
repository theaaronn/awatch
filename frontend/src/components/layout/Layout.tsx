import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useAppStore } from '../../store'
import { useWebSocket } from '../../hooks/useWebSocket'
import Header from './Header'
import Sidebar from './Sidebar'
import AlertToast from '../AlertToast'
import type { AlertMessage } from '../../types'

export default function Layout() {
  const darkMode = useAppStore((state) => state.darkMode)
  const liveAlerts = useAppStore((state) => state.liveAlerts)
  useWebSocket()
  
  const [toasts, setToasts] = useState<AlertMessage[]>([])
  const [seenTimestamps, setSeenTimestamps] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (liveAlerts.length > 0) {
      const latestAlert = liveAlerts[0]
      if (!seenTimestamps.has(latestAlert.timestamp)) {
        setSeenTimestamps((prev) => new Set([...prev, latestAlert.timestamp]))
        setToasts((prev) => [latestAlert, ...prev].slice(0, 5))
      }
    }
  }, [liveAlerts, seenTimestamps])

  const dismissToast = (timestamp: number) => {
    setToasts((prev) => prev.filter((t) => t.timestamp !== timestamp))
  }

  return (
    <div className={darkMode ? 'dark' : ''}>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <Header />
        <div className="flex">
          <Sidebar />
          <main className="flex-1 p-6 min-h-[calc(100vh-4rem)]">
            <Outlet />
          </main>
        </div>
      </div>
      
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((alert) => (
          <AlertToast
            key={alert.timestamp}
            alert={alert}
            onDismiss={() => dismissToast(alert.timestamp)}
          />
        ))}
      </div>
    </div>
  )
}
