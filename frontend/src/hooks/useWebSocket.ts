import { useEffect, useState } from 'react'
import { useAppStore } from '../store'
import { wsService } from '../services/websocket'

export function useWebSocket() {
  const addLiveAlert = useAppStore((s) => s.addLiveAlert)
  const [status, setStatus] = useState(wsService.status)

  useEffect(() => {
    wsService.onStatusChange = setStatus

    const unsub = wsService.subscribe((msg) => {
      if (msg.type === 'alert' && msg.data) {
        addLiveAlert(msg)
      }
    })

    wsService.connect()

    return () => {
      unsub()
      wsService.onStatusChange = undefined
    }
  }, [])

  return { status }
}
