import type { AlertMessage } from '../types'

type MessageHandler = (msg: AlertMessage) => void

export class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private handlers: Set<MessageHandler> = new Set()
  private reconnectAttempt = 0
  private readonly maxReconnectAttempts = 10
  private readonly backoffDelays = [1000, 2000, 4000, 8000, 16000, 30_000]
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private isIntentionallyClosed = false

  public status: 'disconnected' | 'connecting' | 'connected' | 'error' = 'disconnected'
  public onStatusChange?: (status: this['status']) => void

  constructor(baseWsUrl: string, apiKey: string) {
    this.url = `${baseWsUrl}/ws/alerts?api_key=${encodeURIComponent(apiKey)}`
  }

  connect(): void {
    this.isIntentionallyClosed = false
    this.status = 'connecting'
    this.onStatusChange?.(this.status)

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this.status = 'connected'
        this.reconnectAttempt = 0
        this.onStatusChange?.(this.status)
      }

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as AlertMessage
          this.handlers.forEach((handler) => handler(msg))
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      this.ws.onclose = () => {
        if (!this.isIntentionallyClosed) {
          this._scheduleReconnect()
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.status = 'error'
        this.onStatusChange?.(this.status)
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      this.status = 'error'
      this.onStatusChange?.(this.status)
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.status = 'error'
      this.onStatusChange?.(this.status)
      return
    }

    const delay = this.backoffDelays[Math.min(this.reconnectAttempt, this.backoffDelays.length - 1)]
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
    this.reconnectAttempt++
  }

  subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  close(): void {
    this.isIntentionallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.status = 'disconnected'
    this.onStatusChange?.(this.status)
  }
}

const wsUrl = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
const apiKey = import.meta.env.VITE_WS_API_KEY ?? ''
export const wsService = new WebSocketService(wsUrl, apiKey)
