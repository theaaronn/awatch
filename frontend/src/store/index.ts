import { create } from 'zustand'
import type { Server, Incident, AlertMessage } from '../types'

interface AppState {
  servers: Server[]
  serversLoading: boolean
  serversError: string | null
  setServers: (servers: Server[]) => void
  setServersLoading: (v: boolean) => void
  setServersError: (e: string | null) => void

  incidents: Incident[]
  incidentsTotal: number
  incidentsLoading: boolean
  incidentsError: string | null
  setIncidents: (items: Incident[], total: number) => void
  setIncidentsLoading: (v: boolean) => void
  setIncidentsError: (e: string | null) => void
  updateIncident: (updated: Incident) => void

  liveAlerts: AlertMessage[]
  unreadAlertCount: number
  addLiveAlert: (alert: AlertMessage) => void
  clearUnreadCount: () => void

  selectedAgentId: string | null
  setSelectedAgentId: (id: string | null) => void
  darkMode: boolean
  toggleDarkMode: () => void
}

export const useAppStore = create<AppState>((set) => ({
  servers: [],
  serversLoading: false,
  serversError: null,
  setServers: (servers) => set({ servers }),
  setServersLoading: (v) => set({ serversLoading: v }),
  setServersError: (e) => set({ serversError: e }),

  incidents: [],
  incidentsTotal: 0,
  incidentsLoading: false,
  incidentsError: null,
  setIncidents: (items, total) => set({ incidents: items, incidentsTotal: total }),
  setIncidentsLoading: (v) => set({ incidentsLoading: v }),
  setIncidentsError: (e) => set({ incidentsError: e }),
  updateIncident: (updated) =>
    set((s) => ({ incidents: s.incidents.map((i) => (i.id === updated.id ? updated : i)) })),

  liveAlerts: [],
  unreadAlertCount: 0,
  addLiveAlert: (alert) =>
    set((s) => ({
      liveAlerts: [alert, ...s.liveAlerts].slice(0, 100),
      unreadAlertCount: s.unreadAlertCount + 1,
    })),
  clearUnreadCount: () => set({ unreadAlertCount: 0 }),

  selectedAgentId: null,
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
  darkMode: false,
  toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),
}))
