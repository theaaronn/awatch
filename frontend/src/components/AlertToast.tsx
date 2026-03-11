import { useEffect } from 'react'
import type { AlertMessage } from '../types'

interface AlertToastProps {
  alert: AlertMessage
  onDismiss: () => void
}

export default function AlertToast({ alert, onDismiss }: AlertToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 8000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  if (!alert.data) return null

  const severityColors = {
    critical: 'border-red-500 bg-red-50 dark:bg-red-900/20',
    warning: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
    info: 'border-blue-500 bg-blue-50 dark:bg-blue-900/20',
  }

  const severity = alert.data.severity || 'info'

  return (
    <div
      className={`pointer-events-auto w-96 rounded-lg border-l-4 p-4 shadow-lg ${severityColors[severity]}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-900 dark:text-white">
            {alert.data.message}
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Agent: {alert.data.agent_id}
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            {new Date(alert.timestamp * 1000).toLocaleString()}
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="ml-4 rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
        >
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}
