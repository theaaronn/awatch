import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import type { MetricPoint } from '../../types'

interface MetricChartProps {
  title: string
  unit: string
  data: MetricPoint[]
  color: string
  chartType: 'line' | 'area' | 'bar'
  anomalyTimestamps?: number[]
  loading: boolean
}

export default function MetricChart({
  title,
  unit,
  data,
  color,
  chartType,
  anomalyTimestamps = [],
  loading,
}: MetricChartProps) {
  if (loading) {
    return (
      <div className="rounded-lg bg-white p-6 dark:bg-gray-800">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{title}</h2>
        <div className="h-[200px] animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
      </div>
    )
  }

  const chartData = data.map((d) => ({
    ...d,
    timestamp: d.timestamp,
  }))

  const renderChart = () => {
    switch (chartType) {
      case 'line':
        return (
          <LineChart data={chartData}>
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => new Date(t).toLocaleTimeString()}
              stroke="#9ca3af"
              fontSize={12}
            />
            <YAxis stroke="#9ca3af" fontSize={12} />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)} ${unit}`]}
              labelFormatter={(t) => new Date(t).toLocaleString()}
              contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem' }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#fff' }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
            />
            {anomalyTimestamps.map((ts) => (
              <ReferenceLine key={ts} x={ts} stroke="red" strokeDasharray="3 3" />
            ))}
          </LineChart>
        )
      case 'area':
        return (
          <AreaChart data={chartData}>
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => new Date(t).toLocaleTimeString()}
              stroke="#9ca3af"
              fontSize={12}
            />
            <YAxis stroke="#9ca3af" fontSize={12} />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)} ${unit}`]}
              labelFormatter={(t) => new Date(t).toLocaleString()}
              contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem' }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#fff' }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              fill={color}
              fillOpacity={0.3}
            />
            {anomalyTimestamps.map((ts) => (
              <ReferenceLine key={ts} x={ts} stroke="red" strokeDasharray="3 3" />
            ))}
          </AreaChart>
        )
      case 'bar':
        return (
          <BarChart data={chartData}>
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => new Date(t).toLocaleTimeString()}
              stroke="#9ca3af"
              fontSize={12}
            />
            <YAxis stroke="#9ca3af" fontSize={12} />
            <Tooltip
              formatter={(v: number) => [`${v.toFixed(2)} ${unit}`]}
              labelFormatter={(t) => new Date(t).toLocaleString()}
              contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem' }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#fff' }}
            />
            <Bar dataKey="value" fill={color} />
            {anomalyTimestamps.map((ts) => (
              <ReferenceLine key={ts} x={ts} stroke="red" strokeDasharray="3 3" />
            ))}
          </BarChart>
        )
    }
  }

  return (
    <div className="rounded-lg bg-white p-6 dark:bg-gray-800">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">{title}</h2>
      <ResponsiveContainer width="100%" height={200}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  )
}
