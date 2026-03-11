interface TimeRangeSelectorProps {
  value: '-1h' | '-6h' | '-24h' | '-7d'
  onChange: (range: '-1h' | '-6h' | '-24h' | '-7d') => void
}

const ranges: Array<{ value: '-1h' | '-6h' | '-24h' | '-7d'; label: string }> = [
  { value: '-1h', label: '1h' },
  { value: '-6h', label: '6h' },
  { value: '-24h', label: '24h' },
  { value: '-7d', label: '7d' },
]

export default function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-700">
      {ranges.map((range) => (
        <button
          key={range.value}
          onClick={() => onChange(range.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === range.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-200 dark:hover:bg-gray-500'
          }`}
        >
          {range.label}
        </button>
      ))}
    </div>
  )
}
