import { createBrowserRouter } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Dashboard from '../pages/Dashboard'
import Servers from '../pages/Servers'
import AlertHistory from '../pages/AlertHistory'
import Settings from '../pages/Settings'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'servers', element: <Servers /> },
      { path: 'alerts', element: <AlertHistory /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
])
